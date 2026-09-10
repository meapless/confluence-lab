from __future__ import annotations

import hashlib
import io
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen

import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .data import dataframe_fingerprint, diagnose_dataset, validate_dataset
from .experiments import ValidationGate
from .families import FAMILIES
from .matrix import ExecutionVariant, run_matrix_experiment
from .payouts import break_even_win_rate
from .splits import chronological_split
from .strategies import (
    always_call,
    always_put,
    ema_crossover,
    random_baseline,
    rsi_reversal,
)


@dataclass(frozen=True)
class PublicBenchmarkSource:
    name: str
    repository: str
    commit: str
    blob_sha: str
    path: str
    timestamp_column: str
    symbol: str
    timeframe: str
    timestamp_interpretation: str = "UTC"
    rename_columns: Mapping[str, str] | None = None
    license: str | None = None

    @property
    def url(self) -> str:
        return (
            "https://raw.githubusercontent.com/"
            f"{self.repository}/{self.commit}/{self.path}"
        )


@dataclass(frozen=True)
class PublicBenchmarkPolicy:
    fixed_payout: float = 0.82
    expiries: tuple[int, ...] = (1, 2, 3, 5)
    search_objective: str = "wilson_low"
    min_development_trades: int = 30
    min_development_expectancy: float | None = 0.0
    min_validation_trades: int = 30
    min_locked_test_trades: int = 30
    require_validation_wilson_above_break_even: bool = True

    def validation_gate(self) -> ValidationGate:
        threshold = (
            break_even_win_rate(self.fixed_payout)
            if self.require_validation_wilson_above_break_even
            else None
        )
        return ValidationGate(
            min_trades=self.min_validation_trades,
            min_expectancy=0.0,
            min_locked_test_trades=self.min_locked_test_trades,
            min_wilson_low=threshold,
        )


def download_source(source: PublicBenchmarkSource, *, timeout: float = 60.0) -> bytes:
    request = Request(
        source.url,
        headers={"User-Agent": "ConfluenceLabBenchmark/0.4"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - pinned GitHub host
        payload = response.read()
    if not payload:
        raise RuntimeError(f"benchmark source {source.name!r} returned no bytes")
    return payload


def normalize_csv_source(
    payload: bytes,
    source: PublicBenchmarkSource,
) -> pd.DataFrame:
    frame = pd.read_csv(io.BytesIO(payload))
    rename = dict(source.rename_columns or {})
    if rename:
        frame = frame.rename(columns=rename)

    timestamp_column = rename.get(source.timestamp_column, source.timestamp_column)
    if timestamp_column not in frame.columns:
        raise ValueError(
            f"source dataset missing timestamp column {timestamp_column!r}"
        )
    if timestamp_column != "timestamp":
        frame = frame.rename(columns={timestamp_column: "timestamp"})

    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"source dataset missing OHLC columns: {sorted(missing)}")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    preferred = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "spread",
        "real_volume",
    ]
    keep = [column for column in preferred if column in frame.columns]
    return validate_dataset(frame[keep], allow_gaps=True)


def metric_payload(metrics, *, payout: float) -> dict[str, object] | None:
    if metrics is None:
        return None
    values = asdict(metrics)
    threshold = break_even_win_rate(payout)
    values["hypothetical_break_even_win_rate"] = threshold
    values["wilson_lower_above_break_even"] = (
        metrics.wilson_low is not None and metrics.wilson_low > threshold
    )
    values["positive_expectancy"] = (
        metrics.expectancy is not None and metrics.expectancy > 0
    )
    return values


def baseline_results(
    frame: pd.DataFrame,
    policy: PublicBenchmarkPolicy,
) -> list[dict[str, object]]:
    split = chronological_split(frame)
    baselines = {
        "always_call": always_call,
        "always_put": always_put,
        "random_seed_7": lambda data: random_baseline(data, seed=7),
        "ema_crossover_10_30": lambda data: ema_crossover(data, fast=10, slow=30),
        "rsi_reversal_14_30_70": lambda data: rsi_reversal(
            data, period=14, lower=30, upper=70
        ),
    }
    rows: list[dict[str, object]] = []
    for name, strategy in baselines.items():
        for expiry in policy.expiries:
            config = BacktestConfig(
                expiry_bars=expiry,
                fixed_payout=policy.fixed_payout,
            )
            rows.append(
                {
                    "name": name,
                    "expiry_bars": expiry,
                    "development": metric_payload(
                        run_backtest(split.development, strategy, config).metrics,
                        payout=policy.fixed_payout,
                    ),
                    "validation": metric_payload(
                        run_backtest(split.validation, strategy, config).metrics,
                        payout=policy.fixed_payout,
                    ),
                    "locked_test": metric_payload(
                        run_backtest(split.test, strategy, config).metrics,
                        payout=policy.fixed_payout,
                    ),
                }
            )
    return rows


def run_public_benchmark(
    payload: bytes,
    source: PublicBenchmarkSource,
    *,
    policy: PublicBenchmarkPolicy = PublicBenchmarkPolicy(),
    family_names: Iterable[str] | None = None,
) -> dict[str, object]:
    frame = normalize_csv_source(payload, source)
    diagnostics = diagnose_dataset(frame)
    gate = policy.validation_gate()
    threshold = break_even_win_rate(policy.fixed_payout)

    variants = [
        ExecutionVariant(
            expiry_bars=expiry,
            fixed_payout=policy.fixed_payout,
            payout_column=None,
            min_payout=None,
        )
        for expiry in policy.expiries
    ]

    selected_names = list(family_names) if family_names is not None else list(FAMILIES)
    families: dict[str, Any] = {}
    total_evaluations = 0
    for name in selected_names:
        if name not in FAMILIES:
            raise ValueError(f"unknown family {name!r}")
        family = FAMILIES[name]
        result = run_matrix_experiment(
            frame,
            family.builder,
            family.parameter_grid,
            variants,
            objective=policy.search_objective,
            search_min_trades=policy.min_development_trades,
            search_min_expectancy=policy.min_development_expectancy,
            gate=gate,
            prepared_factory=family.prepared_factory,
        )
        evaluations = family.grid_size * len(variants)
        total_evaluations += evaluations
        best = None
        if result.best_development is not None:
            best = {
                "params": result.best_development.params,
                "execution": asdict(result.best_development.execution),
                "score": result.best_development.score,
                "metrics": metric_payload(
                    result.best_development.metrics,
                    payout=policy.fixed_payout,
                ),
            }
        locked_payload = metric_payload(result.test_metrics, payout=policy.fixed_payout)
        families[name] = {
            "description": family.description,
            "intended_regimes": list(family.intended_regimes),
            "development_configurations_evaluated": evaluations,
            "status": result.status,
            "best_development": best,
            "validation": metric_payload(
                result.validation_metrics,
                payout=policy.fixed_payout,
            ),
            "locked_test": locked_payload,
            "locked_test_evidence_pass": bool(
                result.status == "tested"
                and locked_payload is not None
                and locked_payload["positive_expectancy"]
                and locked_payload["wilson_lower_above_break_even"]
            ),
        }

    return {
        "benchmark_kind": "third_party_regular_fx_engineering_benchmark",
        "interpretation_warning": (
            "This is NOT Pocket Option or OTC data. The fixed payout is a hypothetical "
            "economics assumption used to evaluate binary-style expectancy. Results must "
            "not be marketed as Pocket performance or expected future returns."
        ),
        "source": {
            "name": source.name,
            "repository": source.repository,
            "commit": source.commit,
            "blob_sha": source.blob_sha,
            "path": source.path,
            "url": source.url,
            "license": source.license,
            "downloaded_bytes": len(payload),
            "download_sha256": hashlib.sha256(payload).hexdigest(),
        },
        "dataset": {
            "rows": len(frame),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnostics),
            "timestamp_interpretation": source.timestamp_interpretation,
            "symbol": source.symbol,
            "timeframe": source.timeframe,
        },
        "economics": {
            "payout_source": "hypothetical_fixed_assumption",
            "fixed_payout": policy.fixed_payout,
            "break_even_win_rate": threshold,
        },
        "research_policy": {
            "development_fraction": 0.60,
            "validation_fraction": 0.20,
            "locked_test_fraction": 0.20,
            "search_objective": policy.search_objective,
            "minimum_development_trades": policy.min_development_trades,
            "minimum_development_expectancy": policy.min_development_expectancy,
            "minimum_validation_trades": gate.min_trades,
            "minimum_locked_test_trades": gate.min_locked_test_trades,
            "validation_requires_positive_expectancy": True,
            "validation_min_wilson_low": gate.min_wilson_low,
            "locked_evidence_requires_positive_expectancy": True,
            "locked_evidence_requires_wilson_lower_above_break_even": True,
        },
        "development_configurations_evaluated": total_evaluations,
        "strategy_families": families,
        "baselines": baseline_results(frame, policy),
    }
