from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .data import dataframe_fingerprint, diagnose_dataset
from .dukascopy import download_range, normalize_symbol


def _parse_datetime(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "use ISO-8601, e.g. 2026-09-01 or 2026-09-01T12:00:00+00:00"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _write_frame(frame, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame.to_csv(path, index=False)
    elif suffix in {".parquet", ".pq"}:
        try:
            frame.to_parquet(path, index=False)
        except ImportError as exc:
            raise RuntimeError(
                "Parquet output requires pyarrow. Install the project dependencies "
                "with: pip install -e ."
            ) from exc
    else:
        raise ValueError("output must end in .csv, .parquet, or .pq")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download independent Dukascopy FX ticks and aggregate research candles"
    )
    parser.add_argument("symbol", help="FX pair such as EURUSD or EUR/USD")
    parser.add_argument("--start", required=True, type=_parse_datetime)
    parser.add_argument("--end", required=True, type=_parse_datetime)
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--output", default=None, help="Parquet candle output path")
    parser.add_argument("--ticks-output", default=None, help="Optional Parquet tick output path")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbol = normalize_symbol(args.symbol)
    result = download_range(
        symbol,
        args.start,
        args.end,
        timeframe=args.timeframe,
        timeout=args.timeout,
    )
    if result.candles.empty:
        raise SystemExit("No Dukascopy candles were returned for the requested interval")

    candles = result.candles.copy()
    candles["asset"] = symbol
    candles["market_type"] = "regular"
    candles["source"] = "dukascopy"
    candles["timeframe"] = args.timeframe

    default_name = (
        f"{symbol}_{result.start:%Y%m%d%H}_{result.end:%Y%m%d%H}_{args.timeframe}.parquet"
    )
    output = Path(args.output or f"data/raw/dukascopy/{default_name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_frame(candles, output)

    ticks_output = None
    if args.ticks_output:
        ticks_output = Path(args.ticks_output)
        ticks_output.parent.mkdir(parents=True, exist_ok=True)
        _write_frame(result.ticks, ticks_output)

    diagnostics = diagnose_dataset(candles)
    metadata = {
        "source": "dukascopy",
        "symbol": symbol,
        "requested_start": args.start.isoformat(),
        "requested_end": args.end.isoformat(),
        "normalized_start": result.start.isoformat(),
        "normalized_end": result.end.isoformat(),
        "timeframe": args.timeframe,
        "tick_rows": len(result.ticks),
        "candle_rows": len(candles),
        "candle_fingerprint": dataframe_fingerprint(candles),
        "diagnostics": asdict(diagnostics),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "payout_history_available": False,
        "note": (
            "Dukascopy provides independent regular-FX market data. It does not provide "
            "historical Pocket Option payout observations; use fixed-payout scenario analysis "
            "or separately observed payout data rather than inventing historical payouts."
        ),
    }
    metadata_path = output.with_suffix(".meta.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "candles": str(output),
                "metadata": str(metadata_path),
                "ticks": str(ticks_output) if ticks_output else None,
                "rows": len(candles),
                "fingerprint": metadata["candle_fingerprint"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
