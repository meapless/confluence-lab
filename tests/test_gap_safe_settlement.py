import numpy as np
import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest_signals
from confluence_lab.ml import binary_direction_target
from confluence_lab.timebase import contiguous_horizon_mask, infer_bar_interval


def _gapped_frame() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2026-01-02T21:57:00Z",
            "2026-01-02T21:58:00Z",
            "2026-01-02T21:59:00Z",
            "2026-01-04T22:00:00Z",
            "2026-01-04T22:01:00Z",
            "2026-01-04T22:02:00Z",
        ],
        utc=True,
    )
    close = [1.0000, 1.0001, 1.0002, 1.0100, 1.0101, 1.0102]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close,
            "high": [value + 0.0002 for value in close],
            "low": [value - 0.0002 for value in close],
            "close": close,
        }
    )


def test_infer_bar_interval_ignores_long_closure_when_minute_spacing_dominates():
    frame = _gapped_frame()
    assert infer_bar_interval(frame["timestamp"]) == pd.Timedelta(minutes=1)


def test_contiguous_horizon_rejects_weekend_crossing_candidate():
    frame = _gapped_frame()
    mask = contiguous_horizon_mask(
        frame["timestamp"],
        np.array([0, 1, 3]),
        np.array([1, 3, 5]),
    )
    assert mask.tolist() == [True, False, True]


def test_backtest_drops_trade_whose_entry_or_expiry_crosses_gap():
    frame = _gapped_frame()
    signal = pd.Series([0, 1, 0, 1, 0, 0], dtype="int8")

    safe = run_backtest_signals(
        frame,
        signal,
        BacktestConfig(expiry_bars=2, entry_offset_bars=1, fixed_payout=0.82),
    )
    assert safe.metrics.trades == 1
    assert safe.trades.iloc[0]["signal_timestamp"] == frame.iloc[3]["timestamp"]

    legacy = run_backtest_signals(
        frame,
        signal,
        BacktestConfig(
            expiry_bars=2,
            entry_offset_bars=1,
            fixed_payout=0.82,
            require_contiguous_bars=False,
        ),
    )
    assert legacy.metrics.trades == 2


def test_ml_target_marks_gap_crossing_expiry_unlabeled():
    frame = _gapped_frame()
    target = binary_direction_target(frame, expiry_bars=2, entry_offset_bars=1)

    # Signal row 1 would enter row 2 and settle row 3 across the closure.
    assert pd.isna(target.iloc[1])
    # Signal row 3 enters row 4 and settles row 5 on contiguous minute bars.
    assert target.iloc[3] == 1.0


def test_explicit_expected_interval_is_honored():
    frame = _gapped_frame()
    signal = pd.Series([1, 0, 0, 0, 0, 0], dtype="int8")
    result = run_backtest_signals(
        frame,
        signal,
        BacktestConfig(
            expiry_bars=1,
            entry_offset_bars=1,
            expected_interval_seconds=60,
        ),
    )
    assert result.metrics.trades == 1
