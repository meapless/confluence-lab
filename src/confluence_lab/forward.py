from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .registry import append_experiment_record, read_registry, verify_registry

Direction = Literal["call", "put"]


@dataclass(frozen=True)
class ForwardCandidate:
    candidate_id: str
    model_version: str
    asset: str
    market_type: str
    signal_timestamp: pd.Timestamp
    direction: Direction
    probability: float
    probability_threshold: float
    expiry_bars: int
    entry_offset_bars: int
    payout: float | None
    payout_observed_at: pd.Timestamp | None
    dataset_fingerprint: str | None = None


@dataclass(frozen=True)
class ForwardOutcome:
    candidate_id: str
    entry_timestamp: pd.Timestamp
    expiry_timestamp: pd.Timestamp
    entry_price: float
    exit_price: float
    result: Literal["win", "loss", "tie"]
    pnl: float | None


def _utc(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def candidate_id_for(
    *,
    model_version: str,
    asset: str,
    market_type: str,
    signal_timestamp: Any,
    direction: Direction,
    expiry_bars: int,
    entry_offset_bars: int,
    probability_threshold: float,
) -> str:
    """Return a deterministic identifier for one prospective signal decision."""
    payload = {
        "model_version": str(model_version),
        "asset": str(asset),
        "market_type": str(market_type),
        "signal_timestamp": _utc(signal_timestamp).isoformat(),
        "direction": direction,
        "expiry_bars": int(expiry_bars),
        "entry_offset_bars": int(entry_offset_bars),
        "probability_threshold": float(probability_threshold),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _events(path: str | Path) -> list[dict[str, Any]]:
    if not verify_registry(path):
        raise ValueError("forward-test ledger hash chain is invalid")
    return read_registry(path)


def append_forward_candidate(
    path: str | Path,
    *,
    model_version: str,
    asset: str,
    market_type: str,
    signal_timestamp: Any,
    direction: Direction,
    probability: float,
    probability_threshold: float,
    expiry_bars: int,
    entry_offset_bars: int = 1,
    payout: float | None = None,
    payout_observed_at: Any | None = None,
    dataset_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Append a signal-time decision before its outcome is known.

    Outcomes are separate immutable ledger events. Existing candidates are never
    edited or deleted, which makes retrospective signal rewriting detectable.
    """
    if direction not in {"call", "put"}:
        raise ValueError("direction must be call or put")
    if not 0.5 < probability_threshold < 1.0:
        raise ValueError("probability_threshold must be in (0.5, 1)")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    if expiry_bars < 1 or entry_offset_bars < 1:
        raise ValueError("expiry_bars and entry_offset_bars must be positive")
    if direction == "call" and probability < probability_threshold:
        raise ValueError("call probability does not clear the frozen threshold")
    if direction == "put" and probability > 1.0 - probability_threshold:
        raise ValueError("put probability does not clear the frozen threshold")
    if payout is not None and not 0.0 <= payout <= 1.0:
        raise ValueError("payout must be a decimal in [0, 1]")

    signal_at = _utc(signal_timestamp)
    payout_at = _utc(payout_observed_at) if payout_observed_at is not None else None
    if payout_at is not None and payout_at > signal_at:
        raise ValueError("future payout observation cannot be attached to a candidate")

    candidate_id = candidate_id_for(
        model_version=model_version,
        asset=asset,
        market_type=market_type,
        signal_timestamp=signal_at,
        direction=direction,
        expiry_bars=expiry_bars,
        entry_offset_bars=entry_offset_bars,
        probability_threshold=probability_threshold,
    )
    existing = _events(path)
    if any(
        record.get("event_type") == "candidate"
        and record.get("candidate_id") == candidate_id
        for record in existing
    ):
        raise ValueError(f"candidate {candidate_id} already exists")

    return append_experiment_record(
        path,
        {
            "event_type": "candidate",
            "candidate_id": candidate_id,
            "model_version": model_version,
            "asset": asset,
            "market_type": market_type,
            "signal_timestamp": signal_at.isoformat(),
            "direction": direction,
            "probability": float(probability),
            "probability_threshold": float(probability_threshold),
            "expiry_bars": int(expiry_bars),
            "entry_offset_bars": int(entry_offset_bars),
            "payout": None if payout is None else float(payout),
            "payout_observed_at": None if payout_at is None else payout_at.isoformat(),
            "dataset_fingerprint": dataset_fingerprint,
            "outcome_known_at_append": False,
        },
    )


def append_forward_outcome(
    path: str | Path,
    *,
    candidate_id: str,
    entry_timestamp: Any,
    expiry_timestamp: Any,
    entry_price: float,
    exit_price: float,
    result: Literal["win", "loss", "tie"],
    pnl: float | None,
) -> dict[str, Any]:
    """Append exactly one immutable settlement event for a prior candidate."""
    events = _events(path)
    candidates = [
        record
        for record in events
        if record.get("event_type") == "candidate"
        and record.get("candidate_id") == candidate_id
    ]
    if len(candidates) != 1:
        raise ValueError("candidate_id must refer to exactly one prior candidate")
    if any(
        record.get("event_type") == "outcome"
        and record.get("candidate_id") == candidate_id
        for record in events
    ):
        raise ValueError(f"candidate {candidate_id} is already settled")
    if result not in {"win", "loss", "tie"}:
        raise ValueError("result must be win, loss, or tie")

    candidate = candidates[0]
    signal_at = _utc(candidate["signal_timestamp"])
    entry_at = _utc(entry_timestamp)
    expiry_at = _utc(expiry_timestamp)
    if entry_at <= signal_at:
        raise ValueError("entry_timestamp must be after signal_timestamp")
    if expiry_at < entry_at:
        raise ValueError("expiry_timestamp must not precede entry_timestamp")

    if result == "win" and pnl is not None and pnl <= 0:
        raise ValueError("win pnl must be positive when supplied")
    if result == "loss" and pnl is not None and pnl >= 0:
        raise ValueError("loss pnl must be negative when supplied")
    if result == "tie" and pnl is not None and pnl != 0:
        raise ValueError("tie pnl must be zero when supplied")

    return append_experiment_record(
        path,
        {
            "event_type": "outcome",
            "candidate_id": candidate_id,
            "entry_timestamp": entry_at.isoformat(),
            "expiry_timestamp": expiry_at.isoformat(),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "result": result,
            "pnl": None if pnl is None else float(pnl),
        },
    )


def forward_ledger_frame(path: str | Path) -> pd.DataFrame:
    """Return candidates joined to their optional later outcomes."""
    events = _events(path)
    candidates = pd.DataFrame(
        [record for record in events if record.get("event_type") == "candidate"]
    )
    if candidates.empty:
        return candidates
    outcomes = pd.DataFrame(
        [record for record in events if record.get("event_type") == "outcome"]
    )
    drop_hash_fields = ["run_id", "recorded_at", "previous_hash", "record_hash", "event_type"]
    base = candidates.drop(columns=[column for column in drop_hash_fields if column in candidates])
    if outcomes.empty:
        base["settled"] = False
        return base
    outcomes = outcomes.drop(
        columns=[column for column in drop_hash_fields if column in outcomes],
    )
    rename = {column: f"outcome_{column}" for column in outcomes.columns if column != "candidate_id"}
    outcomes = outcomes.rename(columns=rename)
    joined = base.merge(outcomes, how="left", on="candidate_id", validate="one_to_one")
    joined["settled"] = joined["outcome_result"].notna()
    return joined
