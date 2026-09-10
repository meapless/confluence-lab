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


def diagnose_dataset(frame: pd.DataFrame) -> DatasetDiagnostics:
    out = _normalize(frame)
    duplicate_count = int(out["timestamp"].duplicated().sum())
    invalid_high = out["high"] < out[["open", "close", "low"]].max(axis=1)
    invalid_low = out["low"] > out[["open", "close", "high"]].min(axis=1)
    invalid_count = int((invalid_high | invalid_low).sum())
    unique_ts = out.loc[~out["timestamp"].duplicated(), "timestamp"]
    diffs = unique_ts.diff().dropna()
    interval = diffs.mode().iloc[0] if not diffs.empty else None
    missing_intervals = 0
    if interval is not None and interval > pd.Timedelta(0):
        ratios = (diffs / interval).round().astype(int)
        missing_intervals = int((ratios.clip(lower=1) - 1).sum())
    return DatasetDiagnostics(
        rows=len(out), start=out["timestamp"].iloc[0], end=out["timestamp"].iloc[-1],
        duplicate_timestamps=duplicate_count, invalid_ohlc_rows=invalid_count,
        missing_intervals=missing_intervals, inferred_interval=interval,
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


def load_dataset(path: str | Path, *, allow_gaps: bool = True) -> tuple[pd.DataFrame, DatasetDiagnostics]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        raise ValueError("supported dataset formats are CSV and Parquet")
    validated = validate_dataset(frame, allow_gaps=allow_gaps)
    return validated, diagnose_dataset(validated)
