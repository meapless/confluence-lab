from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    out = out.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    return out


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    line = fast_ema - slow_ema
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": signal_line, "macd_hist": line - signal_line}, index=series.index)


def bollinger_bands(series: pd.Series, period: int = 20, stddev: float = 2.0) -> pd.DataFrame:
    middle = sma(series, period)
    sigma = series.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame({"bb_lower": middle - stddev * sigma, "bb_middle": middle, "bb_upper": middle + stddev * sigma}, index=series.index)


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    pieces = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - previous_close).abs(),
        (frame["low"] - previous_close).abs(),
    ], axis=1)
    return pieces.max(axis=1)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(frame).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_diff = frame["high"].diff()
    low_diff = -frame["low"].diff()
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0.0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0.0)
    atr_values = atr(frame, period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_values
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_values
    denominator = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denominator
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def rolling_percentile_rank(series: pd.Series, window: int) -> pd.Series:
    def rank_last(values: np.ndarray) -> float:
        return float(np.mean(values <= values[-1]))
    return series.rolling(window, min_periods=window).apply(rank_last, raw=True)


def add_core_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["ema_20"] = ema(out["close"], 20)
    out["ema_50"] = ema(out["close"], 50)
    out["ema_20_slope"] = out["ema_20"].diff()
    out["ema_50_slope"] = out["ema_50"].diff()
    out["rsi_14"] = rsi(out["close"], 14)
    out = out.join(macd(out["close"]))
    out["atr_14"] = atr(out, 14)
    out["adx_14"] = adx(out, 14)
    out = out.join(bollinger_bands(out["close"], 20, 2.0))
    out["distance_ema20_atr"] = (out["close"] - out["ema_20"]) / out["atr_14"]
    candle_range = (out["high"] - out["low"]).replace(0.0, np.nan)
    out["candle_body_ratio"] = (out["close"] - out["open"]).abs() / candle_range
    out["upper_wick_ratio"] = (out["high"] - out[["open", "close"]].max(axis=1)) / candle_range
    out["lower_wick_ratio"] = (out[["open", "close"]].min(axis=1) - out["low"]) / candle_range
    out["recent_high_20"] = out["high"].rolling(20, min_periods=20).max()
    out["recent_low_20"] = out["low"].rolling(20, min_periods=20).min()
    out["atr_percentile_100"] = rolling_percentile_rank(out["atr_14"], 100)
    return out
