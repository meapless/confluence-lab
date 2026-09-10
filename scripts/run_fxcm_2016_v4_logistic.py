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
from confluence_lab.ml_experiment import evaluate_model_slice, run_logistic_experiment
from confluence_lab.payouts import break_even_win_rate
from confluence_lab.robustness import (
    bootstrap_expectancy,
    moving_block_bootstrap_expectancy,
)
from confluence_lab.splits import chronological_split
from confluence_lab.stress import payout_sensitivity, performance_by_direction, performance_by_period

YEAR = 2016
SYMBOL = "EURUSD"
PROTOCOL_VERSION = "v4-2016-logistic-baseline-1"
PAYOUT = 0.82
EXPIRIES = (1, 2, 3, 5)
THRESHOLDS = DEFAULT_PROBABILITY_THRESHOLDS
DEVELOPMENT_OOF_SPLITS = 5
MIN_DEVELOPMENT_TRADES = 300
MIN_VALIDATION_RESOLVED = 150
MIN_LOCKED_RESOLVED = 150


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run preregistered V4 logistic benchmark")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/fxcm-eurusd-m1-2016-v4-logistic.json"),
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


def _coefficient_payload(candidate):
    if candidate is None:
        return None
    pipeline = candidate.research.model
    model = pipeline.named_steps["model"]
    coefficients = model.coef_[0]
    rows = [
        {"feature": feature, "standardized_coefficient": float(coefficient)}
        for feature, coefficient in zip(ML_FEATURE_COLUMNS, coefficients, strict=True)
    ]
    rows.sort(key=lambda item: abs(item["standardized_coefficient"]), reverse=True)
    return {
        "intercept": float(model.intercept_[0]),
        "coefficients_by_absolute_magnitude": rows,
        "interpretation": (
            "Coefficients are from the development-fitted StandardScaler + LogisticRegression "
            "pipeline. Magnitude is descriptive and must not be interpreted as causal evidence."
        ),
    }


def _locked_robustness(frame: pd.DataFrame, experiment):
    if experiment.candidate is None or experiment.locked_test is None:
        return None
    candidate = experiment.candidate
    model = candidate.research.model
    threshold = candidate.threshold
    expiry = candidate.expiry_bars
    primary = experiment.locked_test

    payout_table = payout_sensitivity(primary.trades, payouts=(0.80, 0.82, 0.90))
    delayed = evaluate_model_slice(
        model,
        frame,
        threshold=threshold,
        expiry_bars=expiry,
        fixed_payout=PAYOUT,
        entry_offset_bars=2,
    )
    non_overlap = evaluate_model_slice(
        model,
        frame,
        threshold=threshold,
        expiry_bars=expiry,
        fixed_payout=PAYOUT,
        entry_offset_bars=1,
        allow_overlapping_positions=False,
        cooldown_bars=0,
    )

    ordinary = bootstrap_expectancy(primary.trades, simulations=5_000, seed=4401)
    blocks = {}
    for block_size in (5, 10, 20):
        if len(primary.trades) >= block_size:
            summary = moving_block_bootstrap_expectancy(
                primary.trades,
                block_size=block_size,
                simulations=5_000,
                seed=4400 + block_size,
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

    experiment = run_logistic_experiment(
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

    report = {
        "study_kind": "preregistered_interpretable_ml_baseline",
        "protocol_version": PROTOCOL_VERSION,
        "preregistration": "research/hypotheses/v4-logistic-baseline-preregistration.md",
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
            "model": "StandardScaler + LogisticRegression",
            "C": 1.0,
            "penalty": "l2",
            "solver": "lbfgs",
            "max_iter": 1000,
            "class_weight": None,
            "feature_columns": list(ML_FEATURE_COLUMNS),
            "expiries": list(EXPIRIES),
            "thresholds": list(THRESHOLDS),
            "development_oof_splits": DEVELOPMENT_OOF_SPLITS,
            "development_candidate_count": len(EXPIRIES) * len(THRESHOLDS),
            "minimum_development_trades": MIN_DEVELOPMENT_TRADES,
            "minimum_validation_resolved_trades": MIN_VALIDATION_RESOLVED,
            "minimum_locked_resolved_trades": MIN_LOCKED_RESOLVED,
        },
        "status": experiment.status,
        "complete_development_search": _development_search_payload(experiment),
        "selected_candidate": candidate_payload,
        "validation": _metric_payload(experiment.validation),
        "locked_test": _metric_payload(experiment.locked_test),
        "development_model": _coefficient_payload(experiment.candidate),
        "locked_test_robustness": _locked_robustness(
            split.test.reset_index(drop=True), experiment
        ),
        "replication_policy": (
            "Only a passed_locked result may be frozen for a preregistered no-tuning "
            "replication on FXCM EUR/USD 2015."
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
