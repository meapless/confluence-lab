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
from .hypotheses_v2 import (
    build_compression_breakout,
    build_htf_aligned_pullback,
    build_sweep_reversal,
    prepare_compression_breakout,
    prepare_htf_aligned_pullback,
    prepare_sweep_reversal,
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

HTF_ALIGNED_PULLBACK_GRID: dict[str, tuple[Any, ...]] = {
    "htf_minutes": (5, 15),
    "adx_min": (15.0, 20.0, 25.0),
    "ema_distance_atr": (0.25, 0.50, 0.75),
    "rsi_trigger": (50.0, 55.0),
    "atr_pct_max": (0.75, 0.90),
}

COMPRESSION_BREAKOUT_GRID: dict[str, tuple[Any, ...]] = {
    "htf_minutes": (5, 15),
    "lookback": (20, 30),
    "compression_max": (0.20, 0.35),
    "body_min": (0.50, 0.65),
    "atr_expansion_min": (1.0, 1.2),
}

SWEEP_REVERSAL_GRID: dict[str, tuple[Any, ...]] = {
    "lookback": (20, 30, 50),
    "wick_min": (0.50, 0.65),
    "rsi_edge": (60.0, 65.0),
    "overshoot_atr": (0.0, 0.10),
    "liquid_core_only": (False, True),
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
    "htf_aligned_pullback": StrategyFamily(
        name="htf_aligned_pullback",
        description="Pullback recovery requiring completed higher-timeframe trend agreement.",
        builder=build_htf_aligned_pullback,
        prepared_factory=prepare_htf_aligned_pullback,
        parameter_grid=HTF_ALIGNED_PULLBACK_GRID,
        intended_regimes=("strong_uptrend", "weak_uptrend", "strong_downtrend", "weak_downtrend"),
    ),
    "compression_breakout": StrategyFamily(
        name="compression_breakout",
        description="Prior-volatility compression followed by a close-confirmed breakout aligned with completed HTF trend.",
        builder=build_compression_breakout,
        prepared_factory=prepare_compression_breakout,
        parameter_grid=COMPRESSION_BREAKOUT_GRID,
        intended_regimes=("breakout_candidate", "high_volatility"),
    ),
    "sweep_reversal": StrategyFamily(
        name="sweep_reversal",
        description="Failed prior-range breakout with wick rejection and close back inside structure.",
        builder=build_sweep_reversal,
        prepared_factory=prepare_sweep_reversal,
        parameter_grid=SWEEP_REVERSAL_GRID,
        intended_regimes=("quiet_range", "high_volatility", "uncertain"),
    ),
}


def get_strategy_family(name: str) -> StrategyFamily:
    try:
        return FAMILIES[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown strategy family {name!r}; choose from {', '.join(sorted(FAMILIES))}"
        ) from exc
