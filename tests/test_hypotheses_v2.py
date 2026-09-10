import pandas as pd

from confluence_lab.hypotheses_v2 import (
    CompressionBreakoutParams,
    HtfAlignedPullbackParams,
    SweepReversalParams,
    compression_breakout,
    htf_aligned_pullback,
    sweep_reversal,
)
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_v2_hypotheses_emit_only_valid_signal_values():
    frame = generate_synthetic_ohlc(rows=900, seed=117)
    signals = [
        htf_aligned_pullback(frame, HtfAlignedPullbackParams()),
        compression_breakout(frame, CompressionBreakoutParams()),
        sweep_reversal(frame, SweepReversalParams()),
    ]
    for signal in signals:
        assert set(signal.unique()).issubset({-1, 0, 1})
        assert signal.index.equals(frame.index)


def test_v2_hypotheses_do_not_change_past_when_future_changes():
    frame = generate_synthetic_ohlc(rows=900, seed=118)
    altered = frame.copy()
    altered.loc[650:, "open"] *= 1.8
    altered.loc[650:, "close"] *= 1.8
    altered.loc[650:, "high"] = altered.loc[650:, ["open", "close"]].max(axis=1) + 0.02
    altered.loc[650:, "low"] = altered.loc[650:, ["open", "close"]].min(axis=1) - 0.02

    strategies = [
        lambda data: htf_aligned_pullback(data, HtfAlignedPullbackParams(htf_minutes=15)),
        lambda data: compression_breakout(data, CompressionBreakoutParams(htf_minutes=15)),
        lambda data: sweep_reversal(data, SweepReversalParams(liquid_core_only=True)),
    ]
    for strategy in strategies:
        original_signal = strategy(frame)
        changed_signal = strategy(altered)
        pd.testing.assert_series_equal(
            original_signal.loc[:649],
            changed_signal.loc[:649],
        )
