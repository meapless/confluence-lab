import pandas as pd

from confluence_lab.matrix import ExecutionVariant, grid_search_matrix


def _direction_builder(params):
    direction = int(params["direction"])

    def strategy(frame):
        return pd.Series(direction, index=frame.index, dtype="int8")

    return strategy


def test_matrix_search_rejects_negative_expectancy_before_ranking():
    rows = 120
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="1min", tz="UTC")
    opens = pd.Series([1.2000 - i * 0.0001 for i in range(rows)], dtype=float)
    closes = opens - 0.00005
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": opens + 0.00002,
            "low": closes - 0.00002,
            "close": closes,
        }
    )

    ranked = grid_search_matrix(
        frame,
        _direction_builder,
        {"direction": [1, -1]},
        [ExecutionVariant(expiry_bars=1, fixed_payout=0.82)],
        objective="wilson_low",
        min_trades=30,
        min_expectancy=0.0,
    )

    assert ranked[0].params["direction"] == -1
    assert ranked[0].metrics.expectancy > 0

    losing = next(candidate for candidate in ranked if candidate.params["direction"] == 1)
    assert losing.metrics.expectancy < 0
    assert losing.score == float("-inf")
