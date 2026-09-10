from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from .indicators import add_core_features


class MarketRegime(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    STRONG_DOWNTREND = "strong_downtrend"
    WEAK_DOWNTREND = "weak_downtrend"
    QUIET_RANGE = "quiet_range"
    HIGH_VOLATILITY = "high_volatility"
    BREAKOUT_CANDIDATE = "breakout_candidate"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class RegimeThresholds:
    strong_adx: float = 25.0
    weak_adx: float = 18.0
    range_adx_max: float = 18.0
    range_atr_pct_max: float = 0.65
    high_volatility_atr_pct: float = 0.90
    breakout_atr_pct_min: float = 0.60
    breakout_body_min: float = 0.50
    breakout_lookback: int = 20

    def __post_init__(self) -> None:
        if self.strong_adx < self.weak_adx:
            raise ValueError("strong_adx must be >= weak_adx")
        if self.breakout_lookback < 2:
            raise ValueError("breakout_lookback must be >= 2")
        for name in (
            "range_atr_pct_max",
            "high_volatility_atr_pct",
            "breakout_atr_pct_min",
            "breakout_body_min",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


def classify_regime_from_features(
    features: pd.DataFrame,
    thresholds: RegimeThresholds = RegimeThresholds(),
) -> pd.Series:
    """Classify each row using only information available at or before that row.

    This is an explainable rule-based regime label, not a prediction. Breakout
    boundaries are explicitly shifted by one bar so the current bar cannot
    define the range it is being compared against.
    """
    required = {
        "close",
        "high",
        "low",
        "ema_20",
        "ema_50",
        "ema_50_slope",
        "adx_14",
        "atr_percentile_100",
        "candle_body_ratio",
    }
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"features missing required columns: {sorted(missing)}")

    previous_high = (
        features["high"]
        .rolling(thresholds.breakout_lookback, min_periods=thresholds.breakout_lookback)
        .max()
        .shift(1)
    )
    previous_low = (
        features["low"]
        .rolling(thresholds.breakout_lookback, min_periods=thresholds.breakout_lookback)
        .min()
        .shift(1)
    )

    labels = pd.Series(
        MarketRegime.INSUFFICIENT_DATA.value,
        index=features.index,
        dtype="object",
    )

    finite = (
        features[[
            "close",
            "ema_20",
            "ema_50",
            "ema_50_slope",
            "adx_14",
            "atr_percentile_100",
            "candle_body_ratio",
        ]]
        .replace([np.inf, -np.inf], np.nan)
        .notna()
        .all(axis=1)
    )
    if not finite.any():
        return labels

    bullish = features["ema_20"].gt(features["ema_50"]) & features["ema_50_slope"].gt(0)
    bearish = features["ema_20"].lt(features["ema_50"]) & features["ema_50_slope"].lt(0)

    breakout = (
        finite
        & features["atr_percentile_100"].ge(thresholds.breakout_atr_pct_min)
        & features["candle_body_ratio"].ge(thresholds.breakout_body_min)
        & (features["close"].gt(previous_high) | features["close"].lt(previous_low))
    )
    labels.loc[breakout] = MarketRegime.BREAKOUT_CANDIDATE.value

    unassigned = finite & ~breakout
    strong_up = unassigned & bullish & features["adx_14"].ge(thresholds.strong_adx)
    strong_down = unassigned & bearish & features["adx_14"].ge(thresholds.strong_adx)
    labels.loc[strong_up] = MarketRegime.STRONG_UPTREND.value
    labels.loc[strong_down] = MarketRegime.STRONG_DOWNTREND.value

    unassigned &= ~(strong_up | strong_down)
    quiet_range = (
        unassigned
        & features["adx_14"].le(thresholds.range_adx_max)
        & features["atr_percentile_100"].le(thresholds.range_atr_pct_max)
    )
    labels.loc[quiet_range] = MarketRegime.QUIET_RANGE.value

    unassigned &= ~quiet_range
    high_volatility = unassigned & features["atr_percentile_100"].ge(
        thresholds.high_volatility_atr_pct
    )
    labels.loc[high_volatility] = MarketRegime.HIGH_VOLATILITY.value

    unassigned &= ~high_volatility
    weak_up = unassigned & bullish & features["adx_14"].ge(thresholds.weak_adx)
    weak_down = unassigned & bearish & features["adx_14"].ge(thresholds.weak_adx)
    labels.loc[weak_up] = MarketRegime.WEAK_UPTREND.value
    labels.loc[weak_down] = MarketRegime.WEAK_DOWNTREND.value

    remaining = unassigned & ~(weak_up | weak_down)
    labels.loc[remaining] = MarketRegime.UNCERTAIN.value
    return labels


def classify_market_regime(
    frame: pd.DataFrame,
    thresholds: RegimeThresholds = RegimeThresholds(),
) -> pd.Series:
    return classify_regime_from_features(add_core_features(frame), thresholds)


def add_regime_column(
    frame: pd.DataFrame,
    thresholds: RegimeThresholds = RegimeThresholds(),
    *,
    column: str = "market_regime",
) -> pd.DataFrame:
    out = frame.copy()
    out[column] = classify_market_regime(out, thresholds)
    return out
