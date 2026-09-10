from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .data import validate_dataset


def _timestamp_utc(value: Any) -> pd.Timestamp:
    numeric = float(value)
    unit = "ms" if abs(numeric) >= 1_000_000_000_000 else "s"
    return pd.to_datetime(numeric, unit=unit, utc=True)


def normalize_payout(value: Any) -> float:
    payout = float(value)
    if payout > 1.0:
        payout /= 100.0
    if not 0 <= payout <= 1:
        raise ValueError(f"unexpected Pocket payout value: {value!r}")
    return payout


def normalize_pocket_candles(
    payload: Any,
    *,
    asset: str,
    period_seconds: int,
    payout: float | None = None,
) -> pd.DataFrame:
    """Normalize supported Pocket history responses to Confluence Lab OHLC.

    The community wrapper documents candle arrays as
    [timestamp, open, close, high, low]. Dict-shaped candle records are also
    accepted defensively because wrapper versions have varied over time.
    """
    if period_seconds < 1:
        raise ValueError("period_seconds must be positive")

    raw_candles = payload.get("candles", []) if isinstance(payload, dict) else payload
    if raw_candles is None:
        raw_candles = []

    rows: list[dict[str, Any]] = []
    for item in raw_candles:
        try:
            if isinstance(item, dict):
                timestamp = item.get("timestamp", item.get("time", item.get("from")))
                row = {
                    "timestamp": _timestamp_utc(timestamp),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                }
            else:
                if len(item) < 5:
                    continue
                timestamp, open_price, close_price, high, low = item[:5]
                row = {
                    "timestamp": _timestamp_utc(timestamp),
                    "open": float(open_price),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close_price),
                }
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(row)

    if not rows:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "asset",
                "market_type",
                "period_seconds",
                "payout",
            ]
        )

    frame = validate_dataset(pd.DataFrame.from_records(rows))
    frame["asset"] = asset
    frame["market_type"] = "otc" if asset.lower().endswith("_otc") else "regular"
    frame["period_seconds"] = period_seconds
    frame["payout"] = payout
    return frame


@dataclass
class PocketResearchAdapter:
    """Research-only adapter around BinaryOptionsToolsAsync.

    Confluence Lab intentionally exposes data retrieval only. There are no
    buy/sell methods here, keeping research and execution separated.
    """

    ssid: str
    demo: bool = True
    _client: Any = None

    async def _ensure_client(self):
        if self._client is None:
            try:
                from BinaryOptionsToolsAsync.pocketoption import PocketOptionAsync
            except ImportError as exc:
                raise RuntimeError(
                    "BinaryOptionsToolsAsync is not installed. Install the optional "
                    "Pocket dependency in your local research environment."
                ) from exc
            self._client = PocketOptionAsync(self.ssid, demo=self.demo)
        return self._client

    async def get_payout(self, asset: str) -> float:
        client = await self._ensure_client()
        return normalize_payout(await client.get_payout(asset))

    async def get_candles(
        self,
        asset: str,
        *,
        period_seconds: int,
        duration_seconds: int,
        include_payout: bool = True,
    ) -> pd.DataFrame:
        client = await self._ensure_client()
        raw = await client.get_candles(asset, period_seconds, duration_seconds)
        payout = await self.get_payout(asset) if include_payout else None
        return normalize_pocket_candles(
            raw,
            asset=asset,
            period_seconds=period_seconds,
            payout=payout,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
