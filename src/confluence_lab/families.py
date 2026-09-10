from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Any, Callable, Mapping

import pandas as pd

from .hypotheses import (
    build_breakout,
    build_range_reversion,
    prepare_breakout,
    prepare_range_reversion,
)
from .optimization import StrategyBuilder
from .strategies import build_trend_pullback, prepare_trend_pullback

PreparedFactory = Callable[[pd.DataFrame], Callable[[dict[str, Any]], pd.Series]]


@dataclass(frozen=True)
class StrategyFamily:
    name: str
    description: str
    builder: StrategyBuilder
    prepared_factory: PreparedFactory
    parameter_grid: Mapping[str, tuple[Any, ...]]
    intended_regimes: tuple[str, ...]

    @property
    def grid_size(self) -> int:
        return prod(len(values) for values in self.parameter_grid.values())


TREND_PULLBACK_GRID: dict[str, tuple[Any, ...]] = {
    "adx_min": (15.0, 20.0, 25.0, 30.0),
    "atr_pct_min": (0.05, 0.15, 0.25),
    "atr_pct_max": (0.75, 0.90),
    "ema_distance_atr": (0.20, 0.35, 0.50, 0.75),
    "rsi_trigger": (50.0, 52.5, 55.0),
}

RANGE_REVERSION_GRID: dict[str, tuple[Any, ...]] = {
    "adx_max": (15.0, 20.0, 25.0, 30.0),
    "rsi_lower": (25.0, 30.0, 35.0),
    "rsi_upper": (65.0, 70.0, 75.0),
    "band_buffer_atr": (0.0, 0.10, 0.20, 0.35),
    "atr_pct_max": (0.50, 0.70),
}

BREAKOUT_GRID: dict[str, tuple[Any, ...]] = {
    "lookback": (10, 20, 30, 50),
    "adx_min": (15.0, 20.0, 25.0, 30.0),
    "body_min": (0.40, 0.55, 0.70),
    "atr_pct_min": (0.30, 0.50),
    "trend_filter": (False, True),
}


FAMILIES: dict[str, StrategyFamily] = {
    "trend_pullback": StrategyFamily(
        name="trend_pullback",
        description="Trend-following pullback entries with momentum recovery and volatility filters.",
        builder=build_trend_pullback,
        prepared_factory=prepare_trend_pullback,
        parameter_grid=TREND_PULLBACK_GRID,
        intended_regimes=("strong_uptrend", "weak_uptrend", "strong_downtrend", "weak_downtrend"),
    ),
    "range_reversion": StrategyFamily(
        name="range_reversion",
        description="Mean-reversion entries near Bollinger extremes in lower-trend-strength conditions.",
        builder=build_range_reversion,
        prepared_factory=prepare_range_reversion,
        parameter_grid=RANGE_REVERSION_GRID,
        intended_regimes=("quiet_range",),
    ),
    "breakout": StrategyFamily(
        name="breakout",
        description="Prior-range breakouts with momentum, body-size, trend and volatility filters.",
        builder=build_breakout,
        prepared_factory=prepare_breakout,
        parameter_grid=BREAKOUT_GRID,
        intended_regimes=("breakout_candidate", "strong_uptrend", "strong_downtrend", "high_volatility"),
    ),
}


def get_strategy_family(name: str) -> StrategyFamily:
    try:
        return FAMILIES[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown strategy family {name!r}; choose from {', '.join(sorted(FAMILIES))}"
        ) from exc
