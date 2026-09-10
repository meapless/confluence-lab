import numpy as np
import pandas as pd

from confluence_lab.backtest import BacktestConfig
from confluence_lab.ml import (
    DEFAULT_PROBABILITY_THRESHOLDS,
    ML_FEATURE_COLUMNS,
    binary_direction_target,
    build_ml_features,
    development_oof_probabilities,
    fit_logistic_research_baseline,
    predict_probabilities,
    probability_to_signal,
    select_probability_threshold,
)
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_binary_direction_target_matches_next_bar_entry_and_expiry_close():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="1min", tz="UTC"),
            "open": [10.0, 10.0, 11.0, 9.0, 10.0, 8.0],
            "high": [11.0, 12.0, 12.0, 11.0, 11.0, 9.0],
            "low": [9.0, 9.0, 8.0, 8.0, 7.0, 7.0],
            "close": [10.0, 11.0, 9.0, 10.0, 8.0, 8.0],
        }
    )
    target = binary_direction_target(frame, expiry_bars=2, entry_offset_bars=1)
    assert target.iloc[0] == 0.0
    assert target.iloc[1] == 0.0
    assert target.iloc[2] == 0.0
    assert target.iloc[3] == 0.0
    assert pd.isna(target.iloc[4])
    assert pd.isna(target.iloc[5])


def test_ml_features_are_fixed_and_future_isolated():
    frame = generate_synthetic_ohlc(rows=2_000, seed=201)
    original = build_ml_features(frame)
    assert tuple(original.columns) == ML_FEATURE_COLUMNS

    altered = frame.copy()
    altered.loc[1600:, "close"] *= 2.0
    altered.loc[1600:, "high"] = altered.loc[1600:, ["open", "close"]].max(axis=1) + 0.02
    altered.loc[1600:, "low"] = altered.loc[1600:, ["open", "close"]].min(axis=1) - 0.02
    changed = build_ml_features(altered)
    pd.testing.assert_frame_equal(original.iloc[:1600], changed.iloc[:1600])


def test_probability_to_signal_has_symmetric_no_trade_zone():
    probabilities = pd.Series([0.20, 0.39, 0.40, 0.50, 0.60, 0.61, 0.80])
    signal = probability_to_signal(probabilities, threshold=0.60)
    assert list(signal) == [-1, -1, -1, 0, 1, 1, 1]


def test_development_oof_predictions_do_not_predict_training_prefix():
    frame = generate_synthetic_ohlc(rows=4_000, seed=202)
    probabilities, prepared = development_oof_probabilities(
        frame, expiry_bars=2, n_splits=4
    )
    assert len(probabilities) == len(frame)
    assert prepared.label_horizon_bars == 2
    assert probabilities.notna().sum() > 0
    first_prediction = int(np.flatnonzero(probabilities.notna().to_numpy())[0])
    assert first_prediction > 0
    assert probabilities.dropna().between(0.0, 1.0).all()


def test_logistic_research_baseline_fits_without_assuming_profitability():
    frame = generate_synthetic_ohlc(rows=5_000, seed=203)
    result = fit_logistic_research_baseline(
        frame,
        expiry_bars=1,
        thresholds=DEFAULT_PROBABILITY_THRESHOLDS,
        n_splits=4,
        min_oof_trades=10,
    )
    assert len(result.development_threshold_results) == len(DEFAULT_PROBABILITY_THRESHOLDS)
    probabilities = predict_probabilities(result.model, frame)
    assert probabilities.notna().sum() > 0
    assert probabilities.dropna().between(0.0, 1.0).all()


def test_threshold_tie_prefers_higher_preregistered_confidence():
    rows = 400
    frame = generate_synthetic_ohlc(rows=rows, seed=204)
    probabilities = pd.Series(np.where(np.arange(rows) % 2 == 0, 0.8, 0.2))
    threshold, _, _ = select_probability_threshold(
        frame,
        probabilities,
        config=BacktestConfig(expiry_bars=1, fixed_payout=0.82),
        thresholds=(0.55, 0.60, 0.65),
        objective="win_rate",
        min_trades=1,
        min_expectancy=None,
    )
    assert threshold == 0.65


def test_probability_threshold_rejects_invalid_values():
    probabilities = pd.Series([0.2, 0.8])
    for threshold in (0.5, 1.0, 1.1):
        try:
            probability_to_signal(probabilities, threshold=threshold)
        except ValueError:
            pass
        else:
            raise AssertionError(f"threshold {threshold} should fail")
