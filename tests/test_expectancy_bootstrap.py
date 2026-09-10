import pandas as pd
import pytest

from confluence_lab.robustness import (
    bootstrap_expectancy,
    moving_block_bootstrap_expectancy,
)


def test_bootstrap_expectancy_is_reproducible():
    trades = pd.DataFrame({"pnl": [0.9, 0.8, -1.0, 0.85, -1.0, 0.92] * 20})
    first = bootstrap_expectancy(trades, simulations=500, seed=12)
    second = bootstrap_expectancy(trades, simulations=500, seed=12)
    assert first == second
    assert first.trades == len(trades)
    assert first.expectancy_p025 <= first.expectancy_median <= first.expectancy_p975
    assert 0 <= first.probability_positive <= 1


def test_bootstrap_lower_bound_flags_clear_positive_edge():
    trades = pd.DataFrame({"pnl": [0.9] * 90 + [-1.0] * 10})
    result = bootstrap_expectancy(trades, simulations=1_000, seed=3)
    assert result.observed_expectancy > 0
    assert result.lower_bound_positive
    assert result.probability_positive > 0.99


def test_moving_block_bootstrap_is_reproducible_and_preserves_size():
    trades = pd.DataFrame({"pnl": ([0.82] * 8 + [-1.0] * 4) * 20})
    first = moving_block_bootstrap_expectancy(
        trades, block_size=12, simulations=500, seed=17
    )
    second = moving_block_bootstrap_expectancy(
        trades, block_size=12, simulations=500, seed=17
    )
    assert first == second
    assert first.trades == len(trades)
    assert first.block_size == 12
    assert first.blocks_per_simulation == 20
    assert first.expectancy_p025 <= first.expectancy_median <= first.expectancy_p975
    assert 0 <= first.probability_positive <= 1


def test_moving_block_bootstrap_flags_clear_positive_edge():
    trades = pd.DataFrame({"pnl": [0.9] * 180 + [-1.0] * 20})
    result = moving_block_bootstrap_expectancy(
        trades, block_size=10, simulations=1_000, seed=4
    )
    assert result.observed_expectancy > 0
    assert result.lower_bound_positive


def test_moving_block_bootstrap_validates_block_size():
    trades = pd.DataFrame({"pnl": [0.82, -1.0, 0.82]})
    with pytest.raises(ValueError, match="positive"):
        moving_block_bootstrap_expectancy(trades, block_size=0, simulations=100)
    with pytest.raises(ValueError, match="exceed"):
        moving_block_bootstrap_expectancy(trades, block_size=4, simulations=100)


def test_bootstrap_rejects_nonfinite_pnl():
    with pytest.raises(ValueError, match="finite"):
        bootstrap_expectancy(pd.DataFrame({"pnl": [0.8, float("nan")]}), simulations=100)
