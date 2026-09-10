from confluence_lab.families import (
    COMPRESSION_BREAKOUT_GRID,
    HTF_ALIGNED_PULLBACK_GRID,
    SWEEP_REVERSAL_GRID,
    get_strategy_family,
)
from scripts.run_fxcm_2018_range_replication import FROZEN_PARAMS, PAYOUT


def test_frozen_2019_range_candidate_matches_preregistration():
    assert FROZEN_PARAMS.adx_max == 30.0
    assert FROZEN_PARAMS.rsi_lower == 25.0
    assert FROZEN_PARAMS.rsi_upper == 65.0
    assert FROZEN_PARAMS.band_buffer_atr == 0.10
    assert FROZEN_PARAMS.atr_pct_max == 0.70
    assert PAYOUT == 0.82


def test_v2_search_budget_matches_preregistration():
    assert get_strategy_family("htf_aligned_pullback").grid_size == 72
    assert get_strategy_family("compression_breakout").grid_size == 32
    assert get_strategy_family("sweep_reversal").grid_size == 48
    assert 4 * (72 + 32 + 48) == 608

    assert HTF_ALIGNED_PULLBACK_GRID == {
        "htf_minutes": (5, 15),
        "adx_min": (15.0, 20.0, 25.0),
        "ema_distance_atr": (0.25, 0.50, 0.75),
        "rsi_trigger": (50.0, 55.0),
        "atr_pct_max": (0.75, 0.90),
    }
    assert COMPRESSION_BREAKOUT_GRID == {
        "htf_minutes": (5, 15),
        "lookback": (20, 30),
        "compression_max": (0.20, 0.35),
        "body_min": (0.50, 0.65),
        "atr_expansion_min": (1.0, 1.2),
    }
    assert SWEEP_REVERSAL_GRID == {
        "lookback": (20, 30, 50),
        "wick_min": (0.50, 0.65),
        "rsi_edge": (60.0, 65.0),
        "overshoot_atr": (0.0, 0.10),
        "liquid_core_only": (False, True),
    }
