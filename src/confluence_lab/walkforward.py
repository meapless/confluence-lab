from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .optimization import StrategyBuilder, grid_search


@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int
    test_bars: int
    step_bars: int | None = None
    min_trades: int = 20
    objective: str = "expectancy"

    def __post_init__(self) -> None:
        if self.train_bars < 1 or self.test_bars < 1:
            raise ValueError("train_bars and test_bars must be positive")
        if self.step_bars is not None and self.step_bars < 1:
            raise ValueError("step_bars must be positive")


def walk_forward(
    frame: pd.DataFrame,
    builder: StrategyBuilder,
    parameter_grid: dict[str, list[Any]],
    *,
    backtest_config: BacktestConfig | None = None,
    config: WalkForwardConfig,
) -> pd.DataFrame:
    """Optimize on each historical train window and score only the next window."""
    data = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    step = config.step_bars or config.test_bars
    backtest_config = backtest_config or BacktestConfig()
    rows: list[dict[str, object]] = []

    train_start = 0
    train_end = config.train_bars
    while train_end + config.test_bars <= len(data):
        test_end = train_end + config.test_bars
        train = data.iloc[train_start:train_end].copy()
        test = data.iloc[train_end:test_end].copy()

        ranked = grid_search(
            train,
            builder,
            parameter_grid,
            config=backtest_config,
            objective=config.objective,
            min_trades=config.min_trades,
        )
        viable = [candidate for candidate in ranked if candidate.score != float("-inf")]
        if viable:
            best = viable[0]
            metrics = run_backtest(test, builder(best.params), backtest_config).metrics
            rows.append(
                {
                    "train_start": train["timestamp"].iloc[0],
                    "train_end": train["timestamp"].iloc[-1],
                    "test_start": test["timestamp"].iloc[0],
                    "test_end": test["timestamp"].iloc[-1],
                    "params": best.params,
                    "train_score": best.score,
                    "test_trades": metrics.trades,
                    "test_win_rate": metrics.win_rate,
                    "test_expectancy": metrics.expectancy,
                    "test_pnl": metrics.total_pnl,
                    "test_max_drawdown": metrics.max_drawdown,
                }
            )

        train_start += step
        train_end += step

    return pd.DataFrame(rows)
