from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MonteCarloSummary:
    simulations: int
    trades_per_simulation: int
    final_pnl_p05: float
    final_pnl_median: float
    final_pnl_p95: float
    max_drawdown_p50: float
    max_drawdown_p95: float
    probability_profitable: float


def _max_drawdown(path: np.ndarray) -> float:
    equity = np.cumsum(path)
    peaks = np.maximum.accumulate(np.maximum(equity, 0.0))
    return float(np.max(peaks - equity)) if len(path) else 0.0


def monte_carlo_trades(
    trades: pd.DataFrame,
    *,
    simulations: int = 5_000,
    seed: int = 42,
) -> MonteCarloSummary:
    """Bootstrap the observed trade P&L distribution.

    This is a robustness diagnostic, not a forecast or guarantee.
    """
    if simulations < 1:
        raise ValueError("simulations must be positive")
    if trades.empty:
        raise ValueError("at least one trade is required")

    pnl = trades["pnl"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    final_pnl = np.empty(simulations)
    drawdowns = np.empty(simulations)

    for index in range(simulations):
        sample = rng.choice(pnl, size=len(pnl), replace=True)
        final_pnl[index] = sample.sum()
        drawdowns[index] = _max_drawdown(sample)

    return MonteCarloSummary(
        simulations=simulations,
        trades_per_simulation=len(pnl),
        final_pnl_p05=float(np.quantile(final_pnl, 0.05)),
        final_pnl_median=float(np.median(final_pnl)),
        final_pnl_p95=float(np.quantile(final_pnl, 0.95)),
        max_drawdown_p50=float(np.median(drawdowns)),
        max_drawdown_p95=float(np.quantile(drawdowns, 0.95)),
        probability_profitable=float(np.mean(final_pnl > 0)),
    )
