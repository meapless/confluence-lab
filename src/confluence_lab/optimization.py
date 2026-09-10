from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Iterable

import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .metrics import PerformanceMetrics
from .strategies import SignalFunction

StrategyBuilder = Callable[[dict[str, Any]], SignalFunction]


@dataclass(frozen=True)
class CandidateResult:
    params: dict[str, Any]
    metrics: PerformanceMetrics
    score: float


def iter_parameter_grid(grid: dict[str, Iterable[Any]]):
    """Yield the Cartesian product of a parameter grid deterministically."""
    keys = list(grid)
    for values in product(*(list(grid[key]) for key in keys)):
        yield dict(zip(keys, values, strict=True))


def score_metrics(
    metrics: PerformanceMetrics,
    *,
    objective: str = "expectancy",
    min_trades: int = 30,
    min_expectancy: float | None = None,
) -> float:
    """Score a backtest while enforcing minimum evidence constraints."""
    if metrics.trades < min_trades:
        return float("-inf")
    if min_expectancy is not None:
        if metrics.expectancy is None or metrics.expectancy <= min_expectancy:
            return float("-inf")
    if objective == "expectancy":
        return float(metrics.expectancy) if metrics.expectancy is not None else float("-inf")
    if objective == "win_rate":
        return float(metrics.win_rate) if metrics.win_rate is not None else float("-inf")
    if objective == "wilson_low":
        return float(metrics.wilson_low) if metrics.wilson_low is not None else float("-inf")
    raise ValueError(f"unknown objective: {objective}")


def grid_search(
    frame: pd.DataFrame,
    builder: StrategyBuilder,
    parameter_grid: dict[str, Iterable[Any]],
    *,
    config: BacktestConfig | None = None,
    objective: str = "expectancy",
    min_trades: int = 30,
    min_expectancy: float | None = None,
) -> list[CandidateResult]:
    """Search only the frame supplied by the caller.

    The research pipeline passes development data here explicitly. This
    function intentionally has no concept of validation or locked-test data.
    """
    config = config or BacktestConfig()
    candidates: list[CandidateResult] = []
    for params in iter_parameter_grid(parameter_grid):
        result = run_backtest(frame, builder(params), config)
        score = score_metrics(
            result.metrics,
            objective=objective,
            min_trades=min_trades,
            min_expectancy=min_expectancy,
        )
        candidates.append(CandidateResult(params=params, metrics=result.metrics, score=score))
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
