from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
from confluence_lab.experiments import ValidationGate
from confluence_lab.families import FAMILIES
from confluence_lab.fxcm import download_fxcm_year
from confluence_lab.matrix import ExecutionVariant, run_matrix_experiment
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.public_benchmark import PublicBenchmarkPolicy, baseline_results, metric_payload

YEAR = 2019
SYMBOL = "EURUSD"
HYPOTHETICAL_PAYOUT = 0.82
EXPIRIES = (1, 2, 3, 5)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a long-history FXCM EUR/USD M1 research benchmark"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2019.json"),
    )
    parser.add_argument(
        "--families",
        nargs="+",
        choices=sorted(FAMILIES),
        default=None,
        help="Optional subset of strategy families to evaluate.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    downloaded = download_fxcm_year(SYMBOL, YEAR, price_side="mid", timeout=30.0)
    frame = downloaded.frame
    diagnostics = diagnose_dataset(frame)
    threshold = break_even_win_rate(HYPOTHETICAL_PAYOUT)

    gate = ValidationGate(
        min_trades=100,
        min_expectancy=0.0,
        min_locked_test_trades=100,
        min_wilson_low=threshold,
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

    selected_names = args.families or list(FAMILIES)
    families: dict[str, object] = {}
    total_evaluations = 0
    for name in selected_names:
        family = FAMILIES[name]
        result = run_matrix_experiment(
            frame,
            family.builder,
            family.parameter_grid,
            variants,
            objective="wilson_low",
            search_min_trades=200,
            search_min_expectancy=0.0,
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
                    payout=HYPOTHETICAL_PAYOUT,
                ),
            }
        locked = metric_payload(result.test_metrics, payout=HYPOTHETICAL_PAYOUT)
        families[name] = {
            "description": family.description,
            "intended_regimes": list(family.intended_regimes),
            "development_configurations_evaluated": evaluations,
            "status": result.status,
            "best_development": best,
            "validation": metric_payload(
                result.validation_metrics,
                payout=HYPOTHETICAL_PAYOUT,
            ),
            "locked_test": locked,
            "locked_test_evidence_pass": bool(
                result.status == "tested"
                and locked is not None
                and locked["positive_expectancy"]
                and locked["wilson_lower_above_break_even"]
            ),
        }

    policy = PublicBenchmarkPolicy(
        fixed_payout=HYPOTHETICAL_PAYOUT,
        expiries=EXPIRIES,
        min_development_trades=200,
        min_development_expectancy=0.0,
        min_validation_trades=100,
        min_locked_test_trades=100,
        require_validation_wilson_above_break_even=True,
    )

    report = {
        "benchmark_kind": "official_fxcm_regular_fx_long_history_benchmark",
        "interpretation_warning": (
            "This is regular FXCM EUR/USD midpoint research data, NOT Pocket Option "
            "or OTC data. The 82% payout is hypothetical and exists only to evaluate "
            "binary-style expectancy. Do not market these results as Pocket performance."
        ),
        "source": {
            "provider": "FXCM public candle archive",
            "provider_repository": "fxcm/MarketData",
            "symbol": SYMBOL,
            "year": YEAR,
            "price_side": downloaded.price_side,
            "weekly_files_downloaded": len(downloaded.files),
            "missing_weeks": list(downloaded.missing_weeks),
            "files": [asdict(item) for item in downloaded.files],
            "timestamp_interpretation": "UTC (FXCM documentation)",
            "price_construction": (
                "OHLC midpoint of corresponding FXCM bid and ask OHLC fields; "
                "open/close spread proxies retained in normalized source frame"
            ),
        },
        "dataset": {
            "rows": len(frame),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnostics),
            "timeframe": "1 minute",
        },
        "economics": {
            "payout_source": "hypothetical_fixed_assumption",
            "fixed_payout": HYPOTHETICAL_PAYOUT,
            "break_even_win_rate": threshold,
        },
        "research_policy": {
            "development_fraction": 0.60,
            "validation_fraction": 0.20,
            "locked_test_fraction": 0.20,
            "search_objective": "wilson_low",
            "minimum_development_trades": 200,
            "minimum_development_expectancy": 0.0,
            "minimum_validation_trades": gate.min_trades,
            "minimum_locked_test_trades": gate.min_locked_test_trades,
            "validation_requires_positive_expectancy": True,
            "validation_min_wilson_low": gate.min_wilson_low,
            "locked_evidence_requires_positive_expectancy": True,
            "locked_evidence_requires_wilson_lower_above_break_even": True,
            "parameters_fixed_before_validation": True,
            "selected_families": selected_names,
        },
        "development_configurations_evaluated": total_evaluations,
        "strategy_families": families,
        "baselines": baseline_results(frame, policy),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print("rows:", len(frame))
    print("downloaded_weeks:", len(downloaded.files))
    print("missing_weeks:", list(downloaded.missing_weeks))
    print("evaluations:", total_evaluations)
    for name, values in families.items():
        validation = values.get("validation") or {}
        locked = values.get("locked_test") or {}
        print(
            name,
            "status=", values["status"],
            "dev_win_rate=", (values.get("best_development") or {}).get("metrics", {}).get("win_rate"),
            "dev_expectancy=", (values.get("best_development") or {}).get("metrics", {}).get("expectancy"),
            "validation_win_rate=", validation.get("win_rate"),
            "validation_wilson_low=", validation.get("wilson_low"),
            "locked_win_rate=", locked.get("win_rate"),
            "locked_expectancy=", locked.get("expectancy"),
            "evidence_pass=", values["locked_test_evidence_pass"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
