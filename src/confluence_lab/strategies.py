from __future__ import annotations

from collections.abc import Callable

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


def rsi_reversal(frame: pd.DataFrame, period: int = 14, lower: float = 30, upper: float = 70) -> pd.Series:
    values = rsi(frame["close"], period)
    signal = pd.Series(0, index=frame.index, dtype="int8")
    signal.loc[(values > lower) & (values.shift(1) <= lower)] = 1
    signal.loc[(values < upper) & (values.shift(1) >= upper)] = -1
    return signal


def trend_pullback_v1(frame: pd.DataFrame) -> pd.Series:
    f = add_core_features(frame)
    signal = pd.Series(0, index=frame.index, dtype="int8")
    common = f["adx_14"].ge(20) & f["atr_percentile_100"].between(0.15, 0.90) & f["distance_ema20_atr"].abs().le(0.45)
    bull = common & f["ema_20"].gt(f["ema_50"]) & f["ema_50_slope"].gt(0) & f["rsi_14"].gt(50) & f["rsi_14"].shift(1).le(50) & f["macd_hist"].gt(f["macd_hist"].shift(1))
    bear = common & f["ema_20"].lt(f["ema_50"]) & f["ema_50_slope"].lt(0) & f["rsi_14"].lt(50) & f["rsi_14"].shift(1).ge(50) & f["macd_hist"].lt(f["macd_hist"].shift(1))
    signal.loc[bull] = 1
    signal.loc[bear] = -1
    return signal


STRATEGIES: dict[str, SignalFunction] = {
    "always_call": always_call,
    "always_put": always_put,
    "random": random_baseline,
    "ema_crossover": ema_crossover,
    "rsi_reversal": rsi_reversal,
    "trend_pullback_v1": trend_pullback_v1,
}
