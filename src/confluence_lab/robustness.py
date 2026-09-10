from __future__ import annotations

from dataclasses import dataclass
from math import ceil

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


@dataclass(frozen=True)
class BlockExpectancyBootstrap:
    simulations: int
    trades: int
    block_size: int
    blocks_per_simulation: int
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

    This ordinary bootstrap assumes exchangeable trade outcomes. Use
    ``moving_block_bootstrap_expectancy`` as a dependence-aware stress test when
    trade outcomes may cluster over time.
    """
    if simulations < 100:
        raise ValueError("simulations must be >= 100 for an expectancy interval")
    pnl = _validated_pnl(trades)
    rng = np.random.default_rng(seed)

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


def moving_block_bootstrap_expectancy(
    trades: pd.DataFrame,
    *,
    block_size: int = 20,
    simulations: int = 10_000,
    seed: int = 42,
) -> BlockExpectancyBootstrap:
    """Bootstrap expectancy while preserving local trade-order dependence.

    Each simulation samples contiguous blocks of the observed P&L sequence with
    replacement and concatenates enough blocks to rebuild the original sample
    length. This is a robustness diagnostic for serially clustered outcomes,
    not a claim that the chosen block size is uniquely correct. Promising
    candidates should be checked across several plausible block sizes.
    """
    if simulations < 100:
        raise ValueError("simulations must be >= 100 for an expectancy interval")
    pnl = _validated_pnl(trades)
    if block_size < 1:
        raise ValueError("block_size must be positive")
    if block_size > len(pnl):
        raise ValueError("block_size cannot exceed number of trades")

    starts = np.arange(0, len(pnl) - block_size + 1, dtype=int)
    blocks_per_simulation = ceil(len(pnl) / block_size)
    rng = np.random.default_rng(seed)
    means = np.empty(simulations, dtype=float)

    # Build one simulation at a time to keep memory bounded even for long
    # trade histories. The expensive operation is block concatenation, but this
    # path is intended for final candidate diagnostics rather than grid search.
    for simulation in range(simulations):
        chosen = rng.choice(starts, size=blocks_per_simulation, replace=True)
        sampled = np.concatenate(
            [pnl[start : start + block_size] for start in chosen]
        )[: len(pnl)]
        means[simulation] = sampled.mean()

    return BlockExpectancyBootstrap(
        simulations=simulations,
        trades=len(pnl),
        block_size=block_size,
        blocks_per_simulation=blocks_per_simulation,
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
