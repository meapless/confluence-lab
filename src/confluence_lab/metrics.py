from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    trades: int
    wins: int
    losses: int
    ties: int
    win_rate: float | None
    wilson_low: float | None
    wilson_high: float | None
    expectancy: float | None
    total_pnl: float
    max_drawdown: float
    max_losing_streak: int
    max_winning_streak: int


def wilson_interval(wins: int, resolved: int, z: float = 1.959963984540054) -> tuple[float, float] | tuple[None, None]:
    if resolved <= 0:
        return None, None
    p = wins / resolved
    denominator = 1 + z * z / resolved
    center = (p + z * z / (2 * resolved)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * resolved)) / resolved) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _max_streak(results: pd.Series, target: str) -> int:
    best = current = 0
    for value in results:
        if value == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def calculate_metrics(trades: pd.DataFrame) -> PerformanceMetrics:
    if trades.empty:
        return PerformanceMetrics(0, 0, 0, 0, None, None, None, None, 0.0, 0.0, 0, 0)
    wins = int((trades["result"] == "win").sum())
    losses = int((trades["result"] == "loss").sum())
    ties = int((trades["result"] == "tie").sum())
    resolved = wins + losses
    win_rate = wins / resolved if resolved else None
    low, high = wilson_interval(wins, resolved)
    total_pnl = float(trades["pnl"].sum())
    expectancy = float(trades["pnl"].mean())
    equity = trades["pnl"].cumsum()
    running_peak = equity.cummax().clip(lower=0.0)
    drawdown = running_peak - equity
    return PerformanceMetrics(
        trades=len(trades), wins=wins, losses=losses, ties=ties,
        win_rate=win_rate, wilson_low=low, wilson_high=high,
        expectancy=expectancy, total_pnl=total_pnl,
        max_drawdown=float(drawdown.max()),
        max_losing_streak=_max_streak(trades["result"], "loss"),
        max_winning_streak=_max_streak(trades["result"], "win"),
    )
