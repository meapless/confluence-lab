from __future__ import annotations

import hashlib
import lzma
import time
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
class DukascopyDaySource:
    day: str
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
    sources: tuple[DukascopyDaySource, ...]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _open_bi5_once(request: Request, *, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted host
        return response.read()


def fetch_bi5_bytes(
    symbol: str,
    day: datetime,
    *,
    timeout: float = 20.0,
    max_attempts: int = 5,
    backoff_seconds: float = 1.0,
) -> bytes | None:
    """Fetch one trusted Dukascopy BI5 object with bounded transient retries.

    HTTP 404 is the only status interpreted as a missing source object. HTTP
    429/500/502/503/504 and URL-level transport errors are retried with
    deterministic exponential backoff. If the retry budget is exhausted, the
    original exception is raised: research data is never silently skipped just
    because the provider is temporarily unavailable.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be non-negative")

    url = dukascopy_tick_url(symbol, day)
    request = Request(url, headers={"User-Agent": "ConfluenceLab/0.5"})

    for attempt in range(1, max_attempts + 1):
        try:
            return _open_bi5_once(request, timeout=timeout)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            retryable = exc.code in _TRANSIENT_HTTP_STATUS
            if not retryable or attempt == max_attempts:
                raise
        except URLError:
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
    """Decode a daily BI5 payload using NumPy rather than a Python tick loop."""
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
    base = pd.Timestamp(_utc(day)).normalize()
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


def download_candles_streaming(
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    timeframe: str = "1min",
    price: str = "mid",
    timeout: float = 20.0,
) -> DukascopyCandleDownload:
    """Build candles one day at a time while retaining raw-source SHA-256 provenance.

    Unlike ``download_range``, this function never retains the whole multi-day
    tick history in memory. Each BI5 day is decoded, converted to candles and
    discarded before the next day is processed. The BI5 decoder is vectorized,
    so the runtime scales with daily payload size without a Python object per tick.
    """
    symbol = normalize_symbol(symbol)
    start_utc = _utc(start)
    end_utc = _utc(end)
    if end_utc <= start_utc:
        raise ValueError("end must be after start")
    if price not in {"mid", "bid", "ask"}:
        raise ValueError("price must be one of: mid, bid, ask")

    pieces: list[pd.DataFrame] = []
    sources: list[DukascopyDaySource] = []
    current = start_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    final_day = (end_utc - timedelta(microseconds=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    while current <= final_day:
        url = dukascopy_tick_url(symbol, current)
        payload = fetch_bi5_bytes(symbol, current, timeout=timeout)
        if payload is None:
            sources.append(
                DukascopyDaySource(
                    day=current.date().isoformat(),
                    url=url,
                    status="missing_404",
                    downloaded_bytes=0,
                    sha256=None,
                    ticks=0,
                    candles=0,
                )
            )
            current += timedelta(days=1)
            continue

        digest = hashlib.sha256(payload).hexdigest()
        ticks = decode_bi5_ticks_vectorized(payload, symbol=symbol, day=current)
        candles = ticks_to_candles(ticks, timeframe=timeframe, price=price)
        if not candles.empty:
            mask = (candles["timestamp"] >= start_utc) & (candles["timestamp"] < end_utc)
            candles = candles.loc[mask].reset_index(drop=True)
            if not candles.empty:
                pieces.append(candles)
        sources.append(
            DukascopyDaySource(
                day=current.date().isoformat(),
                url=url,
                status="downloaded",
                downloaded_bytes=len(payload),
                sha256=digest,
                ticks=len(ticks),
                candles=len(candles),
            )
        )
        current += timedelta(days=1)

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
