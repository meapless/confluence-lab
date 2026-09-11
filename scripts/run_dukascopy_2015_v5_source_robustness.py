from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
from confluence_lab.dukascopy_stream import download_candles_streaming
from confluence_lab.fxcm import download_fxcm_year
from confluence_lab.ml import ML_FEATURE_COLUMNS
from confluence_lab.ml_experiment import evidence_gate
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.robustness import bootstrap_expectancy, moving_block_bootstrap_expectancy
from confluence_lab.stress import payout_sensitivity, performance_by_direction, performance_by_period
from confluence_lab.v5_replication import (
    ENTRY_OFFSET_BARS,
    EXPECTED_TRAIN_FINGERPRINT,
    EXPIRY_BARS,
    FIXED_PAYOUT,
    MINIMUM_REPLICATION_RESOLVED_TRADES,
    PROBABILITY_THRESHOLD,
    SYMBOL,
    TRAIN_YEAR,
    evaluate_frozen_v5,
    fit_frozen_v5,
)

SOURCE_YEAR = 2015
PROTOCOL_VERSION = "v5-dukascopy-2015-source-robustness-2"
SOURCE_MAX_WORKERS = 4
SOURCE_BATCH_HOURS = 24
SOURCE_BATCH_PAUSE_SECONDS = 0.25


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run preregistered frozen V5 quote-source robustness on Dukascopy 2015"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/dukascopy-eurusd-m1-2015-v5-source-robustness.json"),
    )
    return parser


def _metric_payload(result):
    metrics = result.metrics
    values = asdict(metrics)
    values["non_tie_trades"] = metrics.wins + metrics.losses
    values["hypothetical_break_even_win_rate"] = break_even_win_rate(FIXED_PAYOUT)
    values["positive_expectancy"] = metrics.expectancy is not None and metrics.expectancy > 0
    values["wilson_lower_above_break_even"] = (
        metrics.wilson_low is not None
        and metrics.wilson_low > break_even_win_rate(FIXED_PAYOUT)
    )
    return values


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def _primary_pass(result) -> bool:
    return evidence_gate(
        result,
        minimum_resolved_trades=MINIMUM_REPLICATION_RESOLVED_TRADES,
        fixed_payout=FIXED_PAYOUT,
    )


def _post_pass_robustness(source_frame, fit, primary):
    payout_table = payout_sensitivity(primary.trades, payouts=(0.80, 0.82, 0.90))
    payout_80 = payout_table.loc[payout_table["payout"].eq(0.80)].iloc[0]
    payout_80_pass = bool(float(payout_80["expectancy"]) > 0.0)

    delayed = evaluate_frozen_v5(fit, source_frame, entry_offset_bars=2)
    delayed_pass = evidence_gate(
        delayed,
        minimum_resolved_trades=MINIMUM_REPLICATION_RESOLVED_TRADES,
        fixed_payout=FIXED_PAYOUT,
    )

    non_overlap = evaluate_frozen_v5(
        fit,
        source_frame,
        allow_overlapping_positions=False,
        cooldown_bars=0,
    )
    non_overlap_pass = evidence_gate(
        non_overlap,
        minimum_resolved_trades=MINIMUM_REPLICATION_RESOLVED_TRADES,
        fixed_payout=FIXED_PAYOUT,
    )

    ordinary = bootstrap_expectancy(primary.trades, simulations=5_000, seed=5516)
    blocks = {}
    block_pass = True
    for block_size in (5, 10, 20):
        summary = moving_block_bootstrap_expectancy(
            primary.trades,
            block_size=block_size,
            simulations=5_000,
            seed=5516 + block_size,
        )
        passed = bool(summary.expectancy_p025 > 0.0)
        block_pass &= passed
        blocks[str(block_size)] = {**asdict(summary), "pass": passed}

    requirements = {
        "payout_80_positive_expectancy": payout_80_pass,
        "entry_offset_2_evidence_gate": delayed_pass,
        "non_overlapping_evidence_gate": non_overlap_pass,
        "all_moving_block_lower_bounds_positive": block_pass,
    }
    return {
        "requirements": requirements,
        "all_requirements_pass": all(requirements.values()),
        "payout_sensitivity": _records(payout_table),
        "entry_offset_2": _metric_payload(delayed),
        "non_overlapping": _metric_payload(non_overlap),
        "ordinary_bootstrap_expectancy": asdict(ordinary),
        "moving_block_bootstrap_expectancy": blocks,
        "by_direction": _records(performance_by_direction(primary.trades)),
        "by_month": _records(performance_by_period(primary.trades, frequency="M")),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    training = download_fxcm_year(SYMBOL, TRAIN_YEAR, price_side="mid", timeout=30.0)
    observed_training_fingerprint = dataframe_fingerprint(training.frame)
    if observed_training_fingerprint != EXPECTED_TRAIN_FINGERPRINT:
        raise SystemExit(
            "ABORTING BEFORE DUKASCOPY 2015 ACCESS: FXCM 2014 fingerprint mismatch. "
            f"expected={EXPECTED_TRAIN_FINGERPRINT} observed={observed_training_fingerprint}"
        )
    fit = fit_frozen_v5(training.frame)

    source = download_candles_streaming(
        SYMBOL,
        datetime(SOURCE_YEAR, 1, 1, tzinfo=timezone.utc),
        datetime(SOURCE_YEAR + 1, 1, 1, tzinfo=timezone.utc),
        timeframe="1min",
        price="mid",
        timeout=30.0,
        max_workers=SOURCE_MAX_WORKERS,
        batch_hours=SOURCE_BATCH_HOURS,
        pause_between_batches_seconds=SOURCE_BATCH_PAUSE_SECONDS,
    )
    primary = evaluate_frozen_v5(fit, source.frame)
    primary_pass = _primary_pass(primary)

    robustness = None
    if primary_pass:
        robustness = _post_pass_robustness(source.frame, fit, primary)
        classification = (
            "source_robustness_passed_and_robust"
            if robustness["all_requirements_pass"]
            else "source_robustness_passed_but_fragile"
        )
    else:
        classification = "source_robustness_failed"

    model_params = fit.model.get_params()
    source_dates = {item.hour[:10] for item in source.sources}
    report = {
        "study_kind": "preregistered_quote_source_robustness",
        "protocol_version": PROTOCOL_VERSION,
        "preregistration": "research/hypotheses/v5-dukascopy-2015-source-robustness-preregistration.md",
        "protocol_amendment": "research/hypotheses/v5-dukascopy-2015-source-robustness-protocol-amendment-1.md",
        "parent_replication": "research/results/fxcm-2015-v5-replication.md",
        "prior_execution_failures": [
            "research/results/dukascopy-2015-v5-source-robustness-attempt1-execution-failure.md",
            "research/results/dukascopy-2015-v5-source-robustness-attempt2-execution-failure.md",
            "research/results/dukascopy-2015-v5-source-robustness-attempt3-execution-failure.md",
        ],
        "interpretation_warning": (
            "2015 has already been seen on FXCM. This is quote-source robustness, not "
            "a second fresh temporal replication. The fixed payout is hypothetical and "
            "this is not Pocket Option/OTC evidence."
        ),
        "training_source": {
            "provider": "FXCM public candle archive",
            "symbol": SYMBOL,
            "year": TRAIN_YEAR,
            "rows": len(training.frame),
            "expected_fingerprint": EXPECTED_TRAIN_FINGERPRINT,
            "observed_fingerprint": observed_training_fingerprint,
            "fingerprint_verified": True,
            "labeled_training_rows": fit.labeled_training_rows,
            "files": [asdict(item) for item in training.files],
        },
        "evaluation_source": {
            "provider": "Dukascopy historical BI5 raw tick feed",
            "symbol": SYMBOL,
            "year": SOURCE_YEAR,
            "construction": (
                "canonical hourly raw bid/ask BI5 objects; per-tick midpoint; "
                "UTC 1-minute OHLC; object-by-object decode/resample"
            ),
            "transport": {
                "max_workers": SOURCE_MAX_WORKERS,
                "batch_hours": SOURCE_BATCH_HOURS,
                "pause_between_batches_seconds": SOURCE_BATCH_PAUSE_SECONDS,
            },
            "rows": len(source.frame),
            "fingerprint": dataframe_fingerprint(source.frame),
            "diagnostics": asdict(diagnose_dataset(source.frame)),
            "calendar_days_represented_in_source_manifest": len(source_dates),
            "source_objects": len(source.sources),
            "downloaded_objects": sum(item.status == "downloaded" for item in source.sources),
            "missing_404_objects": sum(item.status == "missing_404" for item in source.sources),
            "sources": [asdict(item) for item in source.sources],
        },
        "frozen_candidate": {
            "model": "HistGradientBoostingClassifier",
            "model_params": {
                key: model_params[key]
                for key in (
                    "learning_rate",
                    "max_iter",
                    "max_leaf_nodes",
                    "max_depth",
                    "min_samples_leaf",
                    "l2_regularization",
                    "early_stopping",
                    "random_state",
                )
            },
            "feature_columns": list(ML_FEATURE_COLUMNS),
            "expiry_bars": EXPIRY_BARS,
            "entry_offset_bars": ENTRY_OFFSET_BARS,
            "probability_threshold": PROBABILITY_THRESHOLD,
            "fixed_payout": FIXED_PAYOUT,
            "allow_overlapping_positions": True,
            "cooldown_bars": 0,
            "gap_safe_targets_and_settlement": True,
            "search_on_dukascopy_2015": False,
        },
        "primary_gate": {
            "minimum_resolved_trades": MINIMUM_REPLICATION_RESOLVED_TRADES,
            "minimum_expectancy_exclusive": 0.0,
            "minimum_wilson_low_exclusive": break_even_win_rate(FIXED_PAYOUT),
        },
        "primary_source_test": _metric_payload(primary),
        "primary_source_test_pass": primary_pass,
        "robustness": robustness,
        "classification": classification,
        "no_rescue_policy": (
            "No Dukascopy 2015 subgroup or alternative threshold may alter this classification."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str, allow_nan=False), encoding="utf-8")

    print("fxcm_2014_fingerprint_verified:", True)
    print("dukascopy_2015_rows:", len(source.frame))
    print("dukascopy_2015_fingerprint:", report["evaluation_source"]["fingerprint"])
    print("source_objects:", report["evaluation_source"]["source_objects"])
    print("downloaded_objects:", report["evaluation_source"]["downloaded_objects"])
    print("missing_404_objects:", report["evaluation_source"]["missing_404_objects"])
    print("primary_source_test:", report["primary_source_test"])
    print("primary_source_test_pass:", primary_pass)
    print("robustness_calculated:", robustness is not None)
    if robustness is not None:
        print("robustness_requirements:", robustness["requirements"])
        print("robustness_all_requirements_pass:", robustness["all_requirements_pass"])
        print("entry_offset_2:", robustness["entry_offset_2"])
        print("non_overlapping:", robustness["non_overlapping"])
        print("moving_block_bootstrap_expectancy:", robustness["moving_block_bootstrap_expectancy"])
    print("classification:", classification)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
