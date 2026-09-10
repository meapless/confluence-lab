import pandas as pd

from confluence_lab.experiments import ValidationGate, run_research_experiment
from confluence_lab.matrix import ExecutionVariant, run_matrix_experiment
from confluence_lab.synthetic import generate_synthetic_ohlc


def directional_builder(params):
    every = int(params["every"])
    direction = int(params["direction"])

    def strategy(frame):
        signal = pd.Series(0, index=frame.index, dtype="int8")
        signal.iloc[::every] = direction
        return signal

    return strategy


def test_locked_test_requires_minimum_sample_after_validation_passes():
    frame = generate_synthetic_ohlc(rows=600, seed=111)
    result = run_research_experiment(
        frame,
        directional_builder,
        {"every": [5], "direction": [1]},
        search_min_trades=5,
        gate=ValidationGate(
            min_trades=1,
            min_expectancy=-999,
            min_locked_test_trades=10_000,
        ),
    )
    assert result.status == "insufficient_locked_test"
    assert result.test_metrics is not None


def test_matrix_locked_test_requires_minimum_sample():
    frame = generate_synthetic_ohlc(rows=600, seed=112)
    result = run_matrix_experiment(
        frame,
        directional_builder,
        {"every": [5], "direction": [1]},
        [ExecutionVariant(expiry_bars=1, payout_column="payout")],
        search_min_trades=5,
        gate=ValidationGate(
            min_trades=1,
            min_expectancy=-999,
            min_locked_test_trades=10_000,
        ),
    )
    assert result.status == "insufficient_locked_test"
    assert result.test_metrics is not None
