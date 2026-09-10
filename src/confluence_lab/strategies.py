from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import add_core_features, ema, rsi

SignalFunction = Callable[[pd.DataFrame], pd.Series]


def always_call(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(1, index=frame.index, dtype="int8")


def always_put(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(-1, index=frame.index, dtype="int8")


def random_baseline(frame: pd.DataFrame, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.choice([-1, 1], size=len(frame)), index=frame.index, dtype="int8")


def ema_crossover(frame: pd.DataFrame, fast: int = 10, slow: int = 30) -> pd.Series:
    fast_ema = ema(frame["close"], fast)
    slow_ema = ema(frame["close"], slow)
    bull = (fast_ema > slow_ema) & (fast_ema.shift(1) <= slow_ema.shift(1))
    bear = (fast_ema < slow_ema) & (fast_ema.shift(1) >= slow_ema.shift(1))
    signal = pd.Series(0, index=frame.index, dtype="int8")
    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def rsi_reversal(
    frame: pd.DataFrame,
    period: int = 14,
    lower: float = 30,
    upper: float = 70,
) -> pd.Series:
    values = rsi(frame["close"], period)
    signal = pd.Series(0, index=frame.index, dtype="int8")
    signal.loc[(values > lower) & (values.shift(1) <= lower)] = 1
    signal.loc[(values < upper) & (values.shift(1) >= upper)] = -1
    return signal


@dataclass(frozen=True)
class TrendPullbackParams:
    adx_min: float = 20.0
    atr_pct_min: float = 0.15
    atr_pct_max: float = 0.90
    ema_distance_atr: float = 0.45
    rsi_trigger: float = 50.0

    def __post_init__(self) -> None:
        if self.atr_pct_min >= self.atr_pct_max:
            raise ValueError("atr_pct_min must be below atr_pct_max")
        if not 0 < self.rsi_trigger < 100:
            raise ValueError("rsi_trigger must be between 0 and 100")


def trend_pullback_from_features(
    features: pd.DataFrame,
    params: TrendPullbackParams = TrendPullbackParams(),
) -> pd.Series:
    signal = pd.Series(0, index=features.index, dtype="int8")
    common = (
        features["adx_14"].ge(params.adx_min)
        & features["atr_percentile_100"].between(params.atr_pct_min, params.atr_pct_max)
        & features["distance_ema20_atr"].abs().le(params.ema_distance_atr)
    )

    bull = (
        common
        & features["ema_20"].gt(features["ema_50"])
        & features["ema_50_slope"].gt(0)
        & features["rsi_14"].gt(params.rsi_trigger)
        & features["rsi_14"].shift(1).le(params.rsi_trigger)
        & features["macd_hist"].gt(features["macd_hist"].shift(1))
    )

    bearish_trigger = 100.0 - params.rsi_trigger
    bear = (
        common
        & features["ema_20"].lt(features["ema_50"])
        & features["ema_50_slope"].lt(0)
        & features["rsi_14"].lt(bearish_trigger)
        & features["rsi_14"].shift(1).ge(bearish_trigger)
        & features["macd_hist"].lt(features["macd_hist"].shift(1))
    )

    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


def trend_pullback(
    frame: pd.DataFrame,
    params: TrendPullbackParams = TrendPullbackParams(),
) -> pd.Series:
    return trend_pullback_from_features(add_core_features(frame), params)


def prepare_trend_pullback(frame: pd.DataFrame):
    """Prepare core indicators once, then cheaply evaluate many parameter sets."""
    features = add_core_features(frame)

    def prepared(params: dict[str, float]) -> pd.Series:
        return trend_pullback_from_features(features, TrendPullbackParams(**params))

    return prepared


def trend_pullback_v1(frame: pd.DataFrame) -> pd.Series:
    return trend_pullback(frame)


def build_trend_pullback(params: dict[str, float]) -> SignalFunction:
    config = TrendPullbackParams(**params)
    return lambda frame: trend_pullback(frame, config)


STRATEGIES: dict[str, SignalFunction] = {
    "always_call": always_call,
    "always_put": always_put,
    "random": random_baseline,
    "ema_crossover": ema_crossover,
    "rsi_reversal": rsi_reversal,
    "trend_pullback_v1": trend_pullback_v1,
}
