from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_REQUIRED = ["timestamp", "open", "high", "low", "close"]


@dataclass(frozen=True)
class DatasetDiagnostics:
    rows: int
    start: pd.Timestamp
    end: pd.Timestamp
    duplicate_timestamps: int
    invalid_ohlc_rows: int
    missing_intervals: int
    inferred_interval: pd.Timedelta | None
    gap_events: int
    largest_gap: pd.Timedelta | None
    weekend_spanning_gap_events: int
    weekend_spanning_missing_intervals: int
    non_weekend_missing_intervals: int
    fingerprint: str


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in _REQUIRED if c not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="raise")
    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="raise")
    return out.sort_values("timestamp", kind="stable").reset_index(drop=True)


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    canonical = frame.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%S.%f%z").encode()
    return hashlib.sha256(canonical).hexdigest()


def _gap_spans_weekend(previous: pd.Timestamp, current: pd.Timestamp) -> bool:
    """Return whether the open interval between two bars crosses Sat/Sun.

    This does not claim the gap is *valid* or entirely caused by a market
    closure. It only separates weekend-spanning gaps from gaps that cannot be
    explained by the normal 24x5 FX trading week.
    """
    start_day = previous.normalize()
    end_day = current.normalize()
    days = pd.date_range(start_day, end_day, freq="D", tz="UTC")
    return any(day.weekday() >= 5 for day in days)


def diagnose_dataset(frame: pd.DataFrame) -> DatasetDiagnostics:
    out = _normalize(frame)
    if out.empty:
        raise ValueError("dataset is empty")

    duplicate_count = int(out["timestamp"].duplicated().sum())
    invalid_high = out["high"] < out[["open", "close", "low"]].max(axis=1)
    invalid_low = out["low"] > out[["open", "close", "high"]].min(axis=1)
    invalid_count = int((invalid_high | invalid_low).sum())

    unique_ts = out.loc[~out["timestamp"].duplicated(), "timestamp"].reset_index(drop=True)
    diffs = unique_ts.diff().dropna()
    interval = diffs.mode().iloc[0] if not diffs.empty else None

    missing_intervals = 0
    gap_events = 0
    largest_gap: pd.Timedelta | None = None
    weekend_spanning_gap_events = 0
    weekend_spanning_missing_intervals = 0
    non_weekend_missing_intervals = 0

    if interval is not None and interval > pd.Timedelta(0):
        ratios = (diffs / interval).round().astype(int).clip(lower=1)
        missing_per_gap = ratios - 1
        missing_intervals = int(missing_per_gap.sum())
        gap_mask = missing_per_gap > 0
        gap_events = int(gap_mask.sum())
        if gap_events:
            largest_gap = diffs.loc[gap_mask].max()
            for diff_index in diffs.index[gap_mask]:
                missing = int(missing_per_gap.loc[diff_index])
                previous = unique_ts.iloc[int(diff_index) - 1]
                current = unique_ts.iloc[int(diff_index)]
                if _gap_spans_weekend(previous, current):
                    weekend_spanning_gap_events += 1
                    weekend_spanning_missing_intervals += missing
                else:
                    non_weekend_missing_intervals += missing

    return DatasetDiagnostics(
        rows=len(out),
        start=out["timestamp"].iloc[0],
        end=out["timestamp"].iloc[-1],
        duplicate_timestamps=duplicate_count,
        invalid_ohlc_rows=invalid_count,
        missing_intervals=missing_intervals,
        inferred_interval=interval,
        gap_events=gap_events,
        largest_gap=largest_gap,
        weekend_spanning_gap_events=weekend_spanning_gap_events,
        weekend_spanning_missing_intervals=weekend_spanning_missing_intervals,
        non_weekend_missing_intervals=non_weekend_missing_intervals,
        fingerprint=dataframe_fingerprint(out),
    )


def validate_dataset(frame: pd.DataFrame, *, allow_gaps: bool = True) -> pd.DataFrame:
    out = _normalize(frame)
    d = diagnose_dataset(out)
    if d.duplicate_timestamps:
        raise ValueError(f"dataset contains {d.duplicate_timestamps} duplicate timestamps")
    if d.invalid_ohlc_rows:
        raise ValueError(f"dataset contains {d.invalid_ohlc_rows} invalid OHLC rows")
    if not allow_gaps and d.missing_intervals:
        raise ValueError(f"dataset contains {d.missing_intervals} missing intervals")
    return out


def load_dataset(
    path: str | Path,
    *,
    allow_gaps: bool = True,
) -> tuple[pd.DataFrame, DatasetDiagnostics]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        raise ValueError("supported dataset formats are CSV and Parquet")
    validated = validate_dataset(frame, allow_gaps=allow_gaps)
    return validated, diagnose_dataset(validated)
