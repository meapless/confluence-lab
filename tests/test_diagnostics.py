import pandas as pd

from confluence_lab.diagnostics import (
    add_fixed_volatility_bucket,
    enrich_trades_with_signal_context,
    performance_breakdown,
)


def _trades() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=4, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "signal_timestamp": ts,
            "entry_timestamp": ts,
            "exit_timestamp": ts,
            "direction": [1, 1, -1, -1],
            "result": ["win", "loss", "win", "win"],
            "pnl": [0.82, -1.0, 0.82, 0.82],
        }
    )


def _context() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=4, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "utc_window": ["00_06", "00_06", "07_11", "07_11"],
            "utc_hour": [0, 0, 7, 7],
            "utc_weekday": [3, 3, 3, 3],
            "atr_percentile_100": [0.10, 0.40, 0.60, 0.90],
            "htf_5_trend": [0, 0, 1, 1],
            "htf_15_trend": [0, 0, 1, 1],
        }
    )


def test_enrichment_is_exact_and_does_not_change_trade_count():
    enriched = enrich_trades_with_signal_context(_trades(), _context())
    assert len(enriched) == 4
    assert list(enriched["utc_window"]) == ["00_06", "00_06", "07_11", "07_11"]
    assert list(enriched["pnl"]) == [0.82, -1.0, 0.82, 0.82]


def test_fixed_volatility_buckets_use_preregisterable_boundaries():
    enriched = enrich_trades_with_signal_context(_trades(), _context())
    bucketed = add_fixed_volatility_bucket(enriched)
    assert list(bucketed["volatility_bucket"].astype(str)) == [
        "q1_low",
        "q2",
        "q3",
        "q4_high",
    ]


def test_performance_breakdown_only_summarizes_existing_trades():
    enriched = enrich_trades_with_signal_context(_trades(), _context())
    result = performance_breakdown(enriched, "direction")
    assert set(result["direction"]) == {-1, 1}
    call = result.loc[result["direction"] == 1].iloc[0]
    put = result.loc[result["direction"] == -1].iloc[0]
    assert call["trades"] == 2
    assert call["wins"] == 1
    assert put["trades"] == 2
    assert put["wins"] == 2


def test_breakdown_respects_minimum_sample_filter():
    enriched = enrich_trades_with_signal_context(_trades(), _context())
    result = performance_breakdown(enriched, ["direction", "utc_window"], min_trades=3)
    assert result.empty
