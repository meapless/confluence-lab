from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit

from .backtest import BacktestConfig, BacktestResult
from .ml import (
    DEFAULT_PROBABILITY_THRESHOLDS,
    MLPreparedData,
    ThresholdResult,
    prepare_ml_data,
    select_probability_threshold,
)


@dataclass(frozen=True)
class HistGBResearchResult:
    model: HistGradientBoostingClassifier
    selected_threshold: float | None
    development_threshold_results: tuple[ThresholdResult, ...]
    development_oof_probabilities: pd.Series
    development_oof_result: BacktestResult | None


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in frame.columns:
        raise ValueError("frame must contain timestamp")
    return frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()


def make_histgb_classifier() -> HistGradientBoostingClassifier:
    """Return the single preregistered V5 nonlinear model specification."""
    return HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=200,
        max_leaf_nodes=15,
        max_depth=None,
        min_samples_leaf=100,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=42,
    )


def development_oof_probabilities_histgb(
    frame: pd.DataFrame,
    *,
    expiry_bars: int,
    entry_offset_bars: int = 1,
    n_splits: int = 5,
) -> tuple[pd.Series, MLPreparedData]:
    """Generate purged expanding-window OOF probabilities for V5.

    Training excludes target rows that are ties, out of bounds, or cross a
    candle-time gap. Prediction is still made for every feature-valid row in
    each OOF test fold, so future settlement information never determines
    whether the model was allowed to emit a probability.
    """
    if n_splits < 2:
        raise ValueError("n_splits must be >= 2")

    data = _ordered(frame)
    prepared = prepare_ml_data(
        data,
        expiry_bars=expiry_bars,
        entry_offset_bars=entry_offset_bars,
    )
    eligible_positions = np.flatnonzero(prepared.eligible_features.to_numpy())
    if len(eligible_positions) <= n_splits:
        raise ValueError("not enough feature-valid observations for requested splits")

    splitter = TimeSeriesSplit(
        n_splits=n_splits,
        gap=prepared.label_horizon_bars,
    )
    probabilities = pd.Series(np.nan, index=data.index, dtype=float)

    for train_rel, test_rel in splitter.split(eligible_positions):
        train_positions = eligible_positions[train_rel]
        test_positions = eligible_positions[test_rel]
        train_targets = prepared.target_up.iloc[train_positions]
        train_labeled = train_targets.notna().to_numpy()
        train_positions = train_positions[train_labeled]
        if len(train_positions) < 200:
            continue

        y_train = prepared.target_up.iloc[train_positions].astype(int)
        if y_train.nunique() < 2:
            continue

        model = make_histgb_classifier()
        model.fit(prepared.features.iloc[train_positions], y_train)
        probabilities.iloc[test_positions] = model.predict_proba(
            prepared.features.iloc[test_positions]
        )[:, 1]

    return probabilities, prepared


def fit_histgb_research_baseline(
    development: pd.DataFrame,
    *,
    expiry_bars: int,
    fixed_payout: float = 0.82,
    thresholds: Iterable[float] = DEFAULT_PROBABILITY_THRESHOLDS,
    n_splits: int = 5,
    min_oof_trades: int = 300,
) -> HistGBResearchResult:
    """Fit the preregistered V5 model after OOF-only threshold selection."""
    data = _ordered(development)
    config = BacktestConfig(
        expiry_bars=expiry_bars,
        entry_offset_bars=1,
        fixed_payout=fixed_payout,
    )
    probabilities, prepared = development_oof_probabilities_histgb(
        data,
        expiry_bars=expiry_bars,
        entry_offset_bars=1,
        n_splits=n_splits,
    )
    threshold, threshold_results, oof_result = select_probability_threshold(
        data,
        probabilities,
        config=config,
        thresholds=tuple(float(value) for value in thresholds),
        objective="wilson_low",
        min_trades=min_oof_trades,
        min_expectancy=0.0,
    )

    train_positions = np.flatnonzero(
        prepared.eligible_features.to_numpy() & prepared.target_up.notna().to_numpy()
    )
    if len(train_positions) < 200:
        raise ValueError("not enough labeled development observations to fit V5 model")
    y_train = prepared.target_up.iloc[train_positions].astype(int)
    if y_train.nunique() < 2:
        raise ValueError("development target contains only one class")

    model = make_histgb_classifier()
    model.fit(prepared.features.iloc[train_positions], y_train)

    return HistGBResearchResult(
        model=model,
        selected_threshold=threshold,
        development_threshold_results=threshold_results,
        development_oof_probabilities=probabilities,
        development_oof_result=oof_result,
    )
