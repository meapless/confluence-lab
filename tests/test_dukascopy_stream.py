from __future__ import annotations

import hashlib
import lzma
import struct
from datetime import datetime, timezone

import pandas as pd

import confluence_lab.dukascopy_stream as stream
from confluence_lab.dukascopy import decode_bi5_ticks

_TICK = struct.Struct(">IIIff")


def _payload(prices: list[tuple[int, int, int]]) -> bytes:
    raw = b"".join(
        _TICK.pack(milliseconds, ask, bid, 1.0, 1.0)
        for milliseconds, ask, bid in prices
    )
    return lzma.compress(raw)


def test_vectorized_decoder_matches_reference_decoder():
    payload = _payload(
        [
            (0, 110010, 109990),
            (17_500, 110023, 110002),
            (59_999, 109998, 109979),
        ]
    )
    day = datetime(2020, 1, 1, tzinfo=timezone.utc)
    reference = decode_bi5_ticks(payload, symbol="EURUSD", day=day)
    vectorized = stream.decode_bi5_ticks_vectorized(payload, symbol="EURUSD", day=day)
    pd.testing.assert_frame_equal(vectorized, reference, check_dtype=False, rtol=1e-7, atol=1e-9)


def test_streaming_downloader_hashes_sources_and_drops_missing_days(monkeypatch):
    first = _payload(
        [
            (0, 110010, 109990),
            (30_000, 110020, 110000),
            (60_000, 110030, 110010),
        ]
    )
    third = _payload(
        [
            (0, 111010, 110990),
            (60_000, 111020, 111000),
        ]
    )

    def fake_fetch(symbol, day, *, timeout=20.0):
        if day.day == 1:
            return first
        if day.day == 2:
            return None
        if day.day == 3:
            return third
        raise AssertionError(day)

    monkeypatch.setattr(stream, "fetch_bi5_bytes", fake_fetch)
    result = stream.download_candles_streaming(
        "EURUSD",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        datetime(2020, 1, 4, tzinfo=timezone.utc),
    )

    assert result.symbol == "EURUSD"
    assert len(result.sources) == 3
    assert result.sources[0].sha256 == hashlib.sha256(first).hexdigest()
    assert result.sources[1].status == "missing_404"
    assert result.sources[1].sha256 is None
    assert result.sources[2].sha256 == hashlib.sha256(third).hexdigest()
    assert not result.frame.empty
    assert result.frame["timestamp"].is_monotonic_increasing
    assert not result.frame["timestamp"].duplicated().any()
    assert (result.frame["source"] == "dukascopy").all()
    assert (result.frame["asset"] == "EURUSD").all()
    assert (result.frame["market_type"] == "regular").all()


def test_streaming_downloader_respects_exact_interval(monkeypatch):
    payload = _payload(
        [
            (0, 110010, 109990),
            (60_000, 110020, 110000),
            (120_000, 110030, 110010),
        ]
    )
    monkeypatch.setattr(stream, "fetch_bi5_bytes", lambda *args, **kwargs: payload)
    result = stream.download_candles_streaming(
        "EURUSD",
        datetime(2020, 1, 1, 0, 1, tzinfo=timezone.utc),
        datetime(2020, 1, 1, 0, 3, tzinfo=timezone.utc),
    )
    expected = pd.date_range(
        "2020-01-01T00:01:00Z", periods=2, freq="min", name="timestamp"
    )
    pd.testing.assert_index_equal(pd.DatetimeIndex(result.frame["timestamp"]), expected)


def test_streaming_downloader_rejects_empty_interval(monkeypatch):
    monkeypatch.setattr(stream, "fetch_bi5_bytes", lambda *args, **kwargs: None)
    try:
        stream.download_candles_streaming(
            "EURUSD",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2020, 1, 2, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert "no candles" in str(exc)
    else:
        raise AssertionError("expected no-candles failure")
