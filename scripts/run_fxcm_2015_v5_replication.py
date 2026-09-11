from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
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
    REPLICATION_YEAR,
    SYMBOL,
    TRAIN_YEAR,
    evaluate_frozen_v5,
    fit_frozen_v5,
    primary_replication_pass,
)

PROTOCOL_VERSION = "v5-2015-frozen-replication-1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the preregistered one-shot V5 2015 independent replication"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2015-v5-replication.json"),
    )
    return parser


def _metric_payload(result):
    if result is None:
        return None
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


def _post_pass_robustness(replication_frame, fit, primary):
    """Run only the robustness checks preregistered for a primary pass."""
    payout_table = payout_sensitivity(primary.trades, payouts=(0.80, 0.82, 0.90))
    payout_80 = payout_table.loc[payout_table["payout"].eq(0.80)].iloc[0]
    payout_80_pass = bool(float(payout_80["expectancy"]) > 0.0)

    delayed = evaluate_frozen_v5(
        fit,
        replication_frame,
        entry_offset_bars=2,
    )
    delayed_pass = evidence_gate(
        delayed,
        minimum_resolved_trades=MINIMUM_REPLICATION_RESOLVED_TRADES,
        fixed_payout=FIXED_PAYOUT,
    )

    non_overlap = evaluate_frozen_v5(
        fit,
        replication_frame,
        allow_overlapping_positions=False,
        cooldown_bars=0,
    )
    non_overlap_pass = evidence_gate(
        non_overlap,
        minimum_resolved_trades=MINIMUM_REPLICATION_RESOLVED_TRADES,
        fixed_payout=FIXED_PAYOUT,
    )

    ordinary = bootstrap_expectancy(primary.trades, simulations=5_000, seed=5515)
    block_results: dict[str, object] = {}
    all_blocks_pass = True
    for block_size in (5, 10, 20):
        summary = moving_block_bootstrap_expectancy(
            primary.trades,
            block_size=block_size,
            simulations=5_000,
            seed=5515 + block_size,
        )
        passed = bool(summary.expectancy_p025 > 0.0)
        all_blocks_pass &= passed
        block_results[str(block_size)] = {
            **asdict(summary),
            "pass": passed,
        }

    requirements = {
        "payout_80_positive_expectancy": payout_80_pass,
        "entry_offset_2_evidence_gate": delayed_pass,
        "non_overlapping_evidence_gate": non_overlap_pass,
        "all_moving_block_lower_bounds_positive": all_blocks_pass,
    }
    all_requirements_pass = all(requirements.values())

    return {
        "requirements": requirements,
        "all_requirements_pass": all_requirements_pass,
        "payout_sensitivity": _records(payout_table),
        "entry_offset_2": _metric_payload(delayed),
        "non_overlapping": _metric_payload(non_overlap),
        "ordinary_bootstrap_expectancy": asdict(ordinary),
        "moving_block_bootstrap_expectancy": block_results,
        "by_direction": _records(performance_by_direction(primary.trades)),
        "by_month": _records(performance_by_period(primary.trades, frequency="M")),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Provenance firewall: 2015 must not be downloaded until the exact 2014
    # source history used by the preregistration is confirmed and the model is fit.
    training_download = download_fxcm_year(SYMBOL, TRAIN_YEAR, price_side="mid", timeout=30.0)
    training_frame = training_download.frame
    observed_training_fingerprint = dataframe_fingerprint(training_frame)
    if observed_training_fingerprint != EXPECTED_TRAIN_FINGERPRINT:
        raise SystemExit(
            "ABORTING BEFORE 2015 ACCESS: 2014 fingerprint mismatch. "
            f"expected={EXPECTED_TRAIN_FINGERPRINT} observed={observed_training_fingerprint}"
        )
    fit = fit_frozen_v5(training_frame)

    # Only now is the preregistered independent year consumed.
    replication_download = download_fxcm_year(
        SYMBOL,
        REPLICATION_YEAR,
        price_side="mid",
        timeout=30.0,
    )
    replication_frame = replication_download.frame
    primary = evaluate_frozen_v5(fit, replication_frame)
    primary_pass = primary_replication_pass(primary)

    robustness = None
    if primary_pass:
        robustness = _post_pass_robustness(replication_frame, fit, primary)
        classification = (
            "replicated_and_robust_regular_fx_candidate"
            if robustness["all_requirements_pass"]
            else "replicated_primary_but_fragile"
        )
    else:
        classification = "rejected_replication"

    frozen_params = fit.model.get_params()
    report = {
        "study_kind": "preregistered_frozen_independent_replication",
        "protocol_version": PROTOCOL_VERSION,
        "preregistration": "research/hypotheses/v5-2015-replication-preregistration.md",
        "parent_result": "research/results/fxcm-2014-v5-histgb.md",
        "interpretation_warning": (
            "This is regular FXCM EUR/USD midpoint evidence under a hypothetical 82% "
            "binary-style payout. It is not Pocket Option/OTC evidence and does not "
            "guarantee future profitability or a fixed win rate."
        ),
        "training_source": {
            "provider": "FXCM public candle archive",
            "symbol": SYMBOL,
            "year": TRAIN_YEAR,
            "price_side": training_download.price_side,
            "expected_fingerprint": EXPECTED_TRAIN_FINGERPRINT,
            "observed_fingerprint": observed_training_fingerprint,
            "fingerprint_verified": True,
            "rows": len(training_frame),
            "labeled_training_rows": fit.labeled_training_rows,
            "class_zero_rows": fit.class_zero_rows,
            "class_one_rows": fit.class_one_rows,
            "weekly_files_downloaded": len(training_download.files),
            "missing_weeks": list(training_download.missing_weeks),
            "files": [asdict(item) for item in training_download.files],
        },
        "replication_source": {
            "provider": "FXCM public candle archive",
            "symbol": SYMBOL,
            "year": REPLICATION_YEAR,
            "price_side": replication_download.price_side,
            "rows": len(replication_frame),
            "fingerprint": dataframe_fingerprint(replication_frame),
            "diagnostics": asdict(diagnose_dataset(replication_frame)),
            "weekly_files_downloaded": len(replication_download.files),
            "missing_weeks": list(replication_download.missing_weeks),
            "files": [asdict(item) for item in replication_download.files],
        },
        "frozen_candidate": {
            "model": "HistGradientBoostingClassifier",
            "model_params": {
                "learning_rate": frozen_params["learning_rate"],
                "max_iter": frozen_params["max_iter"],
                "max_leaf_nodes": frozen_params["max_leaf_nodes"],
                "max_depth": frozen_params["max_depth"],
                "min_samples_leaf": frozen_params["min_samples_leaf"],
                "l2_regularization": frozen_params["l2_regularization"],
                "early_stopping": frozen_params["early_stopping"],
                "random_state": frozen_params["random_state"],
            },
            "feature_columns": list(ML_FEATURE_COLUMNS),
            "expiry_bars": EXPIRY_BARS,
            "entry_offset_bars": ENTRY_OFFSET_BARS,
            "probability_threshold": PROBABILITY_THRESHOLD,
            "fixed_payout": FIXED_PAYOUT,
            "allow_overlapping_positions": True,
            "cooldown_bars": 0,
            "gap_safe_targets_and_settlement": True,
            "hyperparameter_search_on_2015": False,
            "threshold_search_on_2015": False,
        },
        "primary_gate": {
            "minimum_resolved_trades": MINIMUM_REPLICATION_RESOLVED_TRADES,
            "minimum_expectancy_exclusive": 0.0,
            "minimum_wilson_low_exclusive": break_even_win_rate(FIXED_PAYOUT),
        },
        "primary_replication": _metric_payload(primary),
        "primary_replication_pass": primary_pass,
        "robustness": robustness,
        "classification": classification,
        "replication_year_consumed": True,
        "no_rescue_policy": (
            "No 2015 direction, month, session, volatility, confidence or other subgroup "
            "may alter this classification. Any changed hypothesis requires new data."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print("2014_fingerprint_verified:", True)
    print("2014_labeled_training_rows:", fit.labeled_training_rows)
    print("2015_rows:", len(replication_frame))
    print("2015_fingerprint:", report["replication_source"]["fingerprint"])
    print("primary_replication:", report["primary_replication"])
    print("primary_replication_pass:", primary_pass)
    print("robustness_calculated:", robustness is not None)
    print("classification:", classification)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
