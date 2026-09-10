import lzma
import struct
from datetime import datetime, timezone

import pandas as pd
import pytest

from confluence_lab import dukascopy
from confluence_lab.dukascopy import (
    decode_bi5_ticks,
    download_range,
    dukascopy_tick_url,
    price_divisor,
    ticks_to_candles,
)


def _payload(records):
    raw = b"".join(struct.pack(">IIIff", *record) for record in records)
    return lzma.compress(raw)


def test_dukascopy_url_uses_current_daily_path_and_zero_indexed_month():
    url = dukascopy_tick_url(
        "EUR/USD",
        datetime(2026, 1, 5, 13, tzinfo=timezone.utc),
    )
    assert url.endswith("EURUSD/2026/00/05_ticks.bi5")


def test_price_divisor_handles_jpy_pairs():
    assert price_divisor("EURUSD") == 100_000
    assert price_divisor("USDJPY") == 1_000


def test_decode_daily_bi5_ticks():
    day = datetime(2026, 1, 5, tzinfo=timezone.utc)
    payload = _payload(
        [
            (500, 110025, 110015, 1.5, 2.5),
            (3_661_000, 110035, 110025, 3.0, 4.0),
        ]
    )
    ticks = decode_bi5_ticks(payload, symbol="EURUSD", day=day)
    assert len(ticks) == 2
    assert ticks.iloc[0]["ask"] == pytest.approx(1.10025)
    assert ticks.iloc[0]["bid"] == pytest.approx(1.10015)
    assert ticks.iloc[1]["timestamp"] == pd.Timestamp("2026-01-05T01:01:01Z")


def test_tick_to_one_minute_mid_candles():
    ticks = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-05T13:00:00Z",
                    "2026-01-05T13:00:30Z",
                    "2026-01-05T13:01:00Z",
                    "2026-01-05T13:01:30Z",
                ]
            ),
            "ask": [1.1002, 1.1004, 1.1005, 1.1003],
            "bid": [1.1000, 1.1002, 1.1003, 1.1001],
            "ask_volume": [1.0, 1.0, 1.0, 1.0],
            "bid_volume": [2.0, 2.0, 2.0, 2.0],
        }
    )
    bars = ticks_to_candles(ticks, timeframe="1min")
    assert len(bars) == 2
    assert bars.iloc[0]["open"] == pytest.approx(1.1001)
    assert bars.iloc[0]["high"] == pytest.approx(1.1003)
    assert bars.iloc[0]["close"] == pytest.approx(1.1003)
    assert bars.iloc[0]["volume"] == pytest.approx(6.0)
    assert bars.iloc[0]["spread_mean"] == pytest.approx(0.0002)


def test_download_range_filters_daily_file_to_exact_requested_interval(monkeypatch):
    ticks = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-05T11:59:59Z",
                    "2026-01-05T12:00:00Z",
                    "2026-01-05T12:30:00Z",
                    "2026-01-05T13:00:00Z",
                ]
            ),
            "ask": [1.1, 1.1, 1.1, 1.1],
            "bid": [1.0, 1.0, 1.0, 1.0],
            "ask_volume": [1.0] * 4,
            "bid_volume": [1.0] * 4,
        }
    )
    monkeypatch.setattr(dukascopy, "fetch_tick_day", lambda *args, **kwargs: ticks)
    result = download_range(
        "EURUSD",
        datetime(2026, 1, 5, 12, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 13, tzinfo=timezone.utc),
    )
    assert len(result.ticks) == 2
    assert result.ticks["timestamp"].min() == pd.Timestamp("2026-01-05T12:00:00Z")
    assert result.ticks["timestamp"].max() == pd.Timestamp("2026-01-05T12:30:00Z")
