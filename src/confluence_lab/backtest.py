from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .metrics import PerformanceMetrics, calculate_metrics
from .payouts import TiePolicy, break_even_win_rate
from .strategies import SignalFunction
from .timebase import contiguous_horizon_mask

_REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close"}
_TRADE_COLUMNS = [
    "signal_timestamp",
    "entry_timestamp",
    "exit_timestamp",
    "direction",
    "entry_price",
    "exit_price",
    "payout",
    "break_even_win_rate",
    "result",
    "pnl",
]


@dataclass(frozen=True)
class BacktestConfig:
    expiry_bars: int = 1
    entry_offset_bars: int = 1
    fixed_payout: float = 0.82
    payout_column: str | None = None
    min_payout: float | None = None
    stake: float = 1.0
    tie_policy: TiePolicy = TiePolicy.REFUND
    allow_overlapping_positions: bool = True
    cooldown_bars: int = 0
    require_contiguous_bars: bool = True
    expected_interval_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.expiry_bars < 1:
            raise ValueError("expiry_bars must be >= 1")
        if self.entry_offset_bars < 1:
            raise ValueError("entry_offset_bars must be >= 1 to avoid same-bar execution assumptions")
        if not 0 <= self.fixed_payout <= 10:
            raise ValueError("fixed_payout must be a decimal return, e.g. 0.82 for 82%")
        if self.min_payout is not None and not 0 <= self.min_payout <= 10:
            raise ValueError("min_payout must be a decimal return, e.g. 0.82 for 82%")
        if self.stake <= 0:
            raise ValueError("stake must be positive")
        if self.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be >= 0")
        if self.expected_interval_seconds is not None and self.expected_interval_seconds <= 0:
            raise ValueError("expected_interval_seconds must be positive")


@dataclass(frozen=True)
class BacktestResult:
    trades: pd.DataFrame
    metrics: PerformanceMetrics
    config: BacktestConfig

    def summary(self) -> dict[str, object]:
        values = asdict(self.metrics)
        values["break_even_win_rate"] = break_even_win_rate(self.config.fixed_payout)
        return values


def _validate_frame(frame: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    missing = _REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    if config.payout_column and config.payout_column not in frame.columns:
        raise ValueError(f"payout column {config.payout_column!r} not found")

    ordered = frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()
    ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True, errors="raise")
    if ordered["timestamp"].duplicated().any():
        raise ValueError("duplicate timestamps are not allowed")
    if (ordered["high"] < ordered[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid OHLC row: high is below another price")
    if (ordered["low"] > ordered[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid OHLC row: low is above another price")
    return ordered


def _empty_result(config: BacktestConfig) -> BacktestResult:
    trades = pd.DataFrame(columns=_TRADE_COLUMNS)
    return BacktestResult(trades=trades, metrics=calculate_metrics(trades), config=config)


def _non_overlapping_mask(
    entry_indices: np.ndarray,
    exit_indices: np.ndarray,
    *,
    cooldown_bars: int,
) -> np.ndarray:
    """Select candidates whose entry occurs after the prior accepted trade settles.

    This intentionally operates in chronological order. A cooldown of zero
    still requires the next entry bar to be strictly after the prior exit bar,
    because an entry at a bar's open precedes settlement at that bar's close.
    """
    keep = np.zeros(len(entry_indices), dtype=bool)
    last_exit = -1
    for index, (entry, exit_) in enumerate(zip(entry_indices, exit_indices, strict=True)):
        if int(entry) > last_exit + cooldown_bars:
            keep[index] = True
            last_exit = int(exit_)
    return keep


def _run_on_validated(
    data: pd.DataFrame,
    signal: pd.Series,
    config: BacktestConfig,
) -> BacktestResult:
    """Vectorized settlement for a prevalidated, ordered frame and signal series."""
    if not signal.index.equals(data.index):
        signal = signal.reindex(data.index)

    raw_signal = pd.to_numeric(signal, errors="coerce").to_numpy(dtype=float)
    signal_indices = np.flatnonzero(np.isfinite(raw_signal) & (raw_signal != 0))
    if not len(signal_indices):
        return _empty_result(config)

    directions = raw_signal[signal_indices].astype(np.int8)
    if not np.isin(directions, [-1, 1]).all():
        raise ValueError("strategy produced direction outside {-1, 0, 1}")

    entry_indices = signal_indices + config.entry_offset_bars
    exit_indices = entry_indices + config.expiry_bars - 1
    in_bounds = (entry_indices < len(data)) & (exit_indices < len(data))
    signal_indices = signal_indices[in_bounds]
    entry_indices = entry_indices[in_bounds]
    exit_indices = exit_indices[in_bounds]
    directions = directions[in_bounds]
    if not len(signal_indices):
        return _empty_result(config)

    if config.require_contiguous_bars:
        expected_interval = (
            pd.Timedelta(seconds=float(config.expected_interval_seconds))
            if config.expected_interval_seconds is not None
            else None
        )
        contiguous = contiguous_horizon_mask(
            data["timestamp"],
            signal_indices,
            exit_indices,
            expected_interval=expected_interval,
        )
        signal_indices = signal_indices[contiguous]
        entry_indices = entry_indices[contiguous]
        exit_indices = exit_indices[contiguous]
        directions = directions[contiguous]
        if not len(signal_indices):
            return _empty_result(config)

    if config.payout_column:
        payout_values = pd.to_numeric(
            data[config.payout_column], errors="coerce"
        ).to_numpy(dtype=float)
        payouts = payout_values[entry_indices]
    else:
        payouts = np.full(len(entry_indices), config.fixed_payout, dtype=float)

    if not np.isfinite(payouts).all() or ((payouts < 0) | (payouts > 10)).any():
        raise ValueError("payout values must be finite decimal returns between 0 and 10")

    if config.min_payout is not None:
        eligible = payouts >= config.min_payout
        signal_indices = signal_indices[eligible]
        entry_indices = entry_indices[eligible]
        exit_indices = exit_indices[eligible]
        directions = directions[eligible]
        payouts = payouts[eligible]
        if not len(signal_indices):
            return _empty_result(config)

    if not config.allow_overlapping_positions:
        keep = _non_overlapping_mask(
            entry_indices,
            exit_indices,
            cooldown_bars=config.cooldown_bars,
        )
        signal_indices = signal_indices[keep]
        entry_indices = entry_indices[keep]
        exit_indices = exit_indices[keep]
        directions = directions[keep]
        payouts = payouts[keep]
        if not len(signal_indices):
            return _empty_result(config)

    open_values = data["open"].to_numpy(dtype=float)
    close_values = data["close"].to_numpy(dtype=float)
    entry_prices = open_values[entry_indices]
    exit_prices = close_values[exit_indices]

    signed_delta = directions * (exit_prices - entry_prices)
    win = signed_delta > 0
    loss = signed_delta < 0
    tie = ~(win | loss)

    results = np.full(len(signed_delta), "tie", dtype=object)
    results[win] = "win"
    results[loss] = "loss"
    pnl = np.zeros(len(signed_delta), dtype=float)
    pnl[win] = config.stake * payouts[win]
    pnl[loss] = -config.stake

    tie_policy = TiePolicy(config.tie_policy)
    if tie_policy is TiePolicy.LOSS:
        results[tie] = "loss"
        pnl[tie] = -config.stake
    elif tie_policy is TiePolicy.WIN:
        results[tie] = "win"
        pnl[tie] = config.stake * payouts[tie]

    timestamps = data["timestamp"].to_numpy()
    trades = pd.DataFrame(
        {
            "signal_timestamp": timestamps[signal_indices],
            "entry_timestamp": timestamps[entry_indices],
            "exit_timestamp": timestamps[exit_indices],
            "direction": directions,
            "entry_price": entry_prices,
            "exit_price": exit_prices,
            "payout": payouts,
            "break_even_win_rate": 1.0 / (1.0 + payouts),
            "result": results,
            "pnl": pnl,
        },
        columns=_TRADE_COLUMNS,
    )
    return BacktestResult(trades=trades, metrics=calculate_metrics(trades), config=config)


def run_backtest_signals(
    frame: pd.DataFrame,
    signal: pd.Series,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Backtest an already-generated signal series."""
    config = config or BacktestConfig()
    data = _validate_frame(frame, config)
    return _run_on_validated(data, signal, config)


def run_backtest(
    frame: pd.DataFrame,
    strategy: SignalFunction,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    config = config or BacktestConfig()
    data = _validate_frame(frame, config)
    signal = strategy(data.copy())
    return _run_on_validated(data, signal, config)
