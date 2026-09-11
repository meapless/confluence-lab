from __future__ import annotations

import hashlib
import lzma
import struct
from datetime import datetime, timezone
from urllib.error import HTTPError

import pandas as pd
import pytest

import confluence_lab.dukascopy_stream as stream
from confluence_lab.dukascopy import decode_bi5_ticks

_TICK = struct.Struct(">IIIff")


def _payload(prices: list[tuple[int, int, int]]) -> bytes:
    raw = b"".join(
        _TICK.pack(milliseconds, ask, bid, 1.0, 1.0)
        for milliseconds, ask, bid in prices
    )
    return lzma.compress(raw)


def _http_error(code: int) -> HTTPError:
    return HTTPError(
        "https://www.dukascopy.com/datafeed/EURUSD/example.bi5",
        code,
        "test",
        hdrs=None,
        fp=None,
    )


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


def test_fetch_retries_transient_503_then_succeeds(monkeypatch):
    expected = b"payload"
    calls = []
    sleeps = []

    def fake_open(request, *, timeout):
        calls.append((request.full_url, timeout))
        if len(calls) < 3:
            raise _http_error(503)
        return expected

    monkeypatch.setattr(stream, "_open_bi5_once", fake_open)
    monkeypatch.setattr(stream.time, "sleep", sleeps.append)

    result = stream.fetch_bi5_bytes(
        "EURUSD",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        timeout=7.0,
        max_attempts=3,
        backoff_seconds=0.25,
    )
    assert result == expected
    assert len(calls) == 3
    assert sleeps == [0.25, 0.5]


def test_fetch_retries_read_timeout_then_succeeds(monkeypatch):
    expected = b"payload"
    calls = []
    sleeps = []

    def fake_open(request, *, timeout):
        calls.append((request.full_url, timeout))
        if len(calls) == 1:
            raise TimeoutError("The read operation timed out")
        return expected

    monkeypatch.setattr(stream, "_open_bi5_once", fake_open)
    monkeypatch.setattr(stream.time, "sleep", sleeps.append)

    result = stream.fetch_bi5_bytes(
        "EURUSD",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        timeout=11.0,
        max_attempts=2,
        backoff_seconds=0.5,
    )
    assert result == expected
    assert len(calls) == 2
    assert calls == [
        (calls[0][0], 11.0),
        (calls[0][0], 11.0),
    ]
    assert sleeps == [0.5]


def test_fetch_exhausted_read_timeout_still_raises(monkeypatch):
    calls = []
    sleeps = []

    def fake_open(request, *, timeout):
        calls.append((request.full_url, timeout))
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(stream, "_open_bi5_once", fake_open)
    monkeypatch.setattr(stream.time, "sleep", sleeps.append)

    with pytest.raises(TimeoutError, match="read operation timed out"):
        stream.fetch_bi5_bytes(
            "EURUSD",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            timeout=13.0,
            max_attempts=3,
            backoff_seconds=0.2,
        )
    assert len(calls) == 3
    assert [timeout for _, timeout in calls] == [13.0, 13.0, 13.0]
    assert sleeps == [0.2, 0.4]


def test_fetch_404_is_missing_without_retry(monkeypatch):
    calls = []
    sleeps = []

    def fake_open(request, *, timeout):
        calls.append(1)
        raise _http_error(404)

    monkeypatch.setattr(stream, "_open_bi5_once", fake_open)
    monkeypatch.setattr(stream.time, "sleep", sleeps.append)

    result = stream.fetch_bi5_bytes(
        "EURUSD",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        max_attempts=5,
    )
    assert result is None
    assert len(calls) == 1
    assert sleeps == []


def test_fetch_exhausted_503_still_raises(monkeypatch):
    calls = []
    sleeps = []

    def fake_open(request, *, timeout):
        calls.append(1)
        raise _http_error(503)

    monkeypatch.setattr(stream, "_open_bi5_once", fake_open)
    monkeypatch.setattr(stream.time, "sleep", sleeps.append)

    with pytest.raises(HTTPError) as exc_info:
        stream.fetch_bi5_bytes(
            "EURUSD",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            max_attempts=3,
            backoff_seconds=0.1,
        )
    assert exc_info.value.code == 503
    assert len(calls) == 3
    assert sleeps == [0.1, 0.2]


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
    with pytest.raises(ValueError, match="no candles"):
        stream.download_candles_streaming(
            "EURUSD",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2020, 1, 2, tzinfo=timezone.utc),
        )
