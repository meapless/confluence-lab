from __future__ import annotations

import pandas as pd

from .context import add_research_context
from .hypotheses import RangeReversionParams, range_reversion
from .hypotheses_v2 import SweepReversalParams, sweep_reversal_from_features


V3A_RANGE_PARAMS = RangeReversionParams(
    adx_max=30.0,
    rsi_lower=25.0,
    rsi_upper=65.0,
    band_buffer_atr=0.10,
    atr_pct_max=0.70,
)

V3B_SWEEP_PARAMS = SweepReversalParams(
    lookback=20,
    wick_min=0.65,
    rsi_edge=65.0,
    overshoot_atr=0.0,
    liquid_core_only=False,
)
V3B_ATR_PERCENTILE_LOW_EXCLUSIVE = 0.25
V3B_ATR_PERCENTILE_HIGH_INCLUSIVE = 0.50


def call_only_range_reversion(
    frame: pd.DataFrame,
    params: RangeReversionParams = V3A_RANGE_PARAMS,
) -> pd.Series:
    """V3A: keep only bullish signals from the frozen V1 range-reversion rule.

    This is intentionally a thin directional filter. It does not retune or add
    conditions to the underlying strategy; the purpose is to replicate a
    post-hoc direction asymmetry on a fresh year.
    """
    signal = range_reversion(frame, params)
    return signal.where(signal.eq(1), 0).astype("int8")


def moderate_vol_sweep_reversal(
    frame: pd.DataFrame,
    params: SweepReversalParams = V3B_SWEEP_PARAMS,
) -> pd.Series:
    """V3B: frozen V2 sweep reversal restricted to the preregistered ATR Q2.

    The volatility rule was generated post-hoc from the failed 2018 V2
    candidate and is therefore tested here without any tuning. Context is
    trailing-only and the exact bucket boundaries are frozen in the V3B
    preregistration.
    """
    features = add_research_context(frame)
    signal = sweep_reversal_from_features(features, params)
    eligible = (
        features["atr_percentile_100"].gt(V3B_ATR_PERCENTILE_LOW_EXCLUSIVE)
        & features["atr_percentile_100"].le(V3B_ATR_PERCENTILE_HIGH_INCLUSIVE)
    )
    return signal.where(eligible, 0).astype("int8")
