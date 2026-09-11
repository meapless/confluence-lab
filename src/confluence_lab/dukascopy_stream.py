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


@dataclass(frozen=True)
class DukascopyCandleDownload:
    symbol: str
    start: datetime
    end: datetime
    timeframe: str
    price: str
    frame: pd.DataFrame
    sources: tuple[DukascopySourceObject, ...]


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
    """Fetch one hourly Dukascopy BI5 object with bounded transient retries.

    HTTP 404 is the only status interpreted as a missing source object. HTTP
    429/500/502/503/504, URL-level transport errors and socket/SSL read
    ``TimeoutError`` exceptions are retried with deterministic exponential
    backoff. If the retry budget is exhausted, the original exception is
    raised: research data is never silently skipped because the provider is
    temporarily unavailable.
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
) -> DukascopyCandleDownload:
    """Build midpoint candles from canonical hourly Dukascopy raw-tick objects.

    Source objects are fetched in small fixed-concurrency batches, then decoded,
    resampled and discarded one hour at a time. The function never retains a
    full year of ticks in memory. ``executor.map`` preserves chronological input
    order, and the final candle frame is sorted and validated before return.
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

    hours = _hour_sequence(start_utc, end_utc)
    pieces: list[pd.DataFrame] = []
    sources: list[DukascopySourceObject] = []

    for batch_start in range(0, len(hours), batch_hours):
        batch = hours[batch_start : batch_start + batch_hours]
        workers = min(max_workers, len(batch))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            payloads = list(
                executor.map(
                    lambda hour: fetch_bi5_bytes(symbol, hour, timeout=timeout),
                    batch,
                )
            )

        for hour, payload in zip(batch, payloads, strict=True):
            url = dukascopy_tick_url(symbol, hour)
            if payload is None:
                sources.append(
                    DukascopySourceObject(
                        hour=hour.isoformat(),
                        url=url,
                        status="missing_404",
                        downloaded_bytes=0,
                        sha256=None,
                        ticks=0,
                        candles=0,
                    )
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
            sources.append(
                DukascopySourceObject(
                    hour=hour.isoformat(),
                    url=url,
                    status="downloaded",
                    downloaded_bytes=len(payload),
                    sha256=digest,
                    ticks=len(ticks),
                    candles=len(candles),
                )
            )

        if batch_start + batch_hours < len(hours) and pause_between_batches_seconds > 0:
            time.sleep(pause_between_batches_seconds)

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
        sources=tuple(sources),
    )
