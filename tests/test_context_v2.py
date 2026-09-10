import pandas as pd

from confluence_lab.context import add_research_context, completed_htf_features
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_completed_htf_context_uses_only_previous_closed_bucket():
    rows = 30
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="1min", tz="UTC"),
            "open": [1.0 + i * 0.001 for i in range(rows)],
            "high": [1.001 + i * 0.001 for i in range(rows)],
            "low": [0.999 + i * 0.001 for i in range(rows)],
            "close": [1.0005 + i * 0.001 for i in range(rows)],
        }
    )

    context = completed_htf_features(
        frame,
        minutes=5,
        ema_fast=1,
        ema_slow=2,
        minimum_coverage=1.0,
    )

    # 00:07 belongs to the 00:05-00:09 bucket, so its completed HTF close
    # must come from the prior 00:00-00:04 bucket.
    assert context.loc[7, "htf_5_close"] == frame.loc[4, "close"]

    altered = frame.copy()
    altered.loc[5:9, ["open", "high", "low", "close"]] *= 10
    changed = completed_htf_features(
        altered,
        minutes=5,
        ema_fast=1,
        ema_slow=2,
        minimum_coverage=1.0,
    )
    assert changed.loc[7, "htf_5_close"] == context.loc[7, "htf_5_close"]


def test_research_context_does_not_change_past_when_future_prices_change():
    frame = generate_synthetic_ohlc(rows=700, seed=91)
    original = add_research_context(frame)

    altered = frame.copy()
    altered.loc[500:, "close"] *= 2.0
    altered.loc[500:, "open"] *= 2.0
    altered.loc[500:, "high"] = altered.loc[500:, ["open", "close"]].max(axis=1) + 0.01
    altered.loc[500:, "low"] = altered.loc[500:, ["open", "close"]].min(axis=1) - 0.01
    changed = add_research_context(altered)

    columns = [
        "ema_20",
        "ema_50",
        "atr_14",
        "bb_width_percentile_200",
        "atr_ratio_5_50",
        "htf_5_close",
        "htf_5_trend",
        "htf_15_close",
        "htf_15_trend",
        "utc_hour",
        "utc_liquid_core",
    ]
    pd.testing.assert_frame_equal(
        original.loc[:499, columns],
        changed.loc[:499, columns],
    )
