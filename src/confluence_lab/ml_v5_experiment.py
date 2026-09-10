from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .backtest import BacktestResult
from .ml import DEFAULT_PROBABILITY_THRESHOLDS
from .ml_experiment import evidence_gate, evaluate_model_slice
from .ml_v5 import HistGBResearchResult, fit_histgb_research_baseline
from .splits import chronological_split


@dataclass(frozen=True)
class HistGBExpirySearchResult:
    expiry_bars: int
    research: HistGBResearchResult


@dataclass(frozen=True)
class HistGBCandidate:
    expiry_bars: int
    threshold: float
    development: BacktestResult
    research: HistGBResearchResult

    @property
    def score(self) -> float:
        value = self.development.metrics.wilson_low
        return float(value) if value is not None else float("-inf")


@dataclass(frozen=True)
class HistGBExperimentResult:
    status: str
    candidate: HistGBCandidate | None
    validation: BacktestResult | None
    locked_test: BacktestResult | None
    development_candidates: tuple[HistGBCandidate, ...]
    development_searches: tuple[HistGBExpirySearchResult, ...]


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()


def run_histgb_experiment(
    frame: pd.DataFrame,
    *,
    expiries: Iterable[int] = (1, 2, 3, 5),
    thresholds: Iterable[float] = DEFAULT_PROBABILITY_THRESHOLDS,
    fixed_payout: float = 0.82,
    development_oof_splits: int = 5,
    minimum_development_trades: int = 300,
    minimum_validation_resolved_trades: int = 150,
    minimum_locked_resolved_trades: int = 150,
) -> HistGBExperimentResult:
    """Run preregistered V5 development -> validation -> locked-test discipline."""
    split = chronological_split(_ordered(frame))
    development = _ordered(split.development)
    validation_frame = _ordered(split.validation)
    locked_frame = _ordered(split.test)

    candidates: list[HistGBCandidate] = []
    searches: list[HistGBExpirySearchResult] = []
    frozen_thresholds = tuple(float(value) for value in thresholds)

    for expiry in tuple(int(value) for value in expiries):
        research = fit_histgb_research_baseline(
            development,
            expiry_bars=expiry,
            fixed_payout=fixed_payout,
            thresholds=frozen_thresholds,
            n_splits=development_oof_splits,
            min_oof_trades=minimum_development_trades,
        )
        searches.append(HistGBExpirySearchResult(expiry_bars=expiry, research=research))
        if research.selected_threshold is None or research.development_oof_result is None:
            continue
        candidates.append(
            HistGBCandidate(
                expiry_bars=expiry,
                threshold=research.selected_threshold,
                development=research.development_oof_result,
                research=research,
            )
        )

    if not candidates:
        return HistGBExperimentResult(
            status="no_development_candidate",
            candidate=None,
            validation=None,
            locked_test=None,
            development_candidates=(),
            development_searches=tuple(searches),
        )

    # Preregistered order: highest Wilson lower bound, then lower expiry, then
    # higher probability threshold.
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
        return HistGBExperimentResult(
            status="rejected_validation",
            candidate=selected,
            validation=validation,
            locked_test=None,
            development_candidates=tuple(candidates),
            development_searches=tuple(searches),
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
    return HistGBExperimentResult(
        status="passed_locked" if locked_pass else "failed_locked",
        candidate=selected,
        validation=validation,
        locked_test=locked,
        development_candidates=tuple(candidates),
        development_searches=tuple(searches),
    )
