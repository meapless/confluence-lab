from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .context import add_research_context
from .strategies import SignalFunction


def _htf_column(minutes: int, name: str) -> str:
    return f"htf_{minutes}_{name}"


@dataclass(frozen=True)
class HtfAlignedPullbackParams:
    htf_minutes: int = 15
    adx_min: float = 20.0
    ema_distance_atr: float = 0.50
    rsi_trigger: float = 50.0
    atr_pct_max: float = 0.90

    def __post_init__(self) -> None:
        if self.htf_minutes not in {5, 15}:
            raise ValueError("htf_minutes must be 5 or 15")
        if self.adx_min < 0:
            raise ValueError("adx_min must be non-negative")
        if self.ema_distance_atr < 0:
            raise ValueError("ema_distance_atr must be non-negative")
        if not 50 <= self.rsi_trigger < 100:
            raise ValueError("rsi_trigger must be in [50, 100)")
        if not 0 < self.atr_pct_max <= 1:
            raise ValueError("atr_pct_max must be in (0, 1]")


def htf_aligned_pullback_from_features(
    features: pd.DataFrame,
    params: HtfAlignedPullbackParams = HtfAlignedPullbackParams(),
) -> pd.Series:
    """Pullback recovery that requires independent completed-HTF trend agreement."""
    signal = pd.Series(0, index=features.index, dtype="int8")
    htf_trend = features[_htf_column(params.htf_minutes, "trend")]
    htf_close = features[_htf_column(params.htf_minutes, "close")]
    htf_slow = features[_htf_column(params.htf_minutes, "ema_slow")]

    common = (
        features["adx_14"].ge(params.adx_min)
        & features["atr_percentile_100"].le(params.atr_pct_max)
        & features["distance_ema20_atr"].abs().le(params.ema_distance_atr)
    )

    bull = (
        common
        & htf_trend.eq(1)
        & htf_close.gt(htf_slow)
        & features["ema_20"].gt(features["ema_50"])
        & features["ema_50_slope"].gt(0)
        & features["rsi_14"].gt(params.rsi_trigger)
        & features["rsi_14"].shift(1).le(params.rsi_trigger)
        & features["macd_hist"].gt(features["macd_hist"].shift(1))
    )

    bearish_trigger = 100.0 - params.rsi_trigger
    bear = (
        common
        & htf_trend.eq(-1)
        & htf_close.lt(htf_slow)
        & features["ema_20"].lt(features["ema_50"])
        & features["ema_50_slope"].lt(0)
        & features["rsi_14"].lt(bearish_trigger)
        & features["rsi_14"].shift(1).ge(bearish_trigger)
        & features["macd_hist"].lt(features["macd_hist"].shift(1))
    )

    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def htf_aligned_pullback(
    frame: pd.DataFrame,
    params: HtfAlignedPullbackParams = HtfAlignedPullbackParams(),
) -> pd.Series:
    return htf_aligned_pullback_from_features(add_research_context(frame), params)


def prepare_htf_aligned_pullback(frame: pd.DataFrame):
    features = add_research_context(frame)

    def prepared(params: dict[str, Any]) -> pd.Series:
        return htf_aligned_pullback_from_features(
            features, HtfAlignedPullbackParams(**params)
        )

    return prepared


def build_htf_aligned_pullback(params: dict[str, Any]) -> SignalFunction:
    config = HtfAlignedPullbackParams(**params)
    return lambda frame: htf_aligned_pullback(frame, config)


@dataclass(frozen=True)
class CompressionBreakoutParams:
    htf_minutes: int = 15
    lookback: int = 20
    compression_max: float = 0.20
    body_min: float = 0.50
    atr_expansion_min: float = 1.0

    def __post_init__(self) -> None:
        if self.htf_minutes not in {5, 15}:
            raise ValueError("htf_minutes must be 5 or 15")
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")
        if not 0 < self.compression_max <= 1:
            raise ValueError("compression_max must be in (0, 1]")
        if not 0 <= self.body_min <= 1:
            raise ValueError("body_min must be between 0 and 1")
        if self.atr_expansion_min <= 0:
            raise ValueError("atr_expansion_min must be positive")


def compression_breakout_from_features(
    features: pd.DataFrame,
    params: CompressionBreakoutParams = CompressionBreakoutParams(),
) -> pd.Series:
    """Close-confirmed breakout following prior low-volatility compression.

    Compression is inspected on the previous bar; breakout boundaries use only
    prior highs/lows; HTF direction comes from a previously completed HTF bar.
    """
    signal = pd.Series(0, index=features.index, dtype="int8")
    previous_high = (
        features["high"]
        .rolling(params.lookback, min_periods=params.lookback)
        .max()
        .shift(1)
    )
    previous_low = (
        features["low"]
        .rolling(params.lookback, min_periods=params.lookback)
        .min()
        .shift(1)
    )
    htf_trend = features[_htf_column(params.htf_minutes, "trend")]
    compressed = features["bb_width_percentile_200"].shift(1).le(
        params.compression_max
    )
    common = (
        compressed
        & features["candle_body_ratio"].ge(params.body_min)
        & features["atr_ratio_5_50"].ge(params.atr_expansion_min)
    )

    bull = common & htf_trend.eq(1) & features["close"].gt(previous_high)
    bear = common & htf_trend.eq(-1) & features["close"].lt(previous_low)
    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def compression_breakout(
    frame: pd.DataFrame,
    params: CompressionBreakoutParams = CompressionBreakoutParams(),
) -> pd.Series:
    return compression_breakout_from_features(add_research_context(frame), params)


def prepare_compression_breakout(frame: pd.DataFrame):
    features = add_research_context(frame)

    def prepared(params: dict[str, Any]) -> pd.Series:
        return compression_breakout_from_features(
            features, CompressionBreakoutParams(**params)
        )

    return prepared


def build_compression_breakout(params: dict[str, Any]) -> SignalFunction:
    config = CompressionBreakoutParams(**params)
    return lambda frame: compression_breakout(frame, config)


@dataclass(frozen=True)
class SweepReversalParams:
    lookback: int = 20
    wick_min: float = 0.50
    rsi_edge: float = 60.0
    overshoot_atr: float = 0.0
    liquid_core_only: bool = False

    def __post_init__(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")
        if not 0 <= self.wick_min <= 1:
            raise ValueError("wick_min must be between 0 and 1")
        if not 50 < self.rsi_edge < 100:
            raise ValueError("rsi_edge must be in (50, 100)")
        if self.overshoot_atr < 0:
            raise ValueError("overshoot_atr must be non-negative")


def sweep_reversal_from_features(
    features: pd.DataFrame,
    params: SweepReversalParams = SweepReversalParams(),
) -> pd.Series:
    """Fade a failed prior-range breakout that closes back inside structure."""
    signal = pd.Series(0, index=features.index, dtype="int8")
    previous_high = (
        features["high"]
        .rolling(params.lookback, min_periods=params.lookback)
        .max()
        .shift(1)
    )
    previous_low = (
        features["low"]
        .rolling(params.lookback, min_periods=params.lookback)
        .min()
        .shift(1)
    )
    prior_atr = features["atr_14"].shift(1)
    overshoot = params.overshoot_atr * prior_atr
    common = prior_atr.gt(0)
    if params.liquid_core_only:
        common &= features["utc_liquid_core"]

    lower_rsi = 100.0 - params.rsi_edge
    bull = (
        common
        & features["low"].lt(previous_low - overshoot)
        & features["close"].gt(previous_low)
        & features["close"].gt(features["open"])
        & features["lower_wick_ratio"].ge(params.wick_min)
        & features["rsi_14"].le(lower_rsi)
    )
    bear = (
        common
        & features["high"].gt(previous_high + overshoot)
        & features["close"].lt(previous_high)
        & features["close"].lt(features["open"])
        & features["upper_wick_ratio"].ge(params.wick_min)
        & features["rsi_14"].ge(params.rsi_edge)
    )

    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def sweep_reversal(
    frame: pd.DataFrame,
    params: SweepReversalParams = SweepReversalParams(),
) -> pd.Series:
    return sweep_reversal_from_features(add_research_context(frame), params)


def prepare_sweep_reversal(frame: pd.DataFrame):
    features = add_research_context(frame)

    def prepared(params: dict[str, Any]) -> pd.Series:
        return sweep_reversal_from_features(features, SweepReversalParams(**params))

    return prepared


def build_sweep_reversal(params: dict[str, Any]) -> SignalFunction:
    config = SweepReversalParams(**params)
    return lambda frame: sweep_reversal(frame, config)
