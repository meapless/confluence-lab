from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd

from .backtest import BacktestConfig, _run_on_validated, _validate_frame, run_backtest
from .experiments import ValidationGate, passes_validation_gate
from .metrics import PerformanceMetrics
from .optimization import StrategyBuilder, iter_parameter_grid, score_metrics
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
    prepared_factory: Callable[
        [pd.DataFrame], Callable[[dict[str, Any]], pd.Series]
    ] | None = None,
) -> list[MatrixCandidate]:
    """Search strategy + execution settings on one caller-supplied slice.

    A strategy signal series is calculated once per strategy parameter set and
    reused across expiry/payout variants. Execution settings cannot influence
    the historical signal itself.
    """
    variants = list(execution_variants)
    if not variants:
        return []

    data = _validate_frame(frame, variants[0].backtest_config())
    candidates: list[MatrixCandidate] = []
    prepared = prepared_factory(data.copy()) if prepared_factory is not None else None

    for params in iter_parameter_grid(parameter_grid):
        signal = prepared(params) if prepared is not None else builder(params)(data.copy())
        for execution in variants:
            result = _run_on_validated(data, signal, execution.backtest_config())
            score = score_metrics(
                result.metrics,
                objective=objective,
                min_trades=min_trades,
            )
            candidates.append(
                MatrixCandidate(
                    params=params,
                    execution=execution,
                    metrics=result.metrics,
                    score=score,
                )
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
    prepared_factory: Callable[
        [pd.DataFrame], Callable[[dict[str, Any]], pd.Series]
    ] | None = None,
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
        prepared_factory=prepared_factory,
    )
    viable = [candidate for candidate in ranked if candidate.score != float("-inf")]
    if not viable:
        return MatrixExperimentResult(None, None, None, "no_development_candidate")

    best = viable[0]
    config = best.execution.backtest_config()
    strategy = builder(best.params)
    validation = run_backtest(split.validation, strategy, config).metrics
    if not passes_validation_gate(validation, gate):
        return MatrixExperimentResult(best, validation, None, "rejected_validation")

    test = run_backtest(split.test, strategy, config).metrics
    if test.trades < gate.min_locked_test_trades:
        return MatrixExperimentResult(
            best,
            validation,
            test,
            "insufficient_locked_test",
        )
    return MatrixExperimentResult(best, validation, test, "tested")
