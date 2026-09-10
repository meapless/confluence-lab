from confluence_lab.matrix import ExecutionVariant, grid_search_matrix
from confluence_lab.strategies import build_trend_pullback, prepare_trend_pullback
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_prepared_matrix_path_matches_unprepared_best_score():
    frame = generate_synthetic_ohlc(rows=500, seed=44)
    variants = [ExecutionVariant(expiry_bars=1, payout_column="payout")]
    grid = {
        "adx_min": [15.0, 25.0],
        "atr_pct_min": [0.15],
        "atr_pct_max": [0.90],
        "ema_distance_atr": [0.35, 0.75],
        "rsi_trigger": [50.0],
    }
    normal = grid_search_matrix(
        frame,
        build_trend_pullback,
        grid,
        variants,
        min_trades=1,
    )
    prepared = grid_search_matrix(
        frame,
        build_trend_pullback,
        grid,
        variants,
        min_trades=1,
        prepared_factory=prepare_trend_pullback,
    )
    assert normal[0].score == prepared[0].score
    assert normal[0].params == prepared[0].params
