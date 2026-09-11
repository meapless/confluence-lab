from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from .data import validate_dataset
from .dukascopy import (
    decode_bi5_ticks,
    dukascopy_tick_url,
    normalize_symbol,
    ticks_to_candles,
)


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


def fetch_bi5_bytes(symbol: str, day: datetime, *, timeout: float = 20.0) -> bytes | None:
    """Fetch one trusted Dukascopy BI5 object; return None only for HTTP 404."""
    url = dukascopy_tick_url(symbol, day)
    request = Request(url, headers={"User-Agent": "ConfluenceLab/0.5"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted host
            return response.read()
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise


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
    discarded before the next day is processed. This makes full-year M1 source
    replication practical while keeping every raw object auditable.
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
        ticks = decode_bi5_ticks(payload, symbol=symbol, day=current)
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
