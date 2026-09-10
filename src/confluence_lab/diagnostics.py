from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import pandas as pd

from .metrics import calculate_metrics


def enrich_trades_with_signal_context(
    trades: pd.DataFrame,
    context: pd.DataFrame,
    *,
    context_columns: Iterable[str] = (
        "utc_window",
        "utc_hour",
        "utc_weekday",
        "atr_percentile_100",
        "htf_5_trend",
        "htf_15_trend",
    ),
) -> pd.DataFrame:
    """Attach signal-time context to an already-settled trade ledger.

    The join is exact on ``signal_timestamp``. This function does not generate,
    filter, or re-settle trades; it exists only for post-hoc diagnostics and
    therefore cannot change the primary result.
    """
    if "signal_timestamp" not in trades.columns:
        raise ValueError("trades must contain signal_timestamp")
    if "timestamp" not in context.columns:
        raise ValueError("context must contain timestamp")

    requested = tuple(context_columns)
    missing = set(requested) - set(context.columns)
    if missing:
        raise ValueError(f"context missing requested columns: {sorted(missing)}")

    left = trades.copy()
    right = context[["timestamp", *requested]].copy()
    left["signal_timestamp"] = pd.to_datetime(
        left["signal_timestamp"], utc=True, errors="raise"
    )
    right["timestamp"] = pd.to_datetime(right["timestamp"], utc=True, errors="raise")
    if right["timestamp"].duplicated().any():
        raise ValueError("context timestamps must be unique")

    enriched = left.merge(
        right,
        how="left",
        left_on="signal_timestamp",
        right_on="timestamp",
        validate="many_to_one",
    ).drop(columns=["timestamp"])
    return enriched


def add_fixed_volatility_bucket(
    trades: pd.DataFrame,
    *,
    source_column: str = "atr_percentile_100",
    target_column: str = "volatility_bucket",
) -> pd.DataFrame:
    """Bucket a trailing ATR percentile into fixed, non-data-mined quartiles."""
    if source_column not in trades.columns:
        raise ValueError(f"missing volatility source column {source_column!r}")
    out = trades.copy()
    values = pd.to_numeric(out[source_column], errors="coerce")
    out[target_column] = pd.cut(
        values,
        bins=[-float("inf"), 0.25, 0.50, 0.75, float("inf")],
        labels=["q1_low", "q2", "q3", "q4_high"],
        include_lowest=True,
        right=True,
    )
    return out


def performance_breakdown(
    trades: pd.DataFrame,
    by: str | Iterable[str],
    *,
    min_trades: int = 1,
) -> pd.DataFrame:
    """Summarize fixed historical trades by one or more diagnostic dimensions."""
    if min_trades < 1:
        raise ValueError("min_trades must be >= 1")
    columns = [by] if isinstance(by, str) else list(by)
    if not columns:
        raise ValueError("at least one grouping column is required")
    missing = set(columns) - set(trades.columns)
    if missing:
        raise ValueError(f"trades missing grouping columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    grouped = trades.groupby(columns, dropna=False, observed=True, sort=True)
    for key, subset in grouped:
        if len(subset) < min_trades:
            continue
        values = key if isinstance(key, tuple) else (key,)
        row = {column: value for column, value in zip(columns, values, strict=True)}
        row.update(asdict(calculate_metrics(subset)))
        rows.append(row)
    return pd.DataFrame.from_records(rows)
