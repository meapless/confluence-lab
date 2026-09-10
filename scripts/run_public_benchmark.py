from __future__ import annotations

import argparse
import hashlib
import io
import json
from dataclasses import asdict
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest
from confluence_lab.data import dataframe_fingerprint, diagnose_dataset, validate_dataset
from confluence_lab.experiments import ValidationGate
from confluence_lab.families import FAMILIES
from confluence_lab.matrix import ExecutionVariant, run_matrix_experiment
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.splits import chronological_split
from confluence_lab.strategies import (
    always_call,
    always_put,
    ema_crossover,
    random_baseline,
    rsi_reversal,
)

SOURCE_REPOSITORY = "shubhamlodha21/MetaTrader-5-Data-Downloader"
SOURCE_COMMIT = "79733c68c5d26490efd4b85b31c5c2c17a907423"
SOURCE_BLOB = "b2f840067011782c6dcdd1ce7a5c036efa711fac"
SOURCE_PATH = "EURUSD_1_Minute_2025-03-04_to_2025-04-03.csv"
SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    f"{SOURCE_REPOSITORY}/{SOURCE_COMMIT}/{SOURCE_PATH}"
)

HYPOTHETICAL_PAYOUT = 0.82
EXPIRIES = (1, 2, 3, 5)


def _download_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "ConfluenceLabBenchmark/0.3"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - pinned trusted GitHub host
        payload = response.read()
    if not payload:
        raise RuntimeError("public benchmark dataset download returned no bytes")
    return payload


def _normalize_source(payload: bytes) -> pd.DataFrame:
    frame = pd.read_csv(io.BytesIO(payload))
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"source dataset missing expected columns: {sorted(missing)}")

    frame = frame.rename(columns={"time": "timestamp", "tick_volume": "volume"})
    # MetaTrader bar epochs are UTC; the source exporter converts those epochs to
    # naive display strings. Reattach UTC explicitly rather than local machine time.
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    keep = [
        column
        for column in (
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "spread",
            "real_volume",
        )
        if column in frame.columns
    ]
    return validate_dataset(frame[keep], allow_gaps=True)


def _metric_payload(metrics, *, payout: float) -> dict[str, object] | None:
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


def _baseline_results(frame: pd.DataFrame) -> list[dict[str, object]]:
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
        for expiry in EXPIRIES:
            config = BacktestConfig(expiry_bars=expiry, fixed_payout=HYPOTHETICAL_PAYOUT)
            development = run_backtest(split.development, strategy, config).metrics
            validation = run_backtest(split.validation, strategy, config).metrics
            locked = run_backtest(split.test, strategy, config).metrics
            rows.append(
                {
                    "name": name,
                    "expiry_bars": expiry,
                    "development": _metric_payload(development, payout=HYPOTHETICAL_PAYOUT),
                    "validation": _metric_payload(validation, payout=HYPOTHETICAL_PAYOUT),
                    "locked_test": _metric_payload(locked, payout=HYPOTHETICAL_PAYOUT),
                }
            )
    return rows


def run_benchmark(output: Path) -> dict[str, object]:
    raw = _download_bytes(SOURCE_URL)
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    frame = _normalize_source(raw)
    diagnostics = diagnose_dataset(frame)

    gate = ValidationGate(
        min_trades=30,
        min_expectancy=0.0,
        min_locked_test_trades=30,
    )
    variants = [
        ExecutionVariant(
            expiry_bars=expiry,
            fixed_payout=HYPOTHETICAL_PAYOUT,
            payout_column=None,
            min_payout=None,
        )
        for expiry in EXPIRIES
    ]

    families: dict[str, object] = {}
    total_evaluations = 0
    for name, family in FAMILIES.items():
        result = run_matrix_experiment(
            frame,
            family.builder,
            family.parameter_grid,
            variants,
            objective="wilson_low",
            search_min_trades=30,
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
                "metrics": _metric_payload(
                    result.best_development.metrics,
                    payout=HYPOTHETICAL_PAYOUT,
                ),
            }
        locked_payload = _metric_payload(result.test_metrics, payout=HYPOTHETICAL_PAYOUT)
        families[name] = {
            "description": family.description,
            "intended_regimes": list(family.intended_regimes),
            "development_configurations_evaluated": evaluations,
            "status": result.status,
            "best_development": best,
            "validation": _metric_payload(
                result.validation_metrics, payout=HYPOTHETICAL_PAYOUT
            ),
            "locked_test": locked_payload,
            "locked_test_evidence_pass": bool(
                result.status == "tested"
                and locked_payload is not None
                and locked_payload["positive_expectancy"]
                and locked_payload["wilson_lower_above_break_even"]
            ),
        }

    report: dict[str, object] = {
        "benchmark_kind": "third_party_regular_fx_engineering_benchmark",
        "interpretation_warning": (
            "This is NOT Pocket Option or OTC data. The 82% payout is a hypothetical "
            "economics assumption used to evaluate binary-style expectancy. Results must "
            "not be marketed as Pocket performance or expected future returns."
        ),
        "source": {
            "repository": SOURCE_REPOSITORY,
            "commit": SOURCE_COMMIT,
            "blob_sha": SOURCE_BLOB,
            "path": SOURCE_PATH,
            "url": SOURCE_URL,
            "downloaded_bytes": len(raw),
            "download_sha256": raw_sha256,
        },
        "dataset": {
            "rows": len(frame),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnostics),
            "timestamp_interpretation": "UTC",
            "symbol": "EURUSD",
            "timeframe": "1 minute",
        },
        "economics": {
            "payout_source": "hypothetical_fixed_assumption",
            "fixed_payout": HYPOTHETICAL_PAYOUT,
            "break_even_win_rate": break_even_win_rate(HYPOTHETICAL_PAYOUT),
        },
        "research_policy": {
            "development_fraction": 0.60,
            "validation_fraction": 0.20,
            "locked_test_fraction": 0.20,
            "search_objective": "wilson_low",
            "minimum_development_trades": 30,
            "minimum_validation_trades": gate.min_trades,
            "minimum_locked_test_trades": gate.min_locked_test_trades,
            "validation_requires_positive_expectancy": True,
            "locked_evidence_requires_positive_expectancy": True,
            "locked_evidence_requires_wilson_lower_above_break_even": True,
        },
        "development_configurations_evaluated": total_evaluations,
        "strategy_families": families,
        "baselines": _baseline_results(frame),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the pinned public EUR/USD engineering benchmark"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/public-eurusd-m1.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_benchmark(args.output)
    summary = {
        "output": str(args.output),
        "rows": report["dataset"]["rows"],
        "development_configurations_evaluated": report[
            "development_configurations_evaluated"
        ],
        "family_statuses": {
            name: values["status"]
            for name, values in report["strategy_families"].items()
        },
        "family_locked_evidence": {
            name: values["locked_test_evidence_pass"]
            for name, values in report["strategy_families"].items()
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
