from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestResult
from .data import dataframe_fingerprint
from .ml import ML_FEATURE_COLUMNS, prepare_ml_data
from .ml_experiment import evidence_gate, evaluate_model_slice
from .ml_v5 import make_histgb_classifier

TRAIN_YEAR = 2014
REPLICATION_YEAR = 2015
SYMBOL = "EURUSD"
EXPECTED_TRAIN_FINGERPRINT = (
    "3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71"
)
EXPIRY_BARS = 3
ENTRY_OFFSET_BARS = 1
PROBABILITY_THRESHOLD = 0.625
FIXED_PAYOUT = 0.82
MINIMUM_REPLICATION_RESOLVED_TRADES = 150


@dataclass(frozen=True)
class FrozenV5Fit:
    model: object
    training_rows: int
    labeled_training_rows: int
    class_zero_rows: int
    class_one_rows: int
    feature_columns: tuple[str, ...]
    training_fingerprint: str


def fit_frozen_v5(training_frame: pd.DataFrame) -> FrozenV5Fit:
    """Fit the preregistered V5 model once on the complete 2014 training year.

    The source fingerprint is checked before fitting. Any upstream revision to
    the 2014 archive therefore stops the replication rather than silently
    changing the model that will be evaluated on 2015.
    """
    observed_fingerprint = dataframe_fingerprint(training_frame)
    if observed_fingerprint != EXPECTED_TRAIN_FINGERPRINT:
        raise ValueError(
            "2014 training fingerprint mismatch: expected "
            f"{EXPECTED_TRAIN_FINGERPRINT}, got {observed_fingerprint}"
        )

    prepared = prepare_ml_data(
        training_frame,
        expiry_bars=EXPIRY_BARS,
        entry_offset_bars=ENTRY_OFFSET_BARS,
    )
    valid = prepared.eligible_features.to_numpy() & prepared.target_up.notna().to_numpy()
    positions = np.flatnonzero(valid)
    if len(positions) < 200:
        raise ValueError("not enough valid labeled 2014 observations to fit frozen V5")

    target = prepared.target_up.iloc[positions].astype(int)
    if target.nunique() != 2:
        raise ValueError("2014 frozen V5 training target must contain both classes")

    model = make_histgb_classifier()
    model.fit(prepared.features.iloc[positions], target)

    return FrozenV5Fit(
        model=model,
        training_rows=len(training_frame),
        labeled_training_rows=len(positions),
        class_zero_rows=int((target == 0).sum()),
        class_one_rows=int((target == 1).sum()),
        feature_columns=tuple(ML_FEATURE_COLUMNS),
        training_fingerprint=observed_fingerprint,
    )


def evaluate_frozen_v5(
    fit: FrozenV5Fit,
    replication_frame: pd.DataFrame,
    *,
    fixed_payout: float = FIXED_PAYOUT,
    entry_offset_bars: int = ENTRY_OFFSET_BARS,
    allow_overlapping_positions: bool = True,
    cooldown_bars: int = 0,
) -> BacktestResult:
    """Evaluate the frozen 2014-fitted V5 model on an untouched frame."""
    return evaluate_model_slice(
        fit.model,
        replication_frame,
        threshold=PROBABILITY_THRESHOLD,
        expiry_bars=EXPIRY_BARS,
        fixed_payout=fixed_payout,
        entry_offset_bars=entry_offset_bars,
        allow_overlapping_positions=allow_overlapping_positions,
        cooldown_bars=cooldown_bars,
    )


def primary_replication_pass(result: BacktestResult) -> bool:
    """Apply the exact preregistered 2015 primary replication gate."""
    return evidence_gate(
        result,
        minimum_resolved_trades=MINIMUM_REPLICATION_RESOLVED_TRADES,
        fixed_payout=FIXED_PAYOUT,
    )
