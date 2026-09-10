from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from confluence_lab.data import dataframe_fingerprint, diagnose_dataset
from confluence_lab.fxcm import download_fxcm_year
from confluence_lab.ml import DEFAULT_PROBABILITY_THRESHOLDS, ML_FEATURE_COLUMNS
from confluence_lab.ml_experiment import evaluate_model_slice
from confluence_lab.ml_v5 import make_histgb_classifier
from confluence_lab.ml_v5_experiment import run_histgb_experiment
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.robustness import bootstrap_expectancy, moving_block_bootstrap_expectancy
from confluence_lab.splits import chronological_split
from confluence_lab.stress import payout_sensitivity, performance_by_direction, performance_by_period

YEAR = 2014
SYMBOL = "EURUSD"
PROTOCOL_VERSION = "v5-2014-histgb-1"
PAYOUT = 0.82
EXPIRIES = (1, 2, 3, 5)
THRESHOLDS = DEFAULT_PROBABILITY_THRESHOLDS
DEVELOPMENT_OOF_SPLITS = 5
MIN_DEVELOPMENT_TRADES = 300
MIN_VALIDATION_RESOLVED = 150
MIN_LOCKED_RESOLVED = 150


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run preregistered V5 HistGradientBoosting benchmark")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2014-v5-histgb.json"),
    )
    return parser


def _metric_payload(result):
    if result is None:
        return None
    metrics = result.metrics
    values = asdict(metrics)
    values["non_tie_trades"] = metrics.wins + metrics.losses
    values["hypothetical_break_even_win_rate"] = break_even_win_rate(PAYOUT)
    values["positive_expectancy"] = metrics.expectancy is not None and metrics.expectancy > 0
    values["wilson_lower_above_break_even"] = (
        metrics.wilson_low is not None and metrics.wilson_low > break_even_win_rate(PAYOUT)
    )
    return values


def _finite_score(value: float):
    return float(value) if math.isfinite(value) else None


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def _development_search_payload(experiment) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for search in experiment.development_searches:
        selected = search.research.selected_threshold
        for threshold_result in search.research.development_threshold_results:
            metrics = threshold_result.metrics
            rows.append(
                {
                    "expiry_bars": search.expiry_bars,
                    "threshold": threshold_result.threshold,
                    "selected_within_expiry": selected == threshold_result.threshold,
                    "eligible": math.isfinite(threshold_result.score),
                    "score_wilson_low": _finite_score(threshold_result.score),
                    "metrics": {
                        **asdict(metrics),
                        "non_tie_trades": metrics.wins + metrics.losses,
                    },
                }
            )
    return rows


def _locked_robustness(frame: pd.DataFrame, experiment):
    # Preregistered V5 rule: robustness diagnostics are permitted only after the
    # candidate has passed the primary locked-test evidence gate. A failed locked
    # test is recorded as the decision and is not mined for additional subgroups.
    if experiment.status != "passed_locked":
        return None
    if experiment.candidate is None or experiment.locked_test is None:
        raise RuntimeError("passed_locked result is missing its candidate or locked test")

    candidate = experiment.candidate
    primary = experiment.locked_test

    payout_table = payout_sensitivity(primary.trades, payouts=(0.80, 0.82, 0.90))
    delayed = evaluate_model_slice(
        candidate.research.model,
        frame,
        threshold=candidate.threshold,
        expiry_bars=candidate.expiry_bars,
        fixed_payout=PAYOUT,
        entry_offset_bars=2,
    )
    non_overlap = evaluate_model_slice(
        candidate.research.model,
        frame,
        threshold=candidate.threshold,
        expiry_bars=candidate.expiry_bars,
        fixed_payout=PAYOUT,
        allow_overlapping_positions=False,
        cooldown_bars=0,
    )
    ordinary = bootstrap_expectancy(primary.trades, simulations=5_000, seed=5501)
    blocks: dict[str, object] = {}
    for block_size in (5, 10, 20):
        if len(primary.trades) >= block_size:
            summary = moving_block_bootstrap_expectancy(
                primary.trades,
                block_size=block_size,
                simulations=5_000,
                seed=5500 + block_size,
            )
            blocks[str(block_size)] = asdict(summary)
        else:
            blocks[str(block_size)] = None

    return {
        "payout_sensitivity": _records(payout_table),
        "entry_offset_2": _metric_payload(delayed),
        "non_overlapping": _metric_payload(non_overlap),
        "by_direction": _records(performance_by_direction(primary.trades)),
        "by_month": _records(performance_by_period(primary.trades, frequency="M")),
        "ordinary_bootstrap_expectancy": asdict(ordinary),
        "moving_block_bootstrap_expectancy": blocks,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    downloaded = download_fxcm_year(SYMBOL, YEAR, price_side="mid", timeout=30.0)
    frame = downloaded.frame
    split = chronological_split(frame)

    experiment = run_histgb_experiment(
        frame,
        expiries=EXPIRIES,
        thresholds=THRESHOLDS,
        fixed_payout=PAYOUT,
        development_oof_splits=DEVELOPMENT_OOF_SPLITS,
        minimum_development_trades=MIN_DEVELOPMENT_TRADES,
        minimum_validation_resolved_trades=MIN_VALIDATION_RESOLVED,
        minimum_locked_resolved_trades=MIN_LOCKED_RESOLVED,
    )

    candidate_payload = None
    if experiment.candidate is not None:
        candidate_payload = {
            "expiry_bars": experiment.candidate.expiry_bars,
            "probability_threshold": experiment.candidate.threshold,
            "development_oof": _metric_payload(experiment.candidate.development),
        }

    frozen_model = make_histgb_classifier().get_params()
    report = {
        "study_kind": "preregistered_fixed_nonlinear_ml_baseline",
        "protocol_version": PROTOCOL_VERSION,
        "preregistration": "research/hypotheses/v5-histgradientboosting-preregistration.md",
        "interpretation_warning": (
            "This study uses regular FXCM EUR/USD midpoint data and a hypothetical 82% "
            "binary-style payout. It is not Pocket Option or OTC evidence and is not a "
            "guarantee of future returns."
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
            "split_rows": {
                "development": len(split.development),
                "validation": len(split.validation),
                "locked_test": len(split.test),
            },
        },
        "economics": {
            "payout_source": "hypothetical_fixed_assumption",
            "fixed_payout": PAYOUT,
            "break_even_win_rate": break_even_win_rate(PAYOUT),
        },
        "model_protocol": {
            "model": "HistGradientBoostingClassifier",
            "learning_rate": frozen_model["learning_rate"],
            "max_iter": frozen_model["max_iter"],
            "max_leaf_nodes": frozen_model["max_leaf_nodes"],
            "max_depth": frozen_model["max_depth"],
            "min_samples_leaf": frozen_model["min_samples_leaf"],
            "l2_regularization": frozen_model["l2_regularization"],
            "early_stopping": frozen_model["early_stopping"],
            "random_state": frozen_model["random_state"],
            "feature_columns": list(ML_FEATURE_COLUMNS),
            "expiries": list(EXPIRIES),
            "thresholds": list(THRESHOLDS),
            "development_oof_splits": DEVELOPMENT_OOF_SPLITS,
            "development_candidate_count": len(EXPIRIES) * len(THRESHOLDS),
            "minimum_development_trades": MIN_DEVELOPMENT_TRADES,
            "minimum_validation_resolved_trades": MIN_VALIDATION_RESOLVED,
            "minimum_locked_resolved_trades": MIN_LOCKED_RESOLVED,
            "hyperparameter_search": False,
            "gap_safe_targets_and_settlement": True,
            "robustness_policy": "only_after_passed_locked",
        },
        "status": experiment.status,
        "complete_development_search": _development_search_payload(experiment),
        "selected_candidate": candidate_payload,
        "validation": _metric_payload(experiment.validation),
        "locked_test": _metric_payload(experiment.locked_test),
        "locked_test_robustness": _locked_robustness(
            split.test.reset_index(drop=True), experiment
        ),
        "replication_policy": (
            "Only a passed_locked 2014 result permits fitting the unchanged model specification "
            "on all labeled 2014 observations and evaluating the frozen expiry/threshold once on "
            "untouched FXCM EUR/USD 2015."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print("rows:", len(frame))
    print("status:", experiment.status)
    print("development_cells:", len(report["complete_development_search"]))
    if experiment.candidate is not None:
        print("selected_expiry:", experiment.candidate.expiry_bars)
        print("selected_threshold:", experiment.candidate.threshold)
        print("development_oof:", _metric_payload(experiment.candidate.development))
    print("validation:", _metric_payload(experiment.validation))
    print("locked_test:", _metric_payload(experiment.locked_test))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
