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


@dataclass(frozen=True)
class ExpectancyBootstrap:
    simulations: int
    trades: int
    observed_expectancy: float
    expectancy_p025: float
    expectancy_median: float
    expectancy_p975: float
    probability_positive: float

    @property
    def lower_bound_positive(self) -> bool:
        return self.expectancy_p025 > 0.0


def _validated_pnl(trades: pd.DataFrame) -> np.ndarray:
    if trades.empty:
        raise ValueError("at least one trade is required")
    if "pnl" not in trades.columns:
        raise ValueError("trades must contain a pnl column")
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(pnl).all():
        raise ValueError("trade pnl values must be finite")
    return pnl


def _max_drawdown(path: np.ndarray) -> float:
    equity = np.cumsum(path)
    peaks = np.maximum.accumulate(np.maximum(equity, 0.0))
    return float(np.max(peaks - equity)) if len(path) else 0.0


def bootstrap_expectancy(
    trades: pd.DataFrame,
    *,
    simulations: int = 10_000,
    seed: int = 42,
) -> ExpectancyBootstrap:
    """Bootstrap mean payout-adjusted P&L per trade.

    Unlike a win-rate interval, this works naturally when individual trades
    have different payouts. A positive point estimate is not treated as strong
    evidence unless the lower confidence bound also clears zero.
    """
    if simulations < 100:
        raise ValueError("simulations must be >= 100 for an expectancy interval")
    pnl = _validated_pnl(trades)
    rng = np.random.default_rng(seed)

    # Batch to bound memory while keeping the calculation vectorized.
    means = np.empty(simulations, dtype=float)
    batch_size = max(1, min(1_000, simulations))
    offset = 0
    while offset < simulations:
        size = min(batch_size, simulations - offset)
        samples = rng.choice(pnl, size=(size, len(pnl)), replace=True)
        means[offset : offset + size] = samples.mean(axis=1)
        offset += size

    return ExpectancyBootstrap(
        simulations=simulations,
        trades=len(pnl),
        observed_expectancy=float(pnl.mean()),
        expectancy_p025=float(np.quantile(means, 0.025)),
        expectancy_median=float(np.median(means)),
        expectancy_p975=float(np.quantile(means, 0.975)),
        probability_positive=float(np.mean(means > 0.0)),
    )


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
    pnl = _validated_pnl(trades)
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
