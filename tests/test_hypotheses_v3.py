import pandas as pd

from confluence_lab.context import add_research_context
from confluence_lab.hypotheses import range_reversion
from confluence_lab.hypotheses_v2 import sweep_reversal_from_features
from confluence_lab.hypotheses_v3 import (
    V3A_RANGE_PARAMS,
    V3B_ATR_PERCENTILE_HIGH_INCLUSIVE,
    V3B_ATR_PERCENTILE_LOW_EXCLUSIVE,
    V3B_SWEEP_PARAMS,
    call_only_range_reversion,
    moderate_vol_sweep_reversal,
)
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_v3a_parameters_are_frozen_to_preregistered_values():
    assert V3A_RANGE_PARAMS.adx_max == 30.0
    assert V3A_RANGE_PARAMS.rsi_lower == 25.0
    assert V3A_RANGE_PARAMS.rsi_upper == 65.0
    assert V3A_RANGE_PARAMS.band_buffer_atr == 0.10
    assert V3A_RANGE_PARAMS.atr_pct_max == 0.70


def test_call_only_filter_never_emits_puts_and_preserves_calls():
    frame = generate_synthetic_ohlc(rows=2_000, seed=121)
    base = range_reversion(frame, V3A_RANGE_PARAMS)
    filtered = call_only_range_reversion(frame)
    assert set(filtered.unique()).issubset({0, 1})
    pd.testing.assert_series_equal(filtered.eq(1), base.eq(1))


def test_call_only_hypothesis_is_future_isolated():
    frame = generate_synthetic_ohlc(rows=1_200, seed=122)
    original = call_only_range_reversion(frame)

    altered = frame.copy()
    altered.loc[900:, "close"] *= 1.7
    altered.loc[900:, "high"] = altered.loc[900:, ["open", "close"]].max(axis=1) + 0.02
    altered.loc[900:, "low"] = altered.loc[900:, ["open", "close"]].min(axis=1) - 0.02
    changed = call_only_range_reversion(altered)

    pd.testing.assert_series_equal(original.iloc[:900], changed.iloc[:900])


def test_v3b_parameters_and_volatility_boundaries_are_frozen():
    assert V3B_SWEEP_PARAMS.lookback == 20
    assert V3B_SWEEP_PARAMS.wick_min == 0.65
    assert V3B_SWEEP_PARAMS.rsi_edge == 65.0
    assert V3B_SWEEP_PARAMS.overshoot_atr == 0.0
    assert V3B_SWEEP_PARAMS.liquid_core_only is False
    assert V3B_ATR_PERCENTILE_LOW_EXCLUSIVE == 0.25
    assert V3B_ATR_PERCENTILE_HIGH_INCLUSIVE == 0.50


def test_v3b_is_exact_base_sweep_masked_by_frozen_atr_q2():
    frame = generate_synthetic_ohlc(rows=3_000, seed=123)
    features = add_research_context(frame)
    base = sweep_reversal_from_features(features, V3B_SWEEP_PARAMS)
    expected_eligible = (
        features["atr_percentile_100"].gt(0.25)
        & features["atr_percentile_100"].le(0.50)
    )
    filtered = moderate_vol_sweep_reversal(frame)

    pd.testing.assert_series_equal(filtered, base.where(expected_eligible, 0).astype("int8"))
    assert (filtered.loc[~expected_eligible] == 0).all()


def test_v3b_hypothesis_is_future_isolated():
    frame = generate_synthetic_ohlc(rows=1_500, seed=124)
    original = moderate_vol_sweep_reversal(frame)

    altered = frame.copy()
    altered.loc[1100:, "close"] *= 2.1
    altered.loc[1100:, "high"] = altered.loc[1100:, ["open", "close"]].max(axis=1) + 0.03
    altered.loc[1100:, "low"] = altered.loc[1100:, ["open", "close"]].min(axis=1) - 0.03
    changed = moderate_vol_sweep_reversal(altered)

    pd.testing.assert_series_equal(original.iloc[:1100], changed.iloc[:1100])
