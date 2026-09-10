from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest
from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
from confluence_lab.fxcm import download_fxcm_year
from confluence_lab.hypotheses import RangeReversionParams, range_reversion
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.public_benchmark import metric_payload
from confluence_lab.robustness import bootstrap_expectancy
from confluence_lab.stress import performance_by_period

YEAR = 2017
SYMBOL = "EURUSD"
PAYOUT = 0.82
FROZEN_PARAMS = RangeReversionParams(
    adx_max=30.0,
    rsi_lower=25.0,
    rsi_upper=65.0,
    band_buffer_atr=0.10,
    atr_pct_max=0.70,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replicate the preregistered CALL-only range hypothesis on FXCM 2017"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2017-call-range-replication.json"),
    )
    return parser


def _strategy(frame: pd.DataFrame) -> pd.Series:
    raw = range_reversion(frame, FROZEN_PARAMS)
    return raw.where(raw.eq(1), 0).astype("int8")


def _run(frame, *, payout=PAYOUT, entry_offset=1, overlap=True, cooldown=0):
    return run_backtest(
        frame,
        _strategy,
        BacktestConfig(
            expiry_bars=5,
            entry_offset_bars=entry_offset,
            fixed_payout=payout,
            stake=1.0,
            allow_overlapping_positions=overlap,
            cooldown_bars=cooldown,
        ),
    )


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return json.loads(frame.to_json(orient="records")) if not frame.empty else []


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    downloaded = download_fxcm_year(SYMBOL, YEAR, price_side="mid", timeout=30.0)
    frame = downloaded.frame
    diagnostics = diagnose_dataset(frame)
    threshold = break_even_win_rate(PAYOUT)

    primary = _run(frame)
    primary_payload = metric_payload(primary.metrics, payout=PAYOUT)
    primary_pass = bool(
        primary.metrics.trades >= 300
        and primary.metrics.expectancy is not None
        and primary.metrics.expectancy > 0
        and primary.metrics.wilson_low is not None
        and primary.metrics.wilson_low > threshold
    )

    overlap_stress = {}
    for cooldown in (0, 1, 2):
        result = _run(frame, overlap=False, cooldown=cooldown)
        overlap_stress[f"non_overlapping_cooldown_{cooldown}"] = metric_payload(
            result.metrics, payout=PAYOUT
        )

    delay_stress = {}
    for entry_offset in (1, 2, 3):
        result = _run(frame, entry_offset=entry_offset)
        delay_stress[f"entry_offset_{entry_offset}"] = metric_payload(
            result.metrics, payout=PAYOUT
        )

    payout_stress = {}
    for payout in (0.70, 0.80, 0.82, 0.90):
        result = _run(frame, payout=payout)
        payout_stress[f"payout_{int(round(payout * 100))}"] = metric_payload(
            result.metrics, payout=payout
        )

    bootstrap = asdict(bootstrap_expectancy(primary.trades, simulations=10_000, seed=2017))
    monthly = _records(performance_by_period(primary.trades, frequency="M"))

    report = {
        "study_kind": "preregistered_direction_specific_replication",
        "preregistration": "research/hypotheses/v3-call-range-preregistration.md",
        "interpretation_warning": (
            "Regular FXCM EUR/USD data only; not Pocket Option or OTC data. "
            "The 82% payout is hypothetical. This study is not a forecast or guarantee."
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
        },
        "dataset": {
            "rows": len(frame),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnostics),
        },
        "configuration": {
            "family": "range_reversion_call_only",
            "params": asdict(FROZEN_PARAMS),
            "direction_filter": "CALL_ONLY",
            "expiry_bars": 5,
            "entry_offset_bars": 1,
            "fixed_payout": PAYOUT,
            "break_even_win_rate": threshold,
            "allow_overlapping_positions": True,
            "tie_policy": "refund",
        },
        "primary_pass_rule": {
            "minimum_trades": 300,
            "minimum_expectancy_exclusive": 0.0,
            "minimum_wilson_low_exclusive": threshold,
        },
        "primary_metrics": primary_payload,
        "primary_replication_pass": primary_pass,
        "secondary_diagnostics": {
            "overlap_and_cooldown": overlap_stress,
            "entry_delay": delay_stress,
            "payout_sensitivity": payout_stress,
            "expectancy_bootstrap": bootstrap,
            "monthly_performance": monthly,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print("rows:", len(frame))
    print("missing_weeks:", list(downloaded.missing_weeks))
    print("trades:", primary.metrics.trades)
    print("win_rate:", primary.metrics.win_rate)
    print("wilson_low:", primary.metrics.wilson_low)
    print("expectancy:", primary.metrics.expectancy)
    print("bootstrap_p025:", bootstrap["expectancy_p025"])
    print("replication_pass:", primary_pass)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
