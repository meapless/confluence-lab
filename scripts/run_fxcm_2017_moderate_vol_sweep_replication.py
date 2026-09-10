from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest
from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
from confluence_lab.fxcm import download_fxcm_year
from confluence_lab.hypotheses_v3 import V3B_SWEEP_PARAMS, moderate_vol_sweep_reversal
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.robustness import moving_block_bootstrap_expectancy
from confluence_lab.stress import payout_sensitivity, performance_by_direction, performance_by_period

YEAR = 2017
SYMBOL = "EURUSD"
PROTOCOL_VERSION = "v3b-2017-moderate-vol-sweep-1"
PRIMARY_PAYOUT = 0.82
PRIMARY_BREAK_EVEN = break_even_win_rate(PRIMARY_PAYOUT)
PRIMARY_CONFIG = BacktestConfig(
    expiry_bars=2,
    entry_offset_bars=1,
    fixed_payout=PRIMARY_PAYOUT,
    allow_overlapping_positions=True,
    cooldown_bars=0,
)
BLOCK_SIZES = (5, 10, 20)
BOOTSTRAP_SIMULATIONS = 5_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run preregistered V3B 2017 replication")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2017-v3b-moderate-vol-sweep.json"),
    )
    return parser


def _metric_dict(result) -> dict[str, object]:
    values = asdict(result.metrics)
    values["non_tie_trades"] = result.metrics.wins + result.metrics.losses
    values["hypothetical_break_even_win_rate"] = PRIMARY_BREAK_EVEN
    return values


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    downloaded = download_fxcm_year(SYMBOL, YEAR, price_side="mid", timeout=30.0)
    frame = downloaded.frame

    strategy = moderate_vol_sweep_reversal
    primary = run_backtest(frame, strategy, PRIMARY_CONFIG)
    primary_metrics = _metric_dict(primary)
    primary_pass = bool(
        primary_metrics["non_tie_trades"] >= 120
        and primary.metrics.expectancy is not None
        and primary.metrics.expectancy > 0
        and primary.metrics.wilson_low is not None
        and primary.metrics.wilson_low > PRIMARY_BREAK_EVEN
    )

    payout_table = payout_sensitivity(primary.trades, payouts=(0.80, 0.82, 0.90))
    payout_80 = payout_table.loc[payout_table["payout"].eq(0.80)].iloc[0]
    payout_robust_80 = bool(float(payout_80["expectancy"]) > 0)

    delayed = run_backtest(frame, strategy, replace(PRIMARY_CONFIG, entry_offset_bars=2))
    entry_delay_robust = bool(
        delayed.metrics.expectancy is not None and delayed.metrics.expectancy > 0
    )

    non_overlap = run_backtest(
        frame,
        strategy,
        replace(PRIMARY_CONFIG, allow_overlapping_positions=False, cooldown_bars=0),
    )
    non_overlap_robust = bool(
        non_overlap.metrics.expectancy is not None and non_overlap.metrics.expectancy > 0
    )

    block_bootstraps: dict[str, object] = {}
    block_all_pass = True
    if primary.trades.empty:
        block_all_pass = False
        for block_size in BLOCK_SIZES:
            block_bootstraps[str(block_size)] = {
                "pass": False,
                "reason": "no_primary_trades",
            }
    else:
        for block_size in BLOCK_SIZES:
            if len(primary.trades) < block_size:
                summary = None
                passed = False
            else:
                summary = moving_block_bootstrap_expectancy(
                    primary.trades,
                    block_size=block_size,
                    simulations=BOOTSTRAP_SIMULATIONS,
                    seed=4200 + block_size,
                )
                passed = summary.lower_bound_positive
            block_all_pass &= passed
            block_bootstraps[str(block_size)] = {
                "pass": passed,
                "summary": asdict(summary) if summary is not None else None,
            }

    if not primary_pass:
        classification = "rejected_primary"
    elif not (payout_robust_80 and entry_delay_robust and non_overlap_robust):
        classification = "replicated_but_fragile"
    elif not block_all_pass:
        classification = "replicated_but_dependence_sensitive"
    else:
        classification = "replicated_and_robust_regular_fx_candidate"

    monthly = performance_by_period(primary.trades, frequency="M")
    direction = performance_by_direction(primary.trades)

    report = {
        "study_kind": "fresh_year_fixed_candidate_replication",
        "protocol_version": PROTOCOL_VERSION,
        "preregistration": "research/hypotheses/v3b-moderate-vol-sweep-preregistration.md",
        "interpretation_warning": (
            "This is regular FXCM EUR/USD midpoint data, not Pocket Option/OTC data. "
            "The 82% payout is hypothetical. Passing would justify more research only; "
            "it would not imply guaranteed future returns."
        ),
        "source": {
            "provider": "FXCM public candle archive",
            "symbol": SYMBOL,
            "year": YEAR,
            "price_side": downloaded.price_side,
            "weekly_files_downloaded": len(downloaded.files),
            "missing_weeks": list(downloaded.missing_weeks),
            "files": [asdict(item) for item in downloaded.files],
        },
        "dataset": {
            "rows": len(frame),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnose_dataset(frame)),
        },
        "frozen_strategy": {
            "family": "moderate_vol_sweep_reversal",
            "params": asdict(V3B_SWEEP_PARAMS),
            "atr_percentile_rule": "> 0.25 and <= 0.50",
            "direction": "BOTH",
            "execution": asdict(PRIMARY_CONFIG),
        },
        "primary_pass_rule": {
            "minimum_non_tie_trades": 120,
            "minimum_expectancy_exclusive": 0.0,
            "minimum_wilson_low_exclusive": PRIMARY_BREAK_EVEN,
        },
        "primary_metrics": primary_metrics,
        "primary_replication_pass": primary_pass,
        "robustness": {
            "payout_80": {
                "pass": payout_robust_80,
                "metrics": payout_80.astype(object).where(pd.notna(payout_80), None).to_dict(),
            },
            "entry_offset_2": {
                "pass": entry_delay_robust,
                "metrics": _metric_dict(delayed),
            },
            "non_overlapping": {
                "pass": non_overlap_robust,
                "metrics": _metric_dict(non_overlap),
            },
            "moving_block_bootstrap": block_bootstraps,
            "moving_block_all_pass": block_all_pass,
            "monthly": _records(monthly),
            "direction": _records(direction),
        },
        "classification": classification,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print("rows:", len(frame))
    print("primary_trades:", primary.metrics.trades)
    print("primary_win_rate:", primary.metrics.win_rate)
    print("primary_wilson_low:", primary.metrics.wilson_low)
    print("primary_expectancy:", primary.metrics.expectancy)
    print("primary_pass:", primary_pass)
    print("payout_80_robust:", payout_robust_80)
    print("entry_delay_robust:", entry_delay_robust)
    print("non_overlap_robust:", non_overlap_robust)
    print("moving_block_all_pass:", block_all_pass)
    print("classification:", classification)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
