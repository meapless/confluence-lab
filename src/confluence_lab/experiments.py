from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .metrics import PerformanceMetrics
from .optimization import CandidateResult, StrategyBuilder, grid_search
from .splits import chronological_split


@dataclass(frozen=True)
class ValidationGate:
    min_trades: int = 30
    min_expectancy: float = 0.0
    min_locked_test_trades: int = 30


@dataclass(frozen=True)
class ExperimentResult:
    best_development: CandidateResult | None
    validation_metrics: PerformanceMetrics | None
    test_metrics: PerformanceMetrics | None
    status: str


def run_research_experiment(
    frame: pd.DataFrame,
    builder: StrategyBuilder,
    parameter_grid: dict[str, list[Any]],
    *,
    config: BacktestConfig | None = None,
    objective: str = "expectancy",
    search_min_trades: int = 30,
    gate: ValidationGate = ValidationGate(),
) -> ExperimentResult:
    """Run a gated development -> validation -> locked-test experiment.

    Parameter search sees development data only. The locked test is executed
    only after the selected development candidate passes the validation gate.
    """
    config = config or BacktestConfig()
    split = chronological_split(frame)

    ranked = grid_search(
        split.development,
        builder,
        parameter_grid,
        config=config,
        objective=objective,
        min_trades=search_min_trades,
    )
    viable = [candidate for candidate in ranked if candidate.score != float("-inf")]
    if not viable:
        return ExperimentResult(None, None, None, "no_development_candidate")

    best = viable[0]
    strategy = builder(best.params)
    validation_metrics = run_backtest(split.validation, strategy, config).metrics

    if (
        validation_metrics.trades < gate.min_trades
        or validation_metrics.expectancy is None
        or validation_metrics.expectancy <= gate.min_expectancy
    ):
        return ExperimentResult(best, validation_metrics, None, "rejected_validation")

    test_metrics = run_backtest(split.test, strategy, config).metrics
    if test_metrics.trades < gate.min_locked_test_trades:
        return ExperimentResult(
            best,
            validation_metrics,
            test_metrics,
            "insufficient_locked_test",
        )
    return ExperimentResult(best, validation_metrics, test_metrics, "tested")
