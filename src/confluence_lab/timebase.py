from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _timestamps_utc(values: Iterable[object] | pd.Series | pd.Index) -> pd.Series:
    return pd.Series(pd.to_datetime(values, utc=True, errors="raise")).reset_index(drop=True)


def infer_bar_interval(values: Iterable[object] | pd.Series | pd.Index) -> pd.Timedelta | None:
    """Infer the dominant positive spacing between ordered candle timestamps.

    The smallest mode is selected when two spacings tie. This is intended for
    fixed-timeframe candle series (for example M1 data) that may contain normal
    market closures or sparse missing bars. Long closures therefore do not
    become the inferred bar interval.
    """
    timestamps = _timestamps_utc(values)
    if len(timestamps) < 2:
        return None

    diffs = timestamps.diff().dropna()
    diffs = diffs.loc[diffs > pd.Timedelta(0)]
    if diffs.empty:
        return None

    counts = diffs.value_counts()
    max_count = int(counts.max())
    modes = counts.loc[counts.eq(max_count)].index
    return min(pd.Timedelta(value) for value in modes)


def contiguous_horizon_mask(
    values: Iterable[object] | pd.Series | pd.Index,
    start_indices: np.ndarray,
    end_indices: np.ndarray,
    *,
    expected_interval: pd.Timedelta | str | None = None,
) -> np.ndarray:
    """Return whether every candle step from start through end is contiguous.

    A candidate spanning indices ``start`` to ``end`` is eligible only when all
    intervening timestamp differences equal the expected candle interval. This
    prevents an N-bar expiry from silently crossing weekends, market closures,
    or missing-candle gaps and turning into an hours/days-long holding period.
    """
    starts = np.asarray(start_indices, dtype=int)
    ends = np.asarray(end_indices, dtype=int)
    if starts.shape != ends.shape:
        raise ValueError("start_indices and end_indices must have the same shape")
    if starts.ndim != 1:
        raise ValueError("start_indices and end_indices must be one-dimensional")
    if not len(starts):
        return np.zeros(0, dtype=bool)

    timestamps = _timestamps_utc(values)
    if (starts < 0).any() or (ends < 0).any():
        raise ValueError("horizon indices must be non-negative")
    if (ends < starts).any():
        raise ValueError("end index cannot precede start index")
    if (ends >= len(timestamps)).any():
        raise ValueError("horizon index exceeds timestamp series")

    interval = (
        pd.Timedelta(expected_interval)
        if expected_interval is not None
        else infer_bar_interval(timestamps)
    )
    if interval is None:
        return starts == ends
    if interval <= pd.Timedelta(0):
        raise ValueError("expected_interval must be positive")

    # Compare Timedelta values directly instead of integer datetime storage.
    # Pandas may store datetimes internally at different resolutions across
    # versions, while Timedelta equality remains unit-safe.
    good_step = timestamps.diff().iloc[1:].eq(interval).to_numpy(dtype=bool)
    bad_prefix = np.concatenate(
        [np.array([0], dtype=int), np.cumsum(~good_step, dtype=int)]
    )
    return (bad_prefix[ends] - bad_prefix[starts]) == 0
