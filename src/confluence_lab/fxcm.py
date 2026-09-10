from __future__ import annotations

import gzip
import hashlib
import io
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from .data import validate_dataset


@dataclass(frozen=True)
class FXCMWeekFile:
    year: int
    week: int
    url: str
    downloaded_bytes: int
    sha256: str


@dataclass(frozen=True)
class FXCMDownloadResult:
    symbol: str
    year: int
    price_side: str
    frame: pd.DataFrame
    files: tuple[FXCMWeekFile, ...]
    missing_weeks: tuple[int, ...]


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    if len(normalized) != 6 or not normalized.isalpha():
        raise ValueError("FX symbol must look like EURUSD or EUR/USD")
    return normalized


def fxcm_week_url(symbol: str, year: int, week: int, *, periodicity: str = "m1") -> str:
    symbol = normalize_symbol(symbol)
    if year < 2000:
        raise ValueError("year is unexpectedly old")
    if not 1 <= week <= 53:
        raise ValueError("week must be between 1 and 53")
    if periodicity not in {"m1", "H1"}:
        raise ValueError("weekly FXCM downloader supports m1 or H1")
    return f"https://candledata.fxcorporate.com/{periodicity}/{symbol}/{year}/{week}.csv.gz"


def _column_lookup(frame: pd.DataFrame) -> dict[str, str]:
    return {str(column).strip().lower(): str(column) for column in frame.columns}


def normalize_fxcm_week(payload: bytes, *, price_side: str = "mid") -> pd.DataFrame:
    """Normalize one FXCM gzipped candle file.

    FXCM files expose bid and ask OHLC independently. ``mid`` derives each OHLC
    field from the corresponding bid/ask midpoint and retains open/close spread.
    """
    if price_side not in {"mid", "bid", "ask"}:
        raise ValueError("price_side must be one of: mid, bid, ask")
    if not payload:
        return pd.DataFrame(
            columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "spread_open", "spread_close",
            ]
        )

    raw = gzip.decompress(payload)
    source = pd.read_csv(io.BytesIO(raw))
    lookup = _column_lookup(source)

    timestamp_key = next(
        (lookup[key] for key in ("datetime", "date", "time") if key in lookup),
        None,
    )
    if timestamp_key is None:
        raise ValueError("FXCM file has no recognized datetime column")

    required = [
        "bidopen", "bidhigh", "bidlow", "bidclose",
        "askopen", "askhigh", "asklow", "askclose",
    ]
    missing = [key for key in required if key not in lookup]
    if missing:
        raise ValueError(f"FXCM file missing expected columns: {missing}")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(source[timestamp_key], utc=True, errors="raise")

    for part in ("open", "high", "low", "close"):
        bid = pd.to_numeric(source[lookup[f"bid{part}"]], errors="raise")
        ask = pd.to_numeric(source[lookup[f"ask{part}"]], errors="raise")
        if price_side == "mid":
            out[part] = (bid + ask) / 2.0
        elif price_side == "bid":
            out[part] = bid
        else:
            out[part] = ask

    tick_key = lookup.get("tickqty") or lookup.get("tick_volume") or lookup.get("volume")
    if tick_key is not None:
        out["volume"] = pd.to_numeric(source[tick_key], errors="coerce").fillna(0.0)

    out["spread_open"] = (
        pd.to_numeric(source[lookup["askopen"]], errors="raise")
        - pd.to_numeric(source[lookup["bidopen"]], errors="raise")
    )
    out["spread_close"] = (
        pd.to_numeric(source[lookup["askclose"]], errors="raise")
        - pd.to_numeric(source[lookup["bidclose"]], errors="raise")
    )
    out["spread_mean_proxy"] = (out["spread_open"] + out["spread_close"]) / 2.0
    return validate_dataset(out, allow_gaps=True)


def download_fxcm_week(
    symbol: str,
    year: int,
    week: int,
    *,
    price_side: str = "mid",
    timeout: float = 30.0,
) -> tuple[pd.DataFrame, FXCMWeekFile | None]:
    url = fxcm_week_url(symbol, year, week)
    request = Request(url, headers={"User-Agent": "ConfluenceLab/0.4"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed FXCM host
            payload = response.read()
    except HTTPError as exc:
        if exc.code == 404:
            return normalize_fxcm_week(b"", price_side=price_side), None
        raise

    provenance = FXCMWeekFile(
        year=year,
        week=week,
        url=url,
        downloaded_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    return normalize_fxcm_week(payload, price_side=price_side), provenance


def download_fxcm_year(
    symbol: str,
    year: int,
    *,
    price_side: str = "mid",
    timeout: float = 30.0,
) -> FXCMDownloadResult:
    symbol = normalize_symbol(symbol)
    pieces: list[pd.DataFrame] = []
    files: list[FXCMWeekFile] = []
    missing_weeks: list[int] = []

    for week in range(1, 54):
        frame, provenance = download_fxcm_week(
            symbol,
            year,
            week,
            price_side=price_side,
            timeout=timeout,
        )
        if provenance is None:
            missing_weeks.append(week)
            continue
        files.append(provenance)
        if not frame.empty:
            pieces.append(frame)

    if not pieces:
        raise RuntimeError(f"FXCM returned no {symbol} candle data for {year}")

    combined = pd.concat(pieces, ignore_index=True).sort_values("timestamp", kind="stable")
    combined = combined.reset_index(drop=True)
    combined = validate_dataset(combined, allow_gaps=True)
    return FXCMDownloadResult(
        symbol=symbol,
        year=year,
        price_side=price_side,
        frame=combined,
        files=tuple(files),
        missing_weeks=tuple(missing_weeks),
    )
