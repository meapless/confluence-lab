import pandas as pd

from confluence_lab.backtest import BacktestConfig, run_backtest
from confluence_lab.experiments import ValidationGate, run_research_experiment
from confluence_lab.matrix import ExecutionVariant, grid_search_matrix, run_matrix_experiment
from confluence_lab.optimization import grid_search, iter_parameter_grid
from confluence_lab.registry import append_experiment_record, read_registry, verify_registry
from confluence_lab.robustness import monte_carlo_trades
from confluence_lab.synthetic import generate_synthetic_ohlc
from confluence_lab.walkforward import WalkForwardConfig, walk_forward


def directional_builder(params):
    every = int(params["every"])
    direction = int(params["direction"])

    def strategy(frame):
        signal = pd.Series(0, index=frame.index, dtype="int8")
        signal.iloc[::every] = direction
        return signal

    return strategy


def test_parameter_grid_cartesian_product():
    values = list(iter_parameter_grid({"a": [1, 2], "b": ["x", "y", "z"]}))
    assert len(values) == 6
    assert {"a": 2, "b": "z"} in values


def test_grid_search_respects_minimum_trade_count():
    frame = generate_synthetic_ohlc(rows=300, seed=1)
    ranked = grid_search(
        frame,
        directional_builder,
        {"every": [2, 100], "direction": [1]},
        config=BacktestConfig(),
        min_trades=50,
    )
    assert ranked[0].params["every"] == 2
    assert ranked[-1].score == float("-inf")


def test_validation_gate_prevents_locked_test_access_on_failure():
    frame = generate_synthetic_ohlc(rows=600, seed=4)
    result = run_research_experiment(
        frame,
        directional_builder,
        {"every": [5], "direction": [1]},
        gate=ValidationGate(min_trades=10, min_expectancy=999),
    )
    assert result.status == "rejected_validation"
    assert result.validation_metrics is not None
    assert result.test_metrics is None


def test_walk_forward_has_strict_train_before_test_boundaries():
    frame = generate_synthetic_ohlc(rows=500, seed=5)
    output = walk_forward(
        frame,
        directional_builder,
        {"every": [3, 5], "direction": [-1, 1]},
        config=WalkForwardConfig(train_bars=200, test_bars=100, min_trades=10),
    )
    assert len(output) == 3
    assert (output["train_end"] < output["test_start"]).all()


def test_monte_carlo_is_reproducible_and_reports_probability():
    trades = pd.DataFrame({"pnl": [0.8, 0.8, -1.0, 0.8, -1.0, 0.8]})
    first = monte_carlo_trades(trades, simulations=200, seed=9)
    second = monte_carlo_trades(trades, simulations=200, seed=9)
    assert first == second
    assert 0 <= first.probability_profitable <= 1
    assert first.final_pnl_p05 <= first.final_pnl_median <= first.final_pnl_p95


def test_walk_forward_does_not_run_when_insufficient_rows():
    frame = generate_synthetic_ohlc(rows=100, seed=2)
    output = walk_forward(
        frame,
        directional_builder,
        {"every": [2], "direction": [1]},
        config=WalkForwardConfig(train_bars=80, test_bars=30, min_trades=1),
    )
    assert output.empty


def test_registry_is_append_only_hash_chain(tmp_path):
    path = tmp_path / "registry.jsonl"
    first = append_experiment_record(path, {"dataset": "abc", "score": 1})
    second = append_experiment_record(path, {"dataset": "def", "score": 2})
    assert second["previous_hash"] == first["record_hash"]
    assert len(read_registry(path)) == 2
    assert verify_registry(path)


def test_registry_detects_tampering(tmp_path):
    path = tmp_path / "registry.jsonl"
    append_experiment_record(path, {"dataset": "abc", "score": 1})
    text = path.read_text(encoding="utf-8").replace('"score": 1', '"score": 999')
    path.write_text(text, encoding="utf-8")
    assert not verify_registry(path)


def test_payout_floor_is_applied_at_entry():
    frame = generate_synthetic_ohlc(rows=100, seed=10)
    frame["payout"] = 0.70
    frame.loc[frame.index[1::2], "payout"] = 0.90
    result = run_backtest(
        frame,
        directional_builder({"every": 1, "direction": 1}),
        BacktestConfig(expiry_bars=1, payout_column="payout", min_payout=0.85),
    )
    assert not result.trades.empty
    assert (result.trades["payout"] >= 0.85).all()


def test_matrix_search_spans_expiry_and_payout_floor():
    frame = generate_synthetic_ohlc(rows=400, seed=11)
    variants = [
        ExecutionVariant(expiry_bars=1, payout_column="payout", min_payout=0.80),
        ExecutionVariant(expiry_bars=3, payout_column="payout", min_payout=0.90),
    ]
    ranked = grid_search_matrix(
        frame,
        directional_builder,
        {"every": [3], "direction": [-1, 1]},
        variants,
        min_trades=5,
    )
    assert len(ranked) == 4
    assert {item.execution.expiry_bars for item in ranked} == {1, 3}


def test_matrix_validation_gate_hides_locked_test():
    frame = generate_synthetic_ohlc(rows=800, seed=12)
    result = run_matrix_experiment(
        frame,
        directional_builder,
        {"every": [3, 5], "direction": [-1, 1]},
        [ExecutionVariant(expiry_bars=1, payout_column="payout")],
        search_min_trades=10,
        gate=ValidationGate(min_trades=5, min_expectancy=999),
    )
    assert result.status == "rejected_validation"
    assert result.test_metrics is None
