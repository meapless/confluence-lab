from __future__ import annotations

from dataclasses import asdict, replace
from typing import Iterable

import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .metrics import calculate_metrics
from .strategies import SignalFunction


def payout_sensitivity(
    trades: pd.DataFrame,
    payouts: Iterable[float] = (0.70, 0.75, 0.80, 0.82, 0.85, 0.90, 0.92),
) -> pd.DataFrame:
    """Reprice an already-settled win/loss/tie sequence at fixed payouts.

    This changes economics only; it does not change which historical trades
    won or lost. It is therefore useful for asking how much payout compression
    a candidate can tolerate before its observed expectancy becomes negative.
    """
    required = {"result"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"trades missing columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    for payout in payouts:
        payout = float(payout)
        if not 0 <= payout <= 10:
            raise ValueError("payouts must be decimal returns")
        repriced = trades.copy()
        repriced["pnl"] = 0.0
        repriced.loc[repriced["result"] == "win", "pnl"] = payout
        repriced.loc[repriced["result"] == "loss", "pnl"] = -1.0
        metrics = calculate_metrics(repriced)
        rows.append(
            {
                "payout": payout,
                "break_even_win_rate": 1.0 / (1.0 + payout),
                **asdict(metrics),
            }
        )
    return pd.DataFrame.from_records(rows)


def execution_sensitivity(
    frame: pd.DataFrame,
    strategy: SignalFunction,
    base_config: BacktestConfig,
    *,
    entry_offsets: Iterable[int] = (1, 2),
    overlap_modes: Iterable[bool] = (True, False),
    cooldowns: Iterable[int] = (0, 1, 2),
) -> pd.DataFrame:
    """Stress a fixed strategy under execution-delay and dependence assumptions."""
    rows: list[dict[str, object]] = []
    for entry_offset in entry_offsets:
        for allow_overlap in overlap_modes:
            relevant_cooldowns = (0,) if allow_overlap else tuple(cooldowns)
            for cooldown in relevant_cooldowns:
                config = replace(
                    base_config,
                    entry_offset_bars=int(entry_offset),
                    allow_overlapping_positions=bool(allow_overlap),
                    cooldown_bars=int(cooldown),
                )
                result = run_backtest(frame, strategy, config)
                rows.append(
                    {
                        "entry_offset_bars": config.entry_offset_bars,
                        "allow_overlapping_positions": config.allow_overlapping_positions,
                        "cooldown_bars": config.cooldown_bars,
                        **asdict(result.metrics),
                    }
                )
    return pd.DataFrame.from_records(rows)


def performance_by_direction(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    if "direction" not in trades.columns:
        raise ValueError("trades missing direction column")
    rows: list[dict[str, object]] = []
    for direction, label in ((1, "call"), (-1, "put")):
        subset = trades.loc[trades["direction"] == direction].copy()
        rows.append({"direction": label, **asdict(calculate_metrics(subset))})
    return pd.DataFrame.from_records(rows)


def performance_by_period(
    trades: pd.DataFrame,
    *,
    frequency: str = "ME",
) -> pd.DataFrame:
    """Report stability by entry-time period without changing strategy rules."""
    if trades.empty:
        return pd.DataFrame()
    if "entry_timestamp" not in trades.columns:
        raise ValueError("trades missing entry_timestamp column")
    frame = trades.copy()
    frame["entry_timestamp"] = pd.to_datetime(frame["entry_timestamp"], utc=True)
    frame["period"] = frame["entry_timestamp"].dt.to_period(frequency)
    rows: list[dict[str, object]] = []
    for period, subset in frame.groupby("period", sort=True):
        rows.append({"period": str(period), **asdict(calculate_metrics(subset))})
    return pd.DataFrame.from_records(rows)
