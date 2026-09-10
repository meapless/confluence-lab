from __future__ import annotations

import pandas as pd

from .hypotheses import RangeReversionParams, range_reversion


V3A_RANGE_PARAMS = RangeReversionParams(
    adx_max=30.0,
    rsi_lower=25.0,
    rsi_upper=65.0,
    band_buffer_atr=0.10,
    atr_pct_max=0.70,
)


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
