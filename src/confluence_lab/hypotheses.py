from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import add_core_features
from .strategies import SignalFunction


@dataclass(frozen=True)
class RangeReversionParams:
    adx_max: float = 20.0
    rsi_lower: float = 30.0
    rsi_upper: float = 70.0
    band_buffer_atr: float = 0.10
    atr_pct_max: float = 0.80

    def __post_init__(self) -> None:
        if self.rsi_lower >= self.rsi_upper:
            raise ValueError("rsi_lower must be below rsi_upper")
        if self.band_buffer_atr < 0:
            raise ValueError("band_buffer_atr must be non-negative")
        if not 0 < self.atr_pct_max <= 1:
            raise ValueError("atr_pct_max must be in (0, 1]")


def range_reversion_from_features(
    features: pd.DataFrame,
    params: RangeReversionParams = RangeReversionParams(),
) -> pd.Series:
    """Mean-reversion hypothesis for quiet/ranging conditions."""
    signal = pd.Series(0, index=features.index, dtype="int8")
    common = (
        features["adx_14"].le(params.adx_max)
        & features["atr_percentile_100"].le(params.atr_pct_max)
        & features["atr_14"].gt(0)
    )
    lower_threshold = features["bb_lower"] + params.band_buffer_atr * features["atr_14"]
    upper_threshold = features["bb_upper"] - params.band_buffer_atr * features["atr_14"]
    bull = common & features["close"].le(lower_threshold) & features["rsi_14"].le(params.rsi_lower)
    bear = common & features["close"].ge(upper_threshold) & features["rsi_14"].ge(params.rsi_upper)
    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def range_reversion(
    frame: pd.DataFrame,
    params: RangeReversionParams = RangeReversionParams(),
) -> pd.Series:
    return range_reversion_from_features(add_core_features(frame), params)


def prepare_range_reversion(frame: pd.DataFrame):
    features = add_core_features(frame)

    def prepared(params: dict[str, float]) -> pd.Series:
        return range_reversion_from_features(features, RangeReversionParams(**params))

    return prepared


def build_range_reversion(params: dict[str, float]) -> SignalFunction:
    config = RangeReversionParams(**params)
    return lambda frame: range_reversion(frame, config)


@dataclass(frozen=True)
class BreakoutParams:
    lookback: int = 20
    adx_min: float = 20.0
    body_min: float = 0.50
    atr_pct_min: float = 0.40
    trend_filter: bool = True

    def __post_init__(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")
        if not 0 <= self.body_min <= 1:
            raise ValueError("body_min must be between 0 and 1")
        if not 0 <= self.atr_pct_min <= 1:
            raise ValueError("atr_pct_min must be between 0 and 1")


def breakout_from_features(
    features: pd.DataFrame,
    params: BreakoutParams = BreakoutParams(),
) -> pd.Series:
    """Close-confirmed breakout using prior-only range boundaries."""
    signal = pd.Series(0, index=features.index, dtype="int8")
    previous_high = features["high"].rolling(
        params.lookback, min_periods=params.lookback
    ).max().shift(1)
    previous_low = features["low"].rolling(
        params.lookback, min_periods=params.lookback
    ).min().shift(1)
    common = (
        features["adx_14"].ge(params.adx_min)
        & features["atr_percentile_100"].ge(params.atr_pct_min)
        & features["candle_body_ratio"].ge(params.body_min)
    )
    bull = common & features["close"].gt(previous_high) & features["macd_hist"].gt(0)
    bear = common & features["close"].lt(previous_low) & features["macd_hist"].lt(0)
    if params.trend_filter:
        bull &= features["ema_20"].gt(features["ema_50"])
        bear &= features["ema_20"].lt(features["ema_50"])
    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def breakout(
    frame: pd.DataFrame,
    params: BreakoutParams = BreakoutParams(),
) -> pd.Series:
    return breakout_from_features(add_core_features(frame), params)


def prepare_breakout(frame: pd.DataFrame):
    features = add_core_features(frame)

    def prepared(params: dict[str, object]) -> pd.Series:
        return breakout_from_features(features, BreakoutParams(**params))

    return prepared


def build_breakout(params: dict[str, object]) -> SignalFunction:
    config = BreakoutParams(**params)
    return lambda frame: breakout(frame, config)
