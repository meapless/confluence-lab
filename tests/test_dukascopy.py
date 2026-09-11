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
    fetch_tick_day,
    price_divisor,
    ticks_to_candles,
)


def _payload(records):
    raw = b"".join(struct.pack(">IIIff", *record) for record in records)
    return lzma.compress(raw)


def _tick_frame(timestamp: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([timestamp]),
            "ask": [1.1002],
            "bid": [1.1000],
            "ask_volume": [1.0],
            "bid_volume": [2.0],
        }
    )


def test_dukascopy_url_uses_hourly_path_zero_indexed_month_and_datafeed_host():
    url = dukascopy_tick_url(
        "EUR/USD",
        datetime(2026, 1, 5, 13, 47, tzinfo=timezone.utc),
    )
    assert url == (
        "https://datafeed.dukascopy.com/datafeed/"
        "EURUSD/2026/00/05/13h_ticks.bi5"
    )


def test_price_divisor_handles_jpy_pairs():
    assert price_divisor("EURUSD") == 100_000
    assert price_divisor("USDJPY") == 1_000


def test_decode_hourly_bi5_ticks_uses_hour_as_epoch():
    hour = datetime(2026, 1, 5, 13, tzinfo=timezone.utc)
    payload = _payload(
        [
            (500, 110025, 110015, 1.5, 2.5),
            (61_000, 110035, 110025, 3.0, 4.0),
        ]
    )
    ticks = decode_bi5_ticks(payload, symbol="EURUSD", day=hour)
    assert len(ticks) == 2
    assert ticks.iloc[0]["ask"] == pytest.approx(1.10025)
    assert ticks.iloc[0]["bid"] == pytest.approx(1.10015)
    assert ticks.iloc[0]["timestamp"] == pd.Timestamp("2026-01-05T13:00:00.500Z")
    assert ticks.iloc[1]["timestamp"] == pd.Timestamp("2026-01-05T13:01:01Z")


def test_fetch_tick_day_concatenates_24_hourly_objects(monkeypatch):
    calls = []

    def fake_fetch_tick_hour(symbol, hour, *, timeout=20.0):
        calls.append(hour)
        if hour.hour == 0:
            return _tick_frame("2026-01-05T00:00:01Z")
        if hour.hour == 13:
            return _tick_frame("2026-01-05T13:30:00Z")
        return decode_bi5_ticks(b"", symbol=symbol, day=hour)

    monkeypatch.setattr(dukascopy, "fetch_tick_hour", fake_fetch_tick_hour)
    ticks = fetch_tick_day(
        "EURUSD",
        datetime(2026, 1, 5, 16, tzinfo=timezone.utc),
    )
    assert len(calls) == 24
    assert [call.hour for call in calls] == list(range(24))
    assert list(ticks["timestamp"]) == [
        pd.Timestamp("2026-01-05T00:00:01Z"),
        pd.Timestamp("2026-01-05T13:30:00Z"),
    ]


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


def test_download_range_filters_hourly_source_to_exact_requested_interval(monkeypatch):
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
