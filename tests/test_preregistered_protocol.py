from pathlib import Path
import runpy

from confluence_lab.families import (
    COMPRESSION_BREAKOUT_GRID,
    HTF_ALIGNED_PULLBACK_GRID,
    SWEEP_REVERSAL_GRID,
    get_strategy_family,
)


def _replication_script_globals():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_fxcm_2018_range_replication.py"
    return runpy.run_path(str(path))


def test_frozen_2019_range_candidate_matches_preregistration():
    values = _replication_script_globals()
    frozen = values["FROZEN_PARAMS"]
    payout = values["PAYOUT"]

    assert frozen.adx_max == 30.0
    assert frozen.rsi_lower == 25.0
    assert frozen.rsi_upper == 65.0
    assert frozen.band_buffer_atr == 0.10
    assert frozen.atr_pct_max == 0.70
    assert payout == 0.82


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
