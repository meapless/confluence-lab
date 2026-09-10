from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest
from confluence_lab.context import add_research_context
from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
from confluence_lab.diagnostics import (
    add_fixed_volatility_bucket,
    enrich_trades_with_signal_context,
    performance_breakdown,
)
from confluence_lab.fxcm import download_fxcm_year
from confluence_lab.hypotheses_v2 import SweepReversalParams, sweep_reversal
from confluence_lab.splits import chronological_split
from confluence_lab.stress import performance_by_period

YEAR = 2018
SYMBOL = "EURUSD"
PAYOUT = 0.82
ANALYSIS_VERSION = "2018-sweep-posthoc-v1"
PARAMS = SweepReversalParams(
    lookback=20,
    wick_min=0.65,
    rsi_edge=65.0,
    overshoot_atr=0.0,
    liquid_core_only=False,
)
CONFIG = BacktestConfig(expiry_bars=2, entry_offset_bars=1, fixed_payout=PAYOUT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Post-hoc diagnostics for the failed 2018 V2 sweep-reversal candidate"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2018-sweep-posthoc.json"),
    )
    return parser


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    clean = frame.astype(object).where(pd.notna(frame), None)
    return clean.to_dict(orient="records")


def _analyze_slice(frame: pd.DataFrame) -> dict[str, object]:
    result = run_backtest(frame, lambda data: sweep_reversal(data, PARAMS), CONFIG)
    context = add_research_context(frame)
    enriched = enrich_trades_with_signal_context(result.trades, context)
    enriched = add_fixed_volatility_bucket(enriched)
    enriched["direction_label"] = enriched["direction"].map({1: "call", -1: "put"})

    return {
        "primary_metrics": asdict(result.metrics),
        "by_direction": _records(performance_breakdown(enriched, "direction_label", min_trades=20)),
        "by_utc_window": _records(performance_breakdown(enriched, "utc_window", min_trades=20)),
        "by_direction_and_utc_window": _records(
            performance_breakdown(
                enriched,
                ["direction_label", "utc_window"],
                min_trades=20,
            )
        ),
        "by_htf_15_trend": _records(
            performance_breakdown(enriched, "htf_15_trend", min_trades=20)
        ),
        "by_volatility_bucket": _records(
            performance_breakdown(enriched, "volatility_bucket", min_trades=20)
        ),
        "by_month": _records(performance_by_period(result.trades, frequency="M")),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    downloaded = download_fxcm_year(SYMBOL, YEAR, price_side="mid", timeout=30.0)
    frame = downloaded.frame
    split = chronological_split(frame)

    report = {
        "study_kind": "posthoc_exploratory_diagnostics_on_failed_locked_candidate",
        "analysis_version": ANALYSIS_VERSION,
        "confirmatory_status": "NOT_EVIDENCE",
        "warning": (
            "This report inspects a candidate after its locked test failed. Any subgroup "
            "pattern is hypothesis-generating only and must be preregistered and tested "
            "on a different untouched year before it can count as evidence."
        ),
        "source": {
            "provider": "FXCM public candle archive",
            "symbol": SYMBOL,
            "year": YEAR,
            "weekly_files_downloaded": len(downloaded.files),
            "missing_weeks": list(downloaded.missing_weeks),
            "files": [asdict(item) for item in downloaded.files],
        },
        "dataset": {
            "rows": len(frame),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnose_dataset(frame)),
        },
        "fixed_candidate": {
            "family": "sweep_reversal",
            "params": asdict(PARAMS),
            "execution": {
                "expiry_bars": CONFIG.expiry_bars,
                "entry_offset_bars": CONFIG.entry_offset_bars,
                "fixed_payout": CONFIG.fixed_payout,
            },
        },
        "development": _analyze_slice(split.development),
        "validation": _analyze_slice(split.validation),
        "locked_test": _analyze_slice(split.test),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    print("rows:", len(frame))
    for name in ("development", "validation", "locked_test"):
        metrics = report[name]["primary_metrics"]
        print(name, "trades=", metrics["trades"], "win_rate=", metrics["win_rate"], "expectancy=", metrics["expectancy"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
