import pandas as pd

from confluence_lab.hypotheses import range_reversion
from confluence_lab.hypotheses_v3 import V3A_RANGE_PARAMS, call_only_range_reversion
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
