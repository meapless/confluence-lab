import pandas as pd
import pytest

from confluence_lab.pocket import normalize_payout, normalize_pocket_candles


def test_normalize_pocket_documented_array_format():
    payload = {
        "asset": "EURUSD_otc",
        "period": 60,
        "candles": [
            [1_789_041_600, 1.10, 1.11, 1.12, 1.09],
            [1_789_041_660, 1.11, 1.105, 1.115, 1.10],
        ],
    }
    frame = normalize_pocket_candles(
        payload,
        asset="EURUSD_otc",
        period_seconds=60,
        payout=0.92,
    )
    assert list(frame.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "asset",
        "market_type",
        "period_seconds",
        "payout",
    ]
    assert frame.iloc[0]["close"] == pytest.approx(1.11)
    assert frame.iloc[0]["high"] == pytest.approx(1.12)
    assert frame.iloc[0]["market_type"] == "otc"
    assert frame.iloc[0]["timestamp"] == pd.Timestamp("2026-09-10T12:00:00Z")


def test_normalize_payout_accepts_percent_or_decimal():
    assert normalize_payout(92) == pytest.approx(0.92)
    assert normalize_payout(0.82) == pytest.approx(0.82)


def test_malformed_candle_is_skipped():
    frame = normalize_pocket_candles(
        {"candles": [[1, 2], [1_789_041_600, 1.0, 1.1, 1.2, 0.9]]},
        asset="EURUSD",
        period_seconds=60,
    )
    assert len(frame) == 1
    assert frame.iloc[0]["market_type"] == "regular"
