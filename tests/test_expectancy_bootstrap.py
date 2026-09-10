import pandas as pd
import pytest

from confluence_lab.robustness import bootstrap_expectancy


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


def test_bootstrap_rejects_nonfinite_pnl():
    with pytest.raises(ValueError, match="finite"):
        bootstrap_expectancy(pd.DataFrame({"pnl": [0.8, float("nan")]}), simulations=100)
