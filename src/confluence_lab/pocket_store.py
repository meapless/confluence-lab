from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from .data import dataframe_fingerprint, validate_dataset


@dataclass(frozen=True)
class PocketSnapshotManifestEntry:
    snapshot_id: str
    asset: str
    period_seconds: int
    observed_at: str
    account_mode: str
    relative_path: str
    rows: int
    candle_fingerprint: str
    start: str | None
    end: str | None


def _utc_timestamp(value) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="raise")


def make_snapshot_manifest_entry(
    frame: pd.DataFrame,
    *,
    asset: str,
    period_seconds: int,
    observed_at,
    account_mode: str,
    relative_path: str,
) -> PocketSnapshotManifestEntry:
    if period_seconds < 1:
        raise ValueError("period_seconds must be positive")
    if account_mode not in {"demo", "live"}:
        raise ValueError("account_mode must be demo or live")
    data = validate_dataset(frame, allow_gaps=True)
    fingerprint = dataframe_fingerprint(data)
    observed = _utc_timestamp(observed_at)
    material = "|".join(
        [asset, str(period_seconds), observed.isoformat(), account_mode, fingerprint, relative_path]
    )
    snapshot_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return PocketSnapshotManifestEntry(
        snapshot_id=snapshot_id,
        asset=asset,
        period_seconds=period_seconds,
        observed_at=observed.isoformat(),
        account_mode=account_mode,
        relative_path=relative_path,
        rows=len(data),
        candle_fingerprint=fingerprint,
        start=data["timestamp"].iloc[0].isoformat() if len(data) else None,
        end=data["timestamp"].iloc[-1].isoformat() if len(data) else None,
    )


def append_snapshot_manifest(
    path: str | Path,
    entry: PocketSnapshotManifestEntry,
) -> None:
    """Append one immutable snapshot record, refusing duplicate snapshot IDs."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            existing = json.loads(line)
            if existing.get("snapshot_id") == entry.snapshot_id:
                raise ValueError(f"snapshot {entry.snapshot_id} already exists in manifest")
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")


def consolidate_pocket_frames(
    frames: Iterable[pd.DataFrame],
    *,
    conflict_policy: str = "raise",
) -> pd.DataFrame:
    """Combine overlapping Pocket candle snapshots without double-counting.

    Identical duplicate timestamps are collapsed. If two snapshots disagree on
    OHLC for the same timestamp, the default is to raise rather than silently
    rewrite history. ``prefer_last`` exists only for explicit repair workflows.
    """
    pieces = [frame.copy() for frame in frames]
    if not pieces:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
    if conflict_policy not in {"raise", "prefer_last"}:
        raise ValueError("conflict_policy must be raise or prefer_last")

    data = pd.concat(pieces, ignore_index=True)
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="raise")
    required = ["timestamp", "open", "high", "low", "close"]
    missing = set(required) - set(data.columns)
    if missing:
        raise ValueError(f"snapshot data missing columns: {sorted(missing)}")

    compare_columns = ["open", "high", "low", "close"]
    duplicate_groups = data.loc[data["timestamp"].duplicated(keep=False)].groupby(
        "timestamp", sort=False
    )
    conflicts: list[pd.Timestamp] = []
    for timestamp, group in duplicate_groups:
        if len(group[compare_columns].drop_duplicates()) > 1:
            conflicts.append(timestamp)
    if conflicts and conflict_policy == "raise":
        preview = ", ".join(str(value) for value in conflicts[:5])
        raise ValueError(
            f"conflicting OHLC values for {len(conflicts)} duplicate timestamps; examples: {preview}"
        )

    keep = "last" if conflict_policy == "prefer_last" else "first"
    deduplicated = (
        data.sort_values("timestamp", kind="stable")
        .drop_duplicates(subset=["timestamp"], keep=keep)
        .reset_index(drop=True)
    )
    return validate_dataset(deduplicated, allow_gaps=True)


def normalize_payout_observations(records: Iterable[dict[str, object]]) -> pd.DataFrame:
    rows = list(records)
    if not rows:
        return pd.DataFrame(columns=["asset", "observed_at", "payout", "account_mode"])
    frame = pd.DataFrame.from_records(rows)
    required = {"asset", "observed_at", "payout"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"payout observations missing columns: {sorted(missing)}")
    frame["observed_at"] = pd.to_datetime(frame["observed_at"], utc=True, errors="raise")
    frame["payout"] = pd.to_numeric(frame["payout"], errors="raise").astype(float)
    if ((frame["payout"] < 0) | (frame["payout"] > 1)).any():
        raise ValueError("payout observations must be decimal returns between 0 and 1")
    return frame.sort_values(["asset", "observed_at"], kind="stable").reset_index(drop=True)


def load_payout_jsonl(path: str | Path) -> pd.DataFrame:
    target = Path(path)
    if not target.exists():
        return normalize_payout_observations([])
    records = [
        json.loads(line)
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return normalize_payout_observations(records)


def align_payouts_backward(
    events: pd.DataFrame,
    payouts: pd.DataFrame,
    *,
    asset: str,
    event_time_column: str = "timestamp",
    max_age_seconds: int = 120,
) -> pd.DataFrame:
    """Attach only the latest payout observed at or before each event.

    A future payout observation is never used. Observations older than
    ``max_age_seconds`` are discarded so stale economics cannot be presented as
    contemporaneous broker payout data.
    """
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    if event_time_column not in events.columns:
        raise ValueError(f"events missing {event_time_column!r}")

    left = events.copy()
    left[event_time_column] = pd.to_datetime(left[event_time_column], utc=True, errors="raise")
    right = normalize_payout_observations(payouts.to_dict(orient="records"))
    right = right.loc[right["asset"].eq(asset)].copy()

    left = left.sort_values(event_time_column, kind="stable").reset_index(drop=True)
    if right.empty:
        left["payout"] = pd.NA
        left["payout_observed_at"] = pd.NaT
        left["payout_age_seconds"] = pd.NA
        return left

    right = right.rename(columns={"observed_at": "payout_observed_at"})
    aligned = pd.merge_asof(
        left,
        right[["payout_observed_at", "payout"]].sort_values("payout_observed_at"),
        left_on=event_time_column,
        right_on="payout_observed_at",
        direction="backward",
        tolerance=pd.Timedelta(seconds=max_age_seconds),
        allow_exact_matches=True,
    )
    aligned["payout_age_seconds"] = (
        aligned[event_time_column] - aligned["payout_observed_at"]
    ).dt.total_seconds()
    return aligned


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
