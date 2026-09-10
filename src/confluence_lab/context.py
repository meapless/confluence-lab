from __future__ import annotations

from math import ceil

import numpy as np
import pandas as pd

from .indicators import add_core_features, atr, ema, rolling_percentile_rank


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in frame.columns:
        raise ValueError("frame must contain a timestamp column")
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="raise")
    return out.sort_values("timestamp", kind="stable").reset_index(drop=True)


def add_utc_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic UTC calendar context without claiming exchange sessions.

    Fixed UTC windows are intentionally used instead of labels such as London or
    New York because daylight-saving transitions would otherwise introduce
    ambiguous session definitions.
    """
    out = frame.copy()
    timestamps = pd.to_datetime(out["timestamp"], utc=True, errors="raise")
    out["utc_hour"] = timestamps.dt.hour.astype("int8")
    out["utc_weekday"] = timestamps.dt.weekday.astype("int8")
    out["utc_liquid_core"] = out["utc_hour"].between(7, 16)

    labels = pd.Series("21_23", index=out.index, dtype="object")
    labels.loc[out["utc_hour"].between(0, 6)] = "00_06"
    labels.loc[out["utc_hour"].between(7, 11)] = "07_11"
    labels.loc[out["utc_hour"].between(12, 16)] = "12_16"
    labels.loc[out["utc_hour"].between(17, 20)] = "17_20"
    out["utc_window"] = labels
    return out


def completed_htf_features(
    frame: pd.DataFrame,
    *,
    minutes: int = 15,
    ema_fast: int = 4,
    ema_slow: int = 12,
    minimum_coverage: float = 0.80,
) -> pd.DataFrame:
    """Map features from the previous completed higher-timeframe bar.

    Every base row inside a higher-timeframe bucket receives features from the
    immediately preceding bucket. The current incomplete HTF bar is never used,
    which prevents lookahead leakage when a 1-minute strategy consults 5/15m
    context.
    """
    if minutes < 2:
        raise ValueError("minutes must be >= 2")
    if ema_fast < 1 or ema_slow <= ema_fast:
        raise ValueError("require 1 <= ema_fast < ema_slow")
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be in (0, 1]")

    data = _ordered(frame)
    indexed = data.set_index("timestamp")
    rule = f"{minutes}min"

    htf = indexed.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        base_rows=("close", "count"),
    )
    htf["coverage"] = htf["base_rows"] / float(minutes)
    minimum_rows = max(1, ceil(minutes * minimum_coverage))
    valid_bar = htf["base_rows"].ge(minimum_rows)

    htf["ema_fast"] = ema(htf["close"], ema_fast)
    htf["ema_slow"] = ema(htf["close"], ema_slow)
    htf["ema_slow_slope"] = htf["ema_slow"].diff()
    htf["return_1"] = htf["close"].pct_change()

    trend = pd.Series(0, index=htf.index, dtype="int8")
    bull = htf["ema_fast"].gt(htf["ema_slow"]) & htf["ema_slow_slope"].gt(0)
    bear = htf["ema_fast"].lt(htf["ema_slow"]) & htf["ema_slow_slope"].lt(0)
    trend.loc[bull] = 1
    trend.loc[bear] = -1
    htf["trend"] = trend

    feature_columns = [
        "open",
        "high",
        "low",
        "close",
        "coverage",
        "ema_fast",
        "ema_slow",
        "ema_slow_slope",
        "return_1",
        "trend",
    ]
    completed = htf[feature_columns].where(valid_bar, np.nan).shift(1)
    buckets = data["timestamp"].dt.floor(rule)
    prefix = f"htf_{minutes}_"

    result = pd.DataFrame(index=data.index)
    for column in feature_columns:
        result[f"{prefix}{column}"] = buckets.map(completed[column])
    return result


def add_volatility_structure_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Add trailing-only volatility and price-location context."""
    out = add_core_features(frame)
    out["atr_5"] = atr(out, 5)
    out["atr_50"] = atr(out, 50)
    out["atr_ratio_5_50"] = out["atr_5"] / out["atr_50"].replace(0.0, np.nan)

    out["bb_width_fraction"] = (
        (out["bb_upper"] - out["bb_lower"]) / out["close"].replace(0.0, np.nan)
    )
    out["bb_width_percentile_200"] = rolling_percentile_rank(
        out["bb_width_fraction"], 200
    )

    previous_high = out["high"].rolling(20, min_periods=20).max().shift(1)
    previous_low = out["low"].rolling(20, min_periods=20).min().shift(1)
    width = (previous_high - previous_low).replace(0.0, np.nan)
    out["prior_high_20"] = previous_high
    out["prior_low_20"] = previous_low
    out["range_position_20"] = (out["close"] - previous_low) / width
    return out


def add_research_context(
    frame: pd.DataFrame,
    *,
    htf_minutes: tuple[int, ...] = (5, 15),
) -> pd.DataFrame:
    """Build the V2 research feature frame once for parameter-grid evaluation."""
    data = _ordered(frame)
    out = add_volatility_structure_context(data)
    out = add_utc_context(out)
    for minutes in htf_minutes:
        htf = completed_htf_features(data, minutes=minutes)
        out = out.join(htf)
    return out
