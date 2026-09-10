from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .metrics import PerformanceMetrics, calculate_metrics
from .payouts import TiePolicy, break_even_win_rate, settle_binary_trade
from .strategies import SignalFunction

_REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close"}


@dataclass(frozen=True)
class BacktestConfig:
    expiry_bars: int = 1
    entry_offset_bars: int = 1
    fixed_payout: float = 0.82
    payout_column: str | None = None
    stake: float = 1.0
    tie_policy: TiePolicy = TiePolicy.REFUND

    def __post_init__(self) -> None:
        if self.expiry_bars < 1:
            raise ValueError("expiry_bars must be >= 1")
        if self.entry_offset_bars < 1:
            raise ValueError("entry_offset_bars must be >= 1 to avoid same-bar execution assumptions")


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
    if ordered["timestamp"].duplicated().any():
        raise ValueError("duplicate timestamps are not allowed")
    if (ordered["high"] < ordered[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid OHLC row: high is below another price")
    if (ordered["low"] > ordered[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid OHLC row: low is above another price")
    return ordered


def run_backtest(frame: pd.DataFrame, strategy: SignalFunction, config: BacktestConfig | None = None) -> BacktestResult:
    config = config or BacktestConfig()
    data = _validate_frame(frame, config)
    signal = strategy(data.copy())
    if not signal.index.equals(data.index):
        signal = signal.reindex(data.index)
    records: list[dict[str, object]] = []
    for signal_index, direction_value in signal.items():
        if pd.isna(direction_value):
            continue
        direction = int(direction_value)
        if direction == 0:
            continue
        if direction not in (-1, 1):
            raise ValueError("strategy produced direction outside {-1, 0, 1}")
        entry_index = int(signal_index) + config.entry_offset_bars
        exit_index = entry_index + config.expiry_bars - 1
        if entry_index >= len(data) or exit_index >= len(data):
            continue
        entry = data.iloc[entry_index]
        exit_row = data.iloc[exit_index]
        payout = float(entry[config.payout_column]) if config.payout_column else config.fixed_payout
        result, pnl = settle_binary_trade(
            direction=direction,
            entry_price=float(entry["open"]),
            exit_price=float(exit_row["close"]),
            payout=payout,
            stake=config.stake,
            tie_policy=config.tie_policy,
        )
        records.append({
            "signal_timestamp": data.iloc[int(signal_index)]["timestamp"],
            "entry_timestamp": entry["timestamp"],
            "exit_timestamp": exit_row["timestamp"],
            "direction": direction,
            "entry_price": float(entry["open"]),
            "exit_price": float(exit_row["close"]),
            "payout": payout,
            "break_even_win_rate": break_even_win_rate(payout),
            "result": result,
            "pnl": pnl,
        })
    trades = pd.DataFrame.from_records(records)
    if trades.empty:
        trades = pd.DataFrame(columns=[
            "signal_timestamp", "entry_timestamp", "exit_timestamp", "direction",
            "entry_price", "exit_price", "payout", "break_even_win_rate", "result", "pnl",
        ])
    return BacktestResult(trades=trades, metrics=calculate_metrics(trades), config=config)
