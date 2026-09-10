from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .experiments import ValidationGate
from .metrics import PerformanceMetrics
from .optimization import StrategyBuilder, grid_search
from .splits import chronological_split


@dataclass(frozen=True)
class ExecutionVariant:
    expiry_bars: int
    min_payout: float | None = None
    fixed_payout: float = 0.82
    payout_column: str | None = None
    entry_offset_bars: int = 1
    stake: float = 1.0

    def backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            expiry_bars=self.expiry_bars,
            entry_offset_bars=self.entry_offset_bars,
            fixed_payout=self.fixed_payout,
            payout_column=self.payout_column,
            min_payout=self.min_payout,
            stake=self.stake,
        )


@dataclass(frozen=True)
class MatrixCandidate:
    params: dict[str, Any]
    execution: ExecutionVariant
    metrics: PerformanceMetrics
    score: float


@dataclass(frozen=True)
class MatrixExperimentResult:
    best_development: MatrixCandidate | None
    validation_metrics: PerformanceMetrics | None
    test_metrics: PerformanceMetrics | None
    status: str


def grid_search_matrix(
    frame: pd.DataFrame,
    builder: StrategyBuilder,
    parameter_grid: dict[str, Iterable[Any]],
    execution_variants: Iterable[ExecutionVariant],
    *,
    objective: str = "expectancy",
    min_trades: int = 30,
) -> list[MatrixCandidate]:
    """Search strategy and execution parameters on one caller-supplied slice."""
    candidates: list[MatrixCandidate] = []
    for execution in execution_variants:
        ranked = grid_search(
            frame,
            builder,
            parameter_grid,
            config=execution.backtest_config(),
            objective=objective,
            min_trades=min_trades,
        )
        candidates.extend(
            MatrixCandidate(
                params=item.params,
                execution=execution,
                metrics=item.metrics,
                score=item.score,
            )
            for item in ranked
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def run_matrix_experiment(
    frame: pd.DataFrame,
    builder: StrategyBuilder,
    parameter_grid: dict[str, Iterable[Any]],
    execution_variants: Iterable[ExecutionVariant],
    *,
    objective: str = "expectancy",
    search_min_trades: int = 30,
    gate: ValidationGate = ValidationGate(),
) -> MatrixExperimentResult:
    """Tune strategy + expiry/payout settings without exposing the locked test."""
    split = chronological_split(frame)
    ranked = grid_search_matrix(
        split.development,
        builder,
        parameter_grid,
        execution_variants,
        objective=objective,
        min_trades=search_min_trades,
    )
    viable = [candidate for candidate in ranked if candidate.score != float("-inf")]
    if not viable:
        return MatrixExperimentResult(None, None, None, "no_development_candidate")

    best = viable[0]
    config = best.execution.backtest_config()
    strategy = builder(best.params)
    validation = run_backtest(split.validation, strategy, config).metrics
    if (
        validation.trades < gate.min_trades
        or validation.expectancy is None
        or validation.expectancy <= gate.min_expectancy
    ):
        return MatrixExperimentResult(best, validation, None, "rejected_validation")

    test = run_backtest(split.test, strategy, config).metrics
    return MatrixExperimentResult(best, validation, test, "tested")
