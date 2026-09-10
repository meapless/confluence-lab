from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .backtest import BacktestConfig, BacktestResult, run_backtest_signals
from .context import add_research_context
from .metrics import PerformanceMetrics
from .optimization import score_metrics


ML_FEATURE_COLUMNS: tuple[str, ...] = (
    "return_1",
    "return_3",
    "return_5",
    "body_atr",
    "range_atr",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "ema_spread_atr",
    "ema20_slope_atr",
    "ema50_slope_atr",
    "distance_ema20_atr",
    "rsi_14",
    "macd_hist_atr",
    "adx_14",
    "atr_percentile_100",
    "bb_position",
    "atr_ratio_5_50",
    "bb_width_percentile_200",
    "range_position_20",
    "htf_5_trend",
    "htf_15_trend",
    "htf_5_return_1",
    "htf_15_return_1",
    "utc_hour_sin",
    "utc_hour_cos",
    "utc_weekday_sin",
    "utc_weekday_cos",
)

DEFAULT_PROBABILITY_THRESHOLDS: tuple[float, ...] = (0.55, 0.575, 0.60, 0.625, 0.65)


@dataclass(frozen=True)
class MLPreparedData:
    features: pd.DataFrame
    target_up: pd.Series
    eligible_features: pd.Series
    label_horizon_bars: int


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    metrics: PerformanceMetrics
    score: float


@dataclass(frozen=True)
class LogisticResearchResult:
    model: Pipeline
    selected_threshold: float | None
    development_threshold_results: tuple[ThresholdResult, ...]
    development_oof_probabilities: pd.Series
    development_oof_result: BacktestResult | None


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in frame.columns:
        raise ValueError("frame must contain timestamp")
    return frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()


def build_ml_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build scale-aware, causal features for the interpretable V4 baseline."""
    context = add_research_context(_ordered(frame))
    out = pd.DataFrame(index=context.index)
    close = context["close"].astype(float)
    atr = context["atr_14"].replace(0.0, np.nan).astype(float)

    out["return_1"] = close.pct_change(1)
    out["return_3"] = close.pct_change(3)
    out["return_5"] = close.pct_change(5)
    out["body_atr"] = (context["close"] - context["open"]) / atr
    out["range_atr"] = (context["high"] - context["low"]) / atr
    out["upper_wick_ratio"] = context["upper_wick_ratio"]
    out["lower_wick_ratio"] = context["lower_wick_ratio"]
    out["ema_spread_atr"] = (context["ema_20"] - context["ema_50"]) / atr
    out["ema20_slope_atr"] = context["ema_20_slope"] / atr
    out["ema50_slope_atr"] = context["ema_50_slope"] / atr
    out["distance_ema20_atr"] = context["distance_ema20_atr"]
    out["rsi_14"] = context["rsi_14"]
    out["macd_hist_atr"] = context["macd_hist"] / atr
    out["adx_14"] = context["adx_14"]
    out["atr_percentile_100"] = context["atr_percentile_100"]

    bb_width = (context["bb_upper"] - context["bb_lower"]).replace(0.0, np.nan)
    out["bb_position"] = (context["close"] - context["bb_middle"]) / bb_width
    out["atr_ratio_5_50"] = context["atr_ratio_5_50"]
    out["bb_width_percentile_200"] = context["bb_width_percentile_200"]
    out["range_position_20"] = context["range_position_20"]
    out["htf_5_trend"] = pd.to_numeric(context["htf_5_trend"], errors="coerce")
    out["htf_15_trend"] = pd.to_numeric(context["htf_15_trend"], errors="coerce")
    out["htf_5_return_1"] = context["htf_5_return_1"]
    out["htf_15_return_1"] = context["htf_15_return_1"]

    hour = context["utc_hour"].astype(float)
    weekday = context["utc_weekday"].astype(float)
    out["utc_hour_sin"] = np.sin(2.0 * pi * hour / 24.0)
    out["utc_hour_cos"] = np.cos(2.0 * pi * hour / 24.0)
    out["utc_weekday_sin"] = np.sin(2.0 * pi * weekday / 7.0)
    out["utc_weekday_cos"] = np.cos(2.0 * pi * weekday / 7.0)

    out = out.replace([np.inf, -np.inf], np.nan)
    return out.loc[:, ML_FEATURE_COLUMNS]


def binary_direction_target(
    frame: pd.DataFrame,
    *,
    expiry_bars: int,
    entry_offset_bars: int = 1,
) -> pd.Series:
    """Return future up/down target from the same settlement convention as backtests.

    Target values are 1.0 for an upward expiry, 0.0 for a downward expiry and
    NaN for ties/out-of-bounds rows. NaN target rows are excluded from model
    fitting only; they must not be excluded from prediction eligibility.
    """
    if expiry_bars < 1:
        raise ValueError("expiry_bars must be >= 1")
    if entry_offset_bars < 1:
        raise ValueError("entry_offset_bars must be >= 1")
    data = _ordered(frame)
    entry_index = np.arange(len(data)) + entry_offset_bars
    exit_index = entry_index + expiry_bars - 1
    target = np.full(len(data), np.nan, dtype=float)
    valid = exit_index < len(data)
    if valid.any():
        entry = data["open"].to_numpy(dtype=float)[entry_index[valid]]
        exit_ = data["close"].to_numpy(dtype=float)[exit_index[valid]]
        delta = exit_ - entry
        positions = np.flatnonzero(valid)
        target[positions[delta > 0]] = 1.0
        target[positions[delta < 0]] = 0.0
    return pd.Series(target, index=data.index, name="target_up")


def prepare_ml_data(
    frame: pd.DataFrame,
    *,
    expiry_bars: int,
    entry_offset_bars: int = 1,
) -> MLPreparedData:
    data = _ordered(frame)
    features = build_ml_features(data)
    target = binary_direction_target(
        data,
        expiry_bars=expiry_bars,
        entry_offset_bars=entry_offset_bars,
    )
    eligible = features.notna().all(axis=1)
    return MLPreparedData(
        features=features,
        target_up=target,
        eligible_features=eligible,
        label_horizon_bars=entry_offset_bars + expiry_bars - 1,
    )


def make_logistic_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=1.0,
                    penalty="l2",
                    solver="lbfgs",
                    max_iter=1_000,
                    class_weight=None,
                ),
            ),
        ]
    )


def probability_to_signal(
    probabilities: pd.Series,
    *,
    threshold: float,
    index: pd.Index | None = None,
) -> pd.Series:
    if not 0.5 < threshold < 1.0:
        raise ValueError("threshold must be strictly between 0.5 and 1")
    probs = pd.to_numeric(probabilities, errors="coerce")
    target_index = index if index is not None else probs.index
    probs = probs.reindex(target_index)
    signal = pd.Series(0, index=target_index, dtype="int8")
    signal.loc[probs.ge(threshold)] = 1
    signal.loc[probs.le(1.0 - threshold)] = -1
    return signal


def development_oof_probabilities(
    frame: pd.DataFrame,
    *,
    expiry_bars: int,
    entry_offset_bars: int = 1,
    n_splits: int = 5,
) -> tuple[pd.Series, MLPreparedData]:
    """Generate expanding-window out-of-fold probabilities on development data.

    Fold training excludes tie/out-of-bounds targets, but predictions are made
    for every feature-valid row in the fold. This avoids the lookahead error of
    deciding ex ante not to trade rows merely because they later settle as ties.
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
        if len(train_positions) < 50:
            continue
        y_train = prepared.target_up.iloc[train_positions].astype(int)
        if y_train.nunique() < 2:
            continue

        model = make_logistic_pipeline()
        model.fit(prepared.features.iloc[train_positions], y_train)
        probabilities.iloc[test_positions] = model.predict_proba(
            prepared.features.iloc[test_positions]
        )[:, 1]

    return probabilities, prepared


def select_probability_threshold(
    frame: pd.DataFrame,
    probabilities: pd.Series,
    *,
    config: BacktestConfig,
    thresholds: Iterable[float] = DEFAULT_PROBABILITY_THRESHOLDS,
    objective: str = "wilson_low",
    min_trades: int = 200,
    min_expectancy: float | None = 0.0,
) -> tuple[float | None, tuple[ThresholdResult, ...], BacktestResult | None]:
    data = _ordered(frame)
    probs = pd.Series(probabilities.to_numpy(copy=True), index=data.index, dtype=float)
    results: list[ThresholdResult] = []
    best_result: BacktestResult | None = None
    best_threshold: float | None = None
    best_score = float("-inf")
    for threshold in thresholds:
        threshold = float(threshold)
        signal = probability_to_signal(probs, threshold=threshold, index=data.index)
        backtest = run_backtest_signals(data, signal, config)
        score = score_metrics(
            backtest.metrics,
            objective=objective,
            min_trades=min_trades,
            min_expectancy=min_expectancy,
        )
        results.append(
            ThresholdResult(
                threshold=threshold,
                metrics=backtest.metrics,
                score=score,
            )
        )
        # Preregistered deterministic tie-break: when statistical score is
        # identical, retain the higher (more selective) confidence threshold.
        better_tie = (
            score == best_score
            and score != float("-inf")
            and (best_threshold is None or threshold > best_threshold)
        )
        if score > best_score or better_tie:
            best_score = score
            best_threshold = threshold
            best_result = backtest

    if best_score == float("-inf"):
        return None, tuple(results), None
    return best_threshold, tuple(results), best_result


def fit_logistic_research_baseline(
    development: pd.DataFrame,
    *,
    expiry_bars: int,
    fixed_payout: float = 0.82,
    thresholds: Iterable[float] = DEFAULT_PROBABILITY_THRESHOLDS,
    n_splits: int = 5,
    min_oof_trades: int = 200,
) -> LogisticResearchResult:
    data = _ordered(development)
    config = BacktestConfig(
        expiry_bars=expiry_bars,
        entry_offset_bars=1,
        fixed_payout=fixed_payout,
    )
    probabilities, prepared = development_oof_probabilities(
        data,
        expiry_bars=expiry_bars,
        entry_offset_bars=1,
        n_splits=n_splits,
    )
    threshold, threshold_results, oof_result = select_probability_threshold(
        data,
        probabilities,
        config=config,
        thresholds=thresholds,
        objective="wilson_low",
        min_trades=min_oof_trades,
        min_expectancy=0.0,
    )

    train_positions = np.flatnonzero(
        prepared.eligible_features.to_numpy() & prepared.target_up.notna().to_numpy()
    )
    if len(train_positions) < 50:
        raise ValueError("not enough labeled development observations to fit model")
    y_train = prepared.target_up.iloc[train_positions].astype(int)
    if y_train.nunique() < 2:
        raise ValueError("development target contains only one class")
    model = make_logistic_pipeline()
    model.fit(prepared.features.iloc[train_positions], y_train)

    return LogisticResearchResult(
        model=model,
        selected_threshold=threshold,
        development_threshold_results=threshold_results,
        development_oof_probabilities=probabilities,
        development_oof_result=oof_result,
    )


def predict_probabilities(
    model: Pipeline,
    frame: pd.DataFrame,
) -> pd.Series:
    data = _ordered(frame)
    features = build_ml_features(data)
    eligible = features.notna().all(axis=1)
    probabilities = pd.Series(np.nan, index=data.index, dtype=float)
    positions = np.flatnonzero(eligible.to_numpy())
    if len(positions):
        probabilities.iloc[positions] = model.predict_proba(features.iloc[positions])[:, 1]
    return probabilities
