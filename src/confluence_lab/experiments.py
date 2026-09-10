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
    min_wilson_low: float | None = None

    def __post_init__(self) -> None:
        if self.min_trades < 1:
            raise ValueError("min_trades must be >= 1")
        if self.min_locked_test_trades < 1:
            raise ValueError("min_locked_test_trades must be >= 1")
        if self.min_wilson_low is not None and not 0 <= self.min_wilson_low <= 1:
            raise ValueError("min_wilson_low must be between 0 and 1")


def passes_validation_gate(metrics: PerformanceMetrics, gate: ValidationGate) -> bool:
    """Return True only when validation evidence clears every configured gate.

    ``min_wilson_low`` is useful when a single fixed payout implies a single
    break-even win rate. Leave it unset for variable-payout datasets, where
    payout-aware P&L uncertainty should be assessed directly instead.
    """
    if metrics.trades < gate.min_trades:
        return False
    if metrics.expectancy is None or metrics.expectancy <= gate.min_expectancy:
        return False
    if gate.min_wilson_low is not None:
        if metrics.wilson_low is None or metrics.wilson_low <= gate.min_wilson_low:
            return False
    return True


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
    search_min_expectancy: float | None = None,
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
        min_expectancy=search_min_expectancy,
    )
    viable = [candidate for candidate in ranked if candidate.score != float("-inf")]
    if not viable:
        return ExperimentResult(None, None, None, "no_development_candidate")

    best = viable[0]
    strategy = builder(best.params)
    validation_metrics = run_backtest(split.validation, strategy, config).metrics

    if not passes_validation_gate(validation_metrics, gate):
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
