import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest


def _frame(rows=12):
    close = [100 + i for i in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC"),
            "open": close,
            "high": [value + 1 for value in close],
            "low": [value - 1 for value in close],
            "close": [value + 0.5 for value in close],
        }
    )


def _always(frame):
    return pd.Series(1, index=frame.index, dtype="int8")


def test_non_overlapping_mode_reduces_correlated_candidates():
    frame = _frame()
    overlapping = run_backtest(
        frame,
        _always,
        BacktestConfig(expiry_bars=3, allow_overlapping_positions=True),
    )
    independent = run_backtest(
        frame,
        _always,
        BacktestConfig(expiry_bars=3, allow_overlapping_positions=False),
    )
    assert overlapping.metrics.trades == 9
    assert independent.metrics.trades == 3
    assert (independent.trades["entry_timestamp"].iloc[1:].reset_index(drop=True) > independent.trades["exit_timestamp"].iloc[:-1].reset_index(drop=True)).all()


def test_cooldown_requires_full_bars_after_settlement():
    frame = _frame(20)
    result = run_backtest(
        frame,
        _always,
        BacktestConfig(
            expiry_bars=2,
            allow_overlapping_positions=False,
            cooldown_bars=2,
        ),
    )
    entries = result.trades["entry_timestamp"].tolist()
    exits = result.trades["exit_timestamp"].tolist()
    assert len(entries) >= 2
    # 1-minute bars: after a two-bar cooldown, the next entry is at least
    # three minutes after the prior exit bar timestamp.
    assert all(next_entry - prior_exit >= pd.Timedelta(minutes=3) for next_entry, prior_exit in zip(entries[1:], exits[:-1], strict=True))


def test_default_behavior_remains_overlap_compatible():
    frame = _frame()
    default = run_backtest(frame, _always, BacktestConfig(expiry_bars=3))
    explicit = run_backtest(
        frame,
        _always,
        BacktestConfig(expiry_bars=3, allow_overlapping_positions=True),
    )
    pd.testing.assert_frame_equal(default.trades, explicit.trades)
