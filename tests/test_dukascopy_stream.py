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
        "https://datafeed.dukascopy.com/datafeed/EURUSD/example.bi5",
        code,
        "test",
        hdrs=None,
        fp=None,
    )


def test_vectorized_decoder_matches_reference_decoder_at_non_midnight_hour():
    payload = _payload(
        [
            (0, 110010, 109990),
            (17_500, 110023, 110002),
            (59_999, 109998, 109979),
        ]
    )
    hour = datetime(2020, 1, 1, 13, tzinfo=timezone.utc)
    reference = decode_bi5_ticks(payload, symbol="EURUSD", day=hour)
    vectorized = stream.decode_bi5_ticks_vectorized(payload, symbol="EURUSD", day=hour)
    pd.testing.assert_frame_equal(vectorized, reference, check_dtype=False, rtol=1e-7, atol=1e-9)
    assert vectorized.iloc[0]["timestamp"] == pd.Timestamp("2020-01-01T13:00:00Z")


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
        datetime(2020, 1, 1, 13, tzinfo=timezone.utc),
        timeout=7.0,
        max_attempts=3,
        backoff_seconds=0.25,
    )
    assert result == expected
    assert len(calls) == 3
    assert calls[0][0].endswith("EURUSD/2020/00/01/13h_ticks.bi5")
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
        datetime(2020, 1, 1, 13, tzinfo=timezone.utc),
        timeout=11.0,
        max_attempts=2,
        backoff_seconds=0.5,
    )
    assert result == expected
    assert len(calls) == 2
    assert [timeout for _, timeout in calls] == [11.0, 11.0]
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
            datetime(2020, 1, 1, 13, tzinfo=timezone.utc),
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
        datetime(2020, 1, 1, 13, tzinfo=timezone.utc),
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
            datetime(2020, 1, 1, 13, tzinfo=timezone.utc),
            max_attempts=3,
            backoff_seconds=0.1,
        )
    assert exc_info.value.code == 503
    assert len(calls) == 3
    assert sleeps == [0.1, 0.2]


def test_streaming_downloader_hashes_hourly_sources_and_keeps_order(monkeypatch):
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

    def fake_fetch(symbol, hour, *, timeout=20.0):
        if hour.hour == 0:
            return first
        if hour.hour == 1:
            return None
        if hour.hour == 2:
            return third
        raise AssertionError(hour)

    monkeypatch.setattr(stream, "fetch_bi5_bytes", fake_fetch)
    result = stream.download_candles_streaming(
        "EURUSD",
        datetime(2020, 1, 1, 0, tzinfo=timezone.utc),
        datetime(2020, 1, 1, 3, tzinfo=timezone.utc),
        max_workers=1,
        batch_hours=3,
        pause_between_batches_seconds=0.0,
    )

    assert result.symbol == "EURUSD"
    assert len(result.sources) == 3
    assert result.sources[0].hour == "2020-01-01T00:00:00+00:00"
    assert result.sources[0].sha256 == hashlib.sha256(first).hexdigest()
    assert result.sources[1].hour == "2020-01-01T01:00:00+00:00"
    assert result.sources[1].status == "missing_404"
    assert result.sources[1].sha256 is None
    assert result.sources[2].hour == "2020-01-01T02:00:00+00:00"
    assert result.sources[2].sha256 == hashlib.sha256(third).hexdigest()
    assert not result.frame.empty
    assert result.frame["timestamp"].is_monotonic_increasing
    assert not result.frame["timestamp"].duplicated().any()
    assert result.frame["timestamp"].max() >= pd.Timestamp("2020-01-01T02:00:00Z")
    assert (result.frame["source"] == "dukascopy").all()
    assert (result.frame["asset"] == "EURUSD").all()
    assert (result.frame["market_type"] == "regular").all()


def test_streaming_downloader_respects_exact_interval_within_one_hour(monkeypatch):
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
        max_workers=1,
        batch_hours=1,
        pause_between_batches_seconds=0.0,
    )
    expected = pd.date_range(
        "2020-01-01T00:01:00Z", periods=2, freq="min", name="timestamp"
    )
    pd.testing.assert_index_equal(pd.DatetimeIndex(result.frame["timestamp"]), expected)
    assert len(result.sources) == 1


def test_streaming_downloader_rejects_empty_interval(monkeypatch):
    monkeypatch.setattr(stream, "fetch_bi5_bytes", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="no candles"):
        stream.download_candles_streaming(
            "EURUSD",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2020, 1, 1, 2, tzinfo=timezone.utc),
            max_workers=1,
            batch_hours=2,
            pause_between_batches_seconds=0.0,
        )


def test_streaming_downloader_validates_transport_batch_controls():
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2020, 1, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="max_workers"):
        stream.download_candles_streaming("EURUSD", start, end, max_workers=0)
    with pytest.raises(ValueError, match="batch_hours"):
        stream.download_candles_streaming("EURUSD", start, end, batch_hours=0)
    with pytest.raises(ValueError, match="pause_between_batches_seconds"):
        stream.download_candles_streaming(
            "EURUSD", start, end, pause_between_batches_seconds=-0.1
        )
