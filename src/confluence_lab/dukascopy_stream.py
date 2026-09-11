from __future__ import annotations

import hashlib
import lzma
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from .data import validate_dataset
from .dukascopy import (
    dukascopy_tick_url,
    normalize_symbol,
    price_divisor,
    ticks_to_candles,
)

_BI5_DTYPE = np.dtype(
    [
        ("millisecond", ">u4"),
        ("ask_raw", ">u4"),
        ("bid_raw", ">u4"),
        ("ask_volume", ">f4"),
        ("bid_volume", ">f4"),
    ]
)
_TRANSIENT_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class DukascopySourceObject:
    hour: str
    url: str
    status: str
    downloaded_bytes: int
    sha256: str | None
    ticks: int
    candles: int
    retrieval_pass: int


@dataclass(frozen=True)
class DukascopySourceFailure:
    hour: str
    url: str
    error_type: str
    error_message: str
    completion_pass: int


class DukascopyAcquisitionError(RuntimeError):
    """Raised only after required source objects remain unavailable at final pass."""

    def __init__(
        self,
        *,
        failures: tuple[DukascopySourceFailure, ...],
        sources: tuple[DukascopySourceObject, ...],
        requested_objects: int,
        completion_passes: int,
    ) -> None:
        self.failures = failures
        self.sources = sources
        self.requested_objects = int(requested_objects)
        self.completion_passes = int(completion_passes)
        hours = ", ".join(item.hour for item in failures[:5])
        suffix = "" if len(failures) <= 5 else f" (+{len(failures) - 5} more)"
        super().__init__(
            f"Dukascopy acquisition incomplete after {completion_passes} completion passes; "
            f"{len(failures)} required source object(s) unavailable: {hours}{suffix}"
        )


@dataclass(frozen=True)
class DukascopyCandleDownload:
    symbol: str
    start: datetime
    end: datetime
    timeframe: str
    price: str
    frame: pd.DataFrame
    sources: tuple[DukascopySourceObject, ...]
    completion_passes_used: int


@dataclass(frozen=True)
class _FetchOutcome:
    hour: datetime
    payload: bytes | None
    failure: DukascopySourceFailure | None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_hour(value: datetime) -> datetime:
    value = _utc(value)
    return value.replace(minute=0, second=0, microsecond=0)


def _open_bi5_once(request: Request, *, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted host
        return response.read()


def fetch_bi5_bytes(
    symbol: str,
    hour: datetime,
    *,
    timeout: float = 20.0,
    max_attempts: int = 5,
    backoff_seconds: float = 1.0,
) -> bytes | None:
    """Fetch one hourly Dukascopy BI5 object with bounded local retries.

    HTTP 404 is the only status interpreted as a missing source object. HTTP
    429/500/502/503/504, URL-level transport errors and socket/SSL read
    ``TimeoutError`` exceptions are retried with deterministic exponential
    backoff. If the local retry budget is exhausted, the exception is raised to
    the completion-pass orchestrator; research data is never silently skipped.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be non-negative")

    hour = _utc_hour(hour)
    url = dukascopy_tick_url(symbol, hour)
    request = Request(url, headers={"User-Agent": "ConfluenceLab/0.6"})

    for attempt in range(1, max_attempts + 1):
        try:
            return _open_bi5_once(request, timeout=timeout)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            retryable = exc.code in _TRANSIENT_HTTP_STATUS
            if not retryable or attempt == max_attempts:
                raise
        except (URLError, TimeoutError):
            if attempt == max_attempts:
                raise

        delay = backoff_seconds * (2 ** (attempt - 1))
        if delay > 0:
            time.sleep(delay)

    raise RuntimeError("unreachable BI5 retry state")


def _capture_fetch(
    symbol: str,
    hour: datetime,
    *,
    timeout: float,
    completion_pass: int,
) -> _FetchOutcome:
    try:
        payload = fetch_bi5_bytes(symbol, hour, timeout=timeout)
    except (HTTPError, URLError, TimeoutError) as exc:
        return _FetchOutcome(
            hour=hour,
            payload=None,
            failure=DukascopySourceFailure(
                hour=hour.isoformat(),
                url=dukascopy_tick_url(symbol, hour),
                error_type=type(exc).__name__,
                error_message=str(exc),
                completion_pass=completion_pass,
            ),
        )
    return _FetchOutcome(hour=hour, payload=payload, failure=None)


def decode_bi5_ticks_vectorized(
    payload: bytes,
    *,
    symbol: str,
    day: datetime,
) -> pd.DataFrame:
    """Decode one hourly BI5 payload using NumPy rather than a Python tick loop.

    ``day`` remains the keyword for compatibility with the reference decoder,
    but its hour component is significant because BI5 offsets are hour-relative.
    """
    columns = ["timestamp", "ask", "bid", "ask_volume", "bid_volume"]
    if not payload:
        return pd.DataFrame(columns=columns)

    raw = lzma.decompress(payload)
    if len(raw) % _BI5_DTYPE.itemsize:
        raise ValueError("BI5 payload length is not a multiple of the 20-byte tick record")
    values = np.frombuffer(raw, dtype=_BI5_DTYPE)
    if len(values) == 0:
        return pd.DataFrame(columns=columns)

    symbol = normalize_symbol(symbol)
    base = pd.Timestamp(_utc_hour(day))
    divisor = float(price_divisor(symbol))
    timestamps = base + pd.to_timedelta(
        values["millisecond"].astype(np.int64), unit="ms"
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "ask": values["ask_raw"].astype(np.float64) / divisor,
            "bid": values["bid_raw"].astype(np.float64) / divisor,
            "ask_volume": values["ask_volume"].astype(np.float64),
            "bid_volume": values["bid_volume"].astype(np.float64),
        }
    )


def _hour_sequence(start: datetime, end: datetime) -> list[datetime]:
    current = _utc_hour(start)
    final = _utc_hour(end - timedelta(microseconds=1))
    hours: list[datetime] = []
    while current <= final:
        hours.append(current)
        current += timedelta(hours=1)
    return hours


def download_candles_streaming(
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    timeframe: str = "1min",
    price: str = "mid",
    timeout: float = 20.0,
    max_workers: int = 4,
    batch_hours: int = 24,
    pause_between_batches_seconds: float = 0.25,
    max_completion_passes: int = 3,
    pause_between_completion_passes_seconds: float = 15.0,
) -> DukascopyCandleDownload:
    """Build midpoint candles from canonical hourly Dukascopy raw-tick objects.

    Source objects are fetched in small fixed-concurrency batches, then decoded,
    resampled and discarded one hour at a time. An hourly object that exhausts
    its local transport retries is deferred rather than causing immediate loss
    of the otherwise-successful year build. Only failed hours enter subsequent
    completion passes. If any required non-404 object remains unavailable after
    the frozen pass budget, ``DukascopyAcquisitionError`` is raised with an exact
    failure/source manifest. Nothing is silently omitted.
    """
    symbol = normalize_symbol(symbol)
    start_utc = _utc(start)
    end_utc = _utc(end)
    if end_utc <= start_utc:
        raise ValueError("end must be after start")
    if price not in {"mid", "bid", "ask"}:
        raise ValueError("price must be one of: mid, bid, ask")
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    if batch_hours < 1:
        raise ValueError("batch_hours must be >= 1")
    if pause_between_batches_seconds < 0:
        raise ValueError("pause_between_batches_seconds must be non-negative")
    if max_completion_passes < 1:
        raise ValueError("max_completion_passes must be >= 1")
    if pause_between_completion_passes_seconds < 0:
        raise ValueError("pause_between_completion_passes_seconds must be non-negative")

    hours = _hour_sequence(start_utc, end_utc)
    pending = list(hours)
    pieces: list[pd.DataFrame] = []
    source_by_hour: dict[datetime, DukascopySourceObject] = {}
    final_failures: tuple[DukascopySourceFailure, ...] = ()
    completion_passes_used = 0

    for completion_pass in range(1, max_completion_passes + 1):
        completion_passes_used = completion_pass
        pass_failures: list[DukascopySourceFailure] = []

        for batch_start in range(0, len(pending), batch_hours):
            batch = pending[batch_start : batch_start + batch_hours]
            workers = min(max_workers, len(batch))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                outcomes = list(
                    executor.map(
                        lambda hour: _capture_fetch(
                            symbol,
                            hour,
                            timeout=timeout,
                            completion_pass=completion_pass,
                        ),
                        batch,
                    )
                )

            for outcome in outcomes:
                hour = outcome.hour
                if outcome.failure is not None:
                    pass_failures.append(outcome.failure)
                    continue

                payload = outcome.payload
                url = dukascopy_tick_url(symbol, hour)
                if payload is None:
                    source_by_hour[hour] = DukascopySourceObject(
                        hour=hour.isoformat(),
                        url=url,
                        status="missing_404",
                        downloaded_bytes=0,
                        sha256=None,
                        ticks=0,
                        candles=0,
                        retrieval_pass=completion_pass,
                    )
                    continue

                digest = hashlib.sha256(payload).hexdigest()
                ticks = decode_bi5_ticks_vectorized(payload, symbol=symbol, day=hour)
                candles = ticks_to_candles(ticks, timeframe=timeframe, price=price)
                if not candles.empty:
                    mask = (candles["timestamp"] >= start_utc) & (candles["timestamp"] < end_utc)
                    candles = candles.loc[mask].reset_index(drop=True)
                    if not candles.empty:
                        pieces.append(candles)
                source_by_hour[hour] = DukascopySourceObject(
                    hour=hour.isoformat(),
                    url=url,
                    status="downloaded",
                    downloaded_bytes=len(payload),
                    sha256=digest,
                    ticks=len(ticks),
                    candles=len(candles),
                    retrieval_pass=completion_pass,
                )

            if batch_start + batch_hours < len(pending) and pause_between_batches_seconds > 0:
                time.sleep(pause_between_batches_seconds)

        if not pass_failures:
            final_failures = ()
            break

        final_failures = tuple(pass_failures)
        pending = [datetime.fromisoformat(item.hour) for item in pass_failures]
        if completion_pass < max_completion_passes and pause_between_completion_passes_seconds > 0:
            time.sleep(pause_between_completion_passes_seconds)

    ordered_sources = tuple(source_by_hour[hour] for hour in sorted(source_by_hour))
    if final_failures:
        raise DukascopyAcquisitionError(
            failures=final_failures,
            sources=ordered_sources,
            requested_objects=len(hours),
            completion_passes=completion_passes_used,
        )

    if len(ordered_sources) != len(hours):
        raise RuntimeError(
            "Dukascopy acquisition completed without failures but source manifest is incomplete"
        )
    if not pieces:
        raise ValueError("Dukascopy returned no candles for the requested interval")

    frame = pd.concat(pieces, ignore_index=True)
    frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    frame = validate_dataset(frame)
    frame["source"] = "dukascopy"
    frame["asset"] = symbol
    frame["market_type"] = "regular"

    return DukascopyCandleDownload(
        symbol=symbol,
        start=start_utc,
        end=end_utc,
        timeframe=timeframe,
        price=price,
        frame=frame,
        sources=ordered_sources,
        completion_passes_used=completion_passes_used,
    )
