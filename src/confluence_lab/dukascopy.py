from __future__ import annotations

import lzma
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

_TICK = struct.Struct(">IIIff")


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    if len(normalized) != 6 or not normalized.isalpha():
        raise ValueError("FX symbol must look like EURUSD or EUR/USD")
    return normalized


def price_divisor(symbol: str) -> int:
    return 1_000 if normalize_symbol(symbol).endswith("JPY") else 100_000


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_utc_day(value: datetime) -> datetime:
    value = _as_utc(value)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def dukascopy_tick_url(symbol: str, day: datetime) -> str:
    """Return the current daily Dukascopy BI5 datafeed URL.

    Dukascopy months are zero-indexed in the datafeed path: January=00.
    """
    symbol = normalize_symbol(symbol)
    day = _as_utc_day(day)
    month = day.month - 1
    return (
        "https://www.dukascopy.com/datafeed/"
        f"{symbol}/{day.year}/{month:02d}/{day.day:02d}_ticks.bi5"
    )


def decode_bi5_ticks(payload: bytes, *, symbol: str, day: datetime) -> pd.DataFrame:
    """Decode one LZMA-compressed Dukascopy daily tick file."""
    if not payload:
        return pd.DataFrame(
            columns=["timestamp", "ask", "bid", "ask_volume", "bid_volume"]
        )
    raw = lzma.decompress(payload)
    if len(raw) % _TICK.size:
        raise ValueError("BI5 payload length is not a multiple of the 20-byte tick record")

    base = _as_utc_day(day)
    divisor = price_divisor(symbol)
    rows: list[dict[str, object]] = []
    for millisecond, ask_raw, bid_raw, ask_volume, bid_volume in _TICK.iter_unpack(raw):
        rows.append(
            {
                "timestamp": base + timedelta(milliseconds=millisecond),
                "ask": ask_raw / divisor,
                "bid": bid_raw / divisor,
                "ask_volume": float(ask_volume),
                "bid_volume": float(bid_volume),
            }
        )
    return pd.DataFrame.from_records(rows)


def fetch_tick_day(symbol: str, day: datetime, *, timeout: float = 20.0) -> pd.DataFrame:
    """Download and decode one daily Dukascopy tick file.

    Missing/holiday days return an empty frame. Network/server failures other
    than 404 are raised so a research dataset cannot silently skip outages.
    """
    url = dukascopy_tick_url(symbol, day)
    request = Request(url, headers={"User-Agent": "ConfluenceLab/0.3"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted host
            payload = response.read()
    except HTTPError as exc:
        if exc.code == 404:
            return decode_bi5_ticks(b"", symbol=symbol, day=day)
        raise
    return decode_bi5_ticks(payload, symbol=symbol, day=day)


def ticks_to_candles(
    ticks: pd.DataFrame,
    *,
    timeframe: str = "1min",
    price: str = "mid",
) -> pd.DataFrame:
    if ticks.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "spread_mean",
            ]
        )
    required = {"timestamp", "ask", "bid", "ask_volume", "bid_volume"}
    missing = required - set(ticks.columns)
    if missing:
        raise ValueError(f"tick data missing columns: {sorted(missing)}")
    if price not in {"mid", "bid", "ask"}:
        raise ValueError("price must be one of: mid, bid, ask")

    frame = ticks.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp", kind="stable").set_index("timestamp")
    if price == "mid":
        frame["price"] = (frame["ask"] + frame["bid"]) / 2.0
    else:
        frame["price"] = frame[price]
    frame["volume"] = frame["ask_volume"] + frame["bid_volume"]
    frame["spread"] = frame["ask"] - frame["bid"]

    bars = frame["price"].resample(timeframe).ohlc()
    bars["volume"] = frame["volume"].resample(timeframe).sum()
    bars["spread_mean"] = frame["spread"].resample(timeframe).mean()
    return bars.dropna(subset=["open", "high", "low", "close"]).reset_index()


@dataclass(frozen=True)
class DukascopyDownloadResult:
    symbol: str
    start: datetime
    end: datetime
    ticks: pd.DataFrame
    candles: pd.DataFrame


def download_range(
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    timeframe: str = "1min",
    timeout: float = 20.0,
) -> DukascopyDownloadResult:
    """Download an exact UTC interval [start, end) using daily BI5 files."""
    symbol = normalize_symbol(symbol)
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    if end_utc <= start_utc:
        raise ValueError("end must be after start")

    pieces: list[pd.DataFrame] = []
    current_day = _as_utc_day(start_utc)
    last_day = _as_utc_day(end_utc - timedelta(microseconds=1))
    while current_day <= last_day:
        ticks = fetch_tick_day(symbol, current_day, timeout=timeout)
        if not ticks.empty:
            pieces.append(ticks)
        current_day += timedelta(days=1)

    if pieces:
        all_ticks = pd.concat(pieces, ignore_index=True).sort_values(
            "timestamp", kind="stable"
        )
        mask = (all_ticks["timestamp"] >= start_utc) & (all_ticks["timestamp"] < end_utc)
        all_ticks = all_ticks.loc[mask].reset_index(drop=True)
    else:
        all_ticks = decode_bi5_ticks(b"", symbol=symbol, day=start_utc)

    candles = ticks_to_candles(all_ticks, timeframe=timeframe)
    return DukascopyDownloadResult(symbol, start_utc, end_utc, all_ticks, candles)
