from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .backtest import BacktestConfig, BacktestResult, run_backtest_signals
from .ml import (
    DEFAULT_PROBABILITY_THRESHOLDS,
    LogisticResearchResult,
    fit_logistic_research_baseline,
    predict_probabilities,
    probability_to_signal,
)
from .payouts import break_even_win_rate
from .splits import chronological_split


@dataclass(frozen=True)
class MLCandidate:
    expiry_bars: int
    threshold: float
    development: BacktestResult
    research: LogisticResearchResult

    @property
    def score(self) -> float:
        value = self.development.metrics.wilson_low
        return float(value) if value is not None else float("-inf")


@dataclass(frozen=True)
class MLExperimentResult:
    status: str
    candidate: MLCandidate | None
    validation: BacktestResult | None
    locked_test: BacktestResult | None
    development_candidates: tuple[MLCandidate, ...]


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()


def resolved_trades(result: BacktestResult) -> int:
    return int(result.metrics.wins + result.metrics.losses)


def evidence_gate(
    result: BacktestResult,
    *,
    minimum_resolved_trades: int,
    fixed_payout: float,
) -> bool:
    """Require sample size, positive economics and Wilson lower > break-even."""
    if minimum_resolved_trades < 1:
        raise ValueError("minimum_resolved_trades must be positive")
    metrics = result.metrics
    threshold = break_even_win_rate(fixed_payout)
    return bool(
        resolved_trades(result) >= minimum_resolved_trades
        and metrics.expectancy is not None
        and metrics.expectancy > 0.0
        and metrics.wilson_low is not None
        and metrics.wilson_low > threshold
    )


def evaluate_model_slice(
    model,
    frame: pd.DataFrame,
    *,
    threshold: float,
    expiry_bars: int,
    fixed_payout: float,
    entry_offset_bars: int = 1,
    allow_overlapping_positions: bool = True,
    cooldown_bars: int = 0,
) -> BacktestResult:
    """Evaluate a fixed fitted model/threshold without fitting on the slice."""
    data = _ordered(frame)
    probabilities = predict_probabilities(model, data)
    signal = probability_to_signal(probabilities, threshold=threshold, index=data.index)
    return run_backtest_signals(
        data,
        signal,
        BacktestConfig(
            expiry_bars=expiry_bars,
            entry_offset_bars=entry_offset_bars,
            fixed_payout=fixed_payout,
            allow_overlapping_positions=allow_overlapping_positions,
            cooldown_bars=cooldown_bars,
        ),
    )


def run_logistic_experiment(
    frame: pd.DataFrame,
    *,
    expiries: Iterable[int] = (1, 2, 3, 5),
    thresholds: Iterable[float] = DEFAULT_PROBABILITY_THRESHOLDS,
    fixed_payout: float = 0.82,
    development_oof_splits: int = 5,
    minimum_development_trades: int = 300,
    minimum_validation_resolved_trades: int = 150,
    minimum_locked_resolved_trades: int = 150,
) -> MLExperimentResult:
    """Run V4 development -> validation -> locked-test discipline.

    Development threshold selection uses only OOF probabilities. One candidate
    is frozen across expiry/threshold choices. Validation and locked slices are
    prediction-only: the selected development-fitted model is never retrained.
    """
    split = chronological_split(_ordered(frame))
    development = _ordered(split.development)
    validation_frame = _ordered(split.validation)
    locked_frame = _ordered(split.test)

    candidates: list[MLCandidate] = []
    for expiry in tuple(int(value) for value in expiries):
        research = fit_logistic_research_baseline(
            development,
            expiry_bars=expiry,
            fixed_payout=fixed_payout,
            thresholds=tuple(float(value) for value in thresholds),
            n_splits=development_oof_splits,
            min_oof_trades=minimum_development_trades,
        )
        if research.selected_threshold is None or research.development_oof_result is None:
            continue
        candidates.append(
            MLCandidate(
                expiry_bars=expiry,
                threshold=research.selected_threshold,
                development=research.development_oof_result,
                research=research,
            )
        )

    if not candidates:
        return MLExperimentResult(
            status="no_development_candidate",
            candidate=None,
            validation=None,
            locked_test=None,
            development_candidates=(),
        )

    # Highest Wilson lower bound wins. Exact ties: lower expiry, then higher
    # confidence threshold, matching the preregistration.
    candidates.sort(
        key=lambda item: (item.score, -item.expiry_bars, item.threshold),
        reverse=True,
    )
    selected = candidates[0]

    validation = evaluate_model_slice(
        selected.research.model,
        validation_frame,
        threshold=selected.threshold,
        expiry_bars=selected.expiry_bars,
        fixed_payout=fixed_payout,
    )
    if not evidence_gate(
        validation,
        minimum_resolved_trades=minimum_validation_resolved_trades,
        fixed_payout=fixed_payout,
    ):
        return MLExperimentResult(
            status="rejected_validation",
            candidate=selected,
            validation=validation,
            locked_test=None,
            development_candidates=tuple(candidates),
        )

    locked = evaluate_model_slice(
        selected.research.model,
        locked_frame,
        threshold=selected.threshold,
        expiry_bars=selected.expiry_bars,
        fixed_payout=fixed_payout,
    )
    locked_pass = evidence_gate(
        locked,
        minimum_resolved_trades=minimum_locked_resolved_trades,
        fixed_payout=fixed_payout,
    )
    return MLExperimentResult(
        status="passed_locked" if locked_pass else "failed_locked",
        candidate=selected,
        validation=validation,
        locked_test=locked,
        development_candidates=tuple(candidates),
    )
