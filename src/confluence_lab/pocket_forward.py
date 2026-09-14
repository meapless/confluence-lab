from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from .data import dataframe_fingerprint, validate_dataset
from .ml import build_ml_features
from .payouts import break_even_win_rate
from .pocket_store import align_payouts_backward
from .v5_replication import EXPIRY_BARS, PROBABILITY_THRESHOLD

CandleTimestampSemantics = Literal["open", "close"]
ForwardDirection = Literal["call", "put", "no_trade"]
V5_POCKET_MODEL_VERSION = "v5-frozen-fxcm2014"
V5_REQUIRED_PERIOD_SECONDS = 60


@dataclass(frozen=True)
class PocketForwardScore:
    model_version: str
    asset: str
    market_type: str
    direction: ForwardDirection
    reason: str
    probability_up: float | None
    implied_win_probability: float | None
    probability_threshold: float
    expiry_bars: int
    period_seconds: int
    candle_timestamp_semantics: CandleTimestampSemantics
    source_candle_timestamp: pd.Timestamp | None
    source_candle_completed_at: pd.Timestamp | None
    decision_timestamp: pd.Timestamp
    decision_delay_seconds: float | None
    payout: float | None
    payout_observed_at: pd.Timestamp | None
    payout_age_seconds: float | None
    payout_break_even_win_rate: float | None
    probability_above_payout_break_even: bool | None
    dataset_fingerprint: str | None


def _utc(value) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _no_trade(
    *,
    asset: str,
    market_type: str,
    reason: str,
    as_of: pd.Timestamp,
    period_seconds: int,
    semantics: CandleTimestampSemantics,
    dataset_fingerprint: str | None,
    source_timestamp: pd.Timestamp | None = None,
    completed_at: pd.Timestamp | None = None,
    delay_seconds: float | None = None,
    probability_up: float | None = None,
    payout: float | None = None,
    payout_observed_at: pd.Timestamp | None = None,
    payout_age_seconds: float | None = None,
) -> PocketForwardScore:
    break_even = None if payout is None else break_even_win_rate(payout)
    return PocketForwardScore(
        model_version=V5_POCKET_MODEL_VERSION,
        asset=asset,
        market_type=market_type,
        direction="no_trade",
        reason=reason,
        probability_up=probability_up,
        implied_win_probability=None,
        probability_threshold=PROBABILITY_THRESHOLD,
        expiry_bars=EXPIRY_BARS,
        period_seconds=period_seconds,
        candle_timestamp_semantics=semantics,
        source_candle_timestamp=source_timestamp,
        source_candle_completed_at=completed_at,
        decision_timestamp=as_of,
        decision_delay_seconds=delay_seconds,
        payout=payout,
        payout_observed_at=payout_observed_at,
        payout_age_seconds=payout_age_seconds,
        payout_break_even_win_rate=break_even,
        probability_above_payout_break_even=None,
        dataset_fingerprint=dataset_fingerprint,
    )


def score_latest_completed_pocket_bar(
    fit,
    candles: pd.DataFrame,
    payouts: pd.DataFrame,
    *,
    asset: str,
    period_seconds: int,
    timestamp_semantics: CandleTimestampSemantics,
    as_of,
    max_decision_delay_seconds: int = 15,
    max_payout_age_seconds: int = 120,
) -> PocketForwardScore:
    """Score exactly one latest completed Pocket candle with frozen V5.

    This function is intentionally prospective/fail-closed:

    - V5 was trained on one-minute candles, so other periods are rejected.
    - Pocket candle timestamp semantics must be supplied explicitly rather than
      guessed from the community wrapper.
    - Features are rebuilt only through the selected completed candle, so rows
      later in the supplied snapshot cannot affect the decision.
    - A completed candle older than ``max_decision_delay_seconds`` is reported as
      NO TRADE rather than backfilled into a fake prospective signal.
    - The canonical signal timestamp is the completed candle boundary. Payout is
      aligned only from an observation at or before that boundary, making the
      signal identity deterministic even if the scorer runs a few seconds later.
      Stale/missing payout does not fabricate economics.

    The function scores research observations only; it never places a trade.
    """
    if period_seconds != V5_REQUIRED_PERIOD_SECONDS:
        raise ValueError(
            f"frozen V5 requires {V5_REQUIRED_PERIOD_SECONDS}-second candles; "
            f"got {period_seconds}"
        )
    if timestamp_semantics not in {"open", "close"}:
        raise ValueError("timestamp_semantics must be 'open' or 'close'")
    if max_decision_delay_seconds < 0:
        raise ValueError("max_decision_delay_seconds must be non-negative")
    if max_payout_age_seconds < 0:
        raise ValueError("max_payout_age_seconds must be non-negative")

    decision_at = _utc(as_of)
    market_type = "otc" if asset.lower().endswith("_otc") else "regular"
    if candles.empty:
        return _no_trade(
            asset=asset,
            market_type=market_type,
            reason="no_candles",
            as_of=decision_at,
            period_seconds=period_seconds,
            semantics=timestamp_semantics,
            dataset_fingerprint=None,
        )

    data = validate_dataset(candles.copy(), allow_gaps=True)
    if "asset" in data.columns:
        observed_assets = set(data["asset"].dropna().astype(str).unique())
        if observed_assets and observed_assets != {asset}:
            raise ValueError(
                f"candle frame asset mismatch: expected only {asset!r}, got {sorted(observed_assets)!r}"
            )
    fingerprint = dataframe_fingerprint(data)
    timestamps = pd.to_datetime(data["timestamp"], utc=True, errors="raise")
    if timestamp_semantics == "open":
        completed = timestamps + pd.to_timedelta(period_seconds, unit="s")
    else:
        completed = timestamps

    completed_positions = np.flatnonzero((completed <= decision_at).to_numpy())
    if len(completed_positions) == 0:
        return _no_trade(
            asset=asset,
            market_type=market_type,
            reason="no_completed_candle",
            as_of=decision_at,
            period_seconds=period_seconds,
            semantics=timestamp_semantics,
            dataset_fingerprint=fingerprint,
        )

    signal_position = int(completed_positions[-1])
    source_timestamp = timestamps.iloc[signal_position]
    completed_at = completed.iloc[signal_position]
    delay_seconds = float((decision_at - completed_at).total_seconds())
    if delay_seconds > max_decision_delay_seconds:
        return _no_trade(
            asset=asset,
            market_type=market_type,
            reason="completed_candle_is_stale",
            as_of=decision_at,
            period_seconds=period_seconds,
            semantics=timestamp_semantics,
            dataset_fingerprint=fingerprint,
            source_timestamp=source_timestamp,
            completed_at=completed_at,
            delay_seconds=delay_seconds,
        )

    # Cut the frame at the selected candle before feature construction. Even if
    # the input snapshot contains later/forming rows, they cannot influence V5.
    history = data.iloc[: signal_position + 1].reset_index(drop=True)
    features = build_ml_features(history)
    latest_features = features.iloc[-1]
    if latest_features.isna().any() or not np.isfinite(latest_features.to_numpy(dtype=float)).all():
        return _no_trade(
            asset=asset,
            market_type=market_type,
            reason="insufficient_causal_feature_history",
            as_of=decision_at,
            period_seconds=period_seconds,
            semantics=timestamp_semantics,
            dataset_fingerprint=fingerprint,
            source_timestamp=source_timestamp,
            completed_at=completed_at,
            delay_seconds=delay_seconds,
        )

    probability_up = float(fit.model.predict_proba(features.iloc[[-1]])[0, 1])
    if not 0.0 <= probability_up <= 1.0:
        raise ValueError(f"model returned invalid probability {probability_up!r}")

    if probability_up >= PROBABILITY_THRESHOLD:
        direction: ForwardDirection = "call"
        implied_win_probability = probability_up
    elif probability_up <= 1.0 - PROBABILITY_THRESHOLD:
        direction = "put"
        implied_win_probability = 1.0 - probability_up
    else:
        return _no_trade(
            asset=asset,
            market_type=market_type,
            reason="frozen_probability_threshold_not_cleared",
            as_of=decision_at,
            period_seconds=period_seconds,
            semantics=timestamp_semantics,
            dataset_fingerprint=fingerprint,
            source_timestamp=source_timestamp,
            completed_at=completed_at,
            delay_seconds=delay_seconds,
            probability_up=probability_up,
        )

    # Anchor payout evidence to the canonical signal boundary, not to the wall
    # clock moment this function happened to execute. That allows the same market
    # event to map to one deterministic forward candidate later.
    event = pd.DataFrame({"signal_timestamp": [completed_at]})
    aligned = align_payouts_backward(
        event,
        payouts,
        asset=asset,
        event_time_column="signal_timestamp",
        max_age_seconds=max_payout_age_seconds,
    ).iloc[0]

    payout_value = None if pd.isna(aligned["payout"]) else float(aligned["payout"])
    payout_at = (
        None
        if pd.isna(aligned["payout_observed_at"])
        else _utc(aligned["payout_observed_at"])
    )
    payout_age = (
        None
        if pd.isna(aligned["payout_age_seconds"])
        else float(aligned["payout_age_seconds"])
    )
    break_even = None if payout_value is None else break_even_win_rate(payout_value)
    above_break_even = (
        None if break_even is None else bool(implied_win_probability > break_even)
    )

    reason = "frozen_signal_with_fresh_payout" if payout_value is not None else "frozen_signal_without_fresh_payout"
    return PocketForwardScore(
        model_version=V5_POCKET_MODEL_VERSION,
        asset=asset,
        market_type=market_type,
        direction=direction,
        reason=reason,
        probability_up=probability_up,
        implied_win_probability=float(implied_win_probability),
        probability_threshold=PROBABILITY_THRESHOLD,
        expiry_bars=EXPIRY_BARS,
        period_seconds=period_seconds,
        candle_timestamp_semantics=timestamp_semantics,
        source_candle_timestamp=source_timestamp,
        source_candle_completed_at=completed_at,
        decision_timestamp=decision_at,
        decision_delay_seconds=delay_seconds,
        payout=payout_value,
        payout_observed_at=payout_at,
        payout_age_seconds=payout_age,
        payout_break_even_win_rate=break_even,
        probability_above_payout_break_even=above_break_even,
        dataset_fingerprint=fingerprint,
    )
