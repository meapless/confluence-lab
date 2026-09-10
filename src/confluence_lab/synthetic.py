from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic_ohlc(*, rows: int = 20_000, seed: int = 42, frequency: str = "1min") -> pd.DataFrame:
    """Generate reproducible regime-switching OHLC data for engineering smoke tests only."""
    if rows < 10:
        raise ValueError("rows must be >= 10")
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2024-01-01", periods=rows, freq=frequency, tz="UTC")
    regime_len = 500
    regimes = np.repeat(rng.choice([-1, 0, 1], size=(rows // regime_len) + 1, p=[0.3, 0.4, 0.3]), regime_len)[:rows]
    drift = regimes * 0.000015
    noise = rng.normal(0, 0.00018, rows)
    returns = drift + noise
    close = 1.10 * np.exp(np.cumsum(returns))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0.00008, 0.00003, rows))
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    payout = rng.choice([0.70, 0.75, 0.80, 0.82, 0.85, 0.90, 0.92], size=rows)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "payout": payout,
    })
