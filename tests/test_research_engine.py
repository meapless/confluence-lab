import numpy as np
import pandas as pd
import pytest

from confluence_lab.backtest import BacktestConfig, run_backtest
from confluence_lab.indicators import add_core_features, ema, rsi
from confluence_lab.metrics import calculate_metrics
from confluence_lab.payouts import TiePolicy, break_even_win_rate, settle_binary_trade
from confluence_lab.splits import chronological_split


def test_break_even_rate() -> None:
    assert break_even_win_rate(0.80) == pytest.approx(1 / 1.8)
    assert break_even_win_rate(0.92) == pytest.approx(1 / 1.92)


def test_call_and_put_settlement() -> None:
    assert settle_binary_trade(direction=1, entry_price=100, exit_price=101, payout=0.8) == ("win", 0.8)
    assert settle_binary_trade(direction=-1, entry_price=100, exit_price=101, payout=0.8) == ("loss", -1.0)


def test_tie_policies() -> None:
    assert settle_binary_trade(direction=1, entry_price=100, exit_price=100, payout=0.8)[1] == 0
    assert settle_binary_trade(direction=1, entry_price=100, exit_price=100, payout=0.8, tie_policy=TiePolicy.LOSS)[1] == -1


def test_split_is_chronological_even_when_input_is_shuffled() -> None:
    frame = pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=100, freq="h"), "x": range(100)})
    frame = frame.sample(frac=1, random_state=3)
    split = chronological_split(frame)
    assert len(split.development) == 60
    assert len(split.validation) == 20
    assert len(split.test) == 20
    assert split.development.timestamp.max() < split.validation.timestamp.min()
    assert split.validation.timestamp.max() < split.test.timestamp.min()


def test_ema_has_no_values_before_minimum_period() -> None:
    s = pd.Series(np.arange(50, dtype=float))
    out = ema(s, 20)
    assert out.iloc[:19].isna().all()
    assert out.iloc[19:].notna().all()


def test_rsi_extremes_on_monotonic_series() -> None:
    up = pd.Series(np.arange(50, dtype=float))
    down = pd.Series(np.arange(50, 0, -1, dtype=float))
    assert rsi(up, 14).iloc[-1] == 100
    assert rsi(down, 14).iloc[-1] == 0


def test_core_features_do_not_change_past_when_future_is_modified() -> None:
    n = 250
    close = pd.Series(np.linspace(1.0, 1.2, n))
    frame = pd.DataFrame({
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 0.001,
        "low": close - 0.001,
        "close": close,
    })
    original = add_core_features(frame)
    altered = frame.copy()
    altered.loc[200:, "close"] *= 10
    altered.loc[200:, "high"] = altered.loc[200:, ["open", "close"]].max(axis=1) + 0.001
    altered.loc[200:, "low"] = altered.loc[200:, ["open", "close"]].min(axis=1) - 0.001
    changed = add_core_features(altered)
    pd.testing.assert_frame_equal(original.iloc[:200], changed.iloc[:200])


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=6, freq="min", tz="UTC"),
        "open": [100, 100, 101, 102, 101, 103],
        "high": [101, 102, 103, 103, 104, 105],
        "low": [99, 99, 100, 100, 100, 102],
        "close": [100, 101, 102, 101, 103, 104],
        "payout": [0.8] * 6,
    })


def test_backtest_enters_after_signal_bar() -> None:
    frame = _frame()
    def strategy(data: pd.DataFrame) -> pd.Series:
        return pd.Series([1, 0, 0, 0, 0, 0], index=data.index)
    result = run_backtest(frame, strategy, BacktestConfig(expiry_bars=2, payout_column="payout"))
    trade = result.trades.iloc[0]
    assert trade.entry_timestamp == frame.iloc[1].timestamp
    assert trade.entry_price == 100
    assert trade.exit_price == frame.iloc[2].close
    assert trade.result == "win"
    assert trade.pnl == pytest.approx(0.8)


def test_strategy_cannot_trade_beyond_dataset_end() -> None:
    frame = _frame()
    def strategy(data: pd.DataFrame) -> pd.Series:
        return pd.Series([0, 0, 0, 0, 0, 1], index=data.index)
    assert run_backtest(frame, strategy, BacktestConfig(expiry_bars=1)).trades.empty


def test_dynamic_payout_is_taken_at_entry() -> None:
    frame = _frame()
    frame["payout"] = [0.1, 0.91, 0.2, 0.2, 0.2, 0.2]
    def strategy(data: pd.DataFrame) -> pd.Series:
        return pd.Series([1, 0, 0, 0, 0, 0], index=data.index)
    result = run_backtest(frame, strategy, BacktestConfig(expiry_bars=1, payout_column="payout"))
    assert result.trades.iloc[0].payout == pytest.approx(0.91)
    assert result.trades.iloc[0].pnl == pytest.approx(0.91)


def test_metrics_and_drawdown() -> None:
    trades = pd.DataFrame({"result": ["win", "loss", "loss", "win"], "pnl": [0.8, -1.0, -1.0, 0.8]})
    m = calculate_metrics(trades)
    assert m.trades == 4
    assert m.win_rate == 0.5
    assert m.total_pnl == pytest.approx(-0.4)
    assert m.max_losing_streak == 2
    assert m.max_drawdown == pytest.approx(2.0)
