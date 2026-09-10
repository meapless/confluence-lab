from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .data import dataframe_fingerprint, diagnose_dataset
from .pocket import PocketResearchAdapter
from .pocket_store import append_snapshot_manifest, make_snapshot_manifest_entry


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
        description="Capture Pocket research candles plus a timestamped current-payout observation"
    )
    parser.add_argument("asset", help="Pocket asset, e.g. EURUSD_otc")
    parser.add_argument("--period-seconds", type=int, default=60)
    parser.add_argument("--duration-seconds", type=int, default=86_400)
    parser.add_argument("--output", default=None, help="Parquet candle output path")
    parser.add_argument(
        "--payout-log",
        default="data/raw/pocket/payout_observations.jsonl",
        help="Append-only JSONL file for timestamped payout observations",
    )
    parser.add_argument(
        "--manifest",
        default="data/raw/pocket/snapshot_manifest.jsonl",
        help="Append-only JSONL manifest describing every captured candle snapshot",
    )
    parser.add_argument(
        "--live-account",
        action="store_true",
        help="Connect to a live account instead of demo; data retrieval only",
    )
    return parser


async def _capture(args: argparse.Namespace) -> dict[str, object]:
    ssid = os.environ.get("POCKET_SSID")
    if not ssid:
        raise SystemExit(
            "POCKET_SSID is not set. Put the session value in your shell environment; "
            "never commit it to the repository."
        )

    adapter = PocketResearchAdapter(ssid=ssid, demo=not args.live_account)
    try:
        candles = await adapter.get_candles(
            args.asset,
            period_seconds=args.period_seconds,
            duration_seconds=args.duration_seconds,
        )
        observed_at = datetime.now(timezone.utc)
        current_payout = await adapter.get_payout(args.asset)
    finally:
        await adapter.close()

    if candles.empty:
        raise SystemExit("Pocket returned no candles for the requested snapshot")

    # Critical: current payout is NOT copied onto historical candles. It is a
    # separately timestamped observation and is only valid for its observation time.
    candles = candles.copy()
    candles["source"] = "pocket"
    default_name = f"{args.asset}_{observed_at:%Y%m%dT%H%M%SZ}_{args.period_seconds}s.parquet"
    output = Path(args.output or f"data/raw/pocket/{default_name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_frame(candles, output)

    payout_log = Path(args.payout_log)
    payout_log.parent.mkdir(parents=True, exist_ok=True)
    account_mode = "live" if args.live_account else "demo"
    payout_observation = {
        "asset": args.asset,
        "observed_at": observed_at.isoformat(),
        "payout": current_payout,
        "account_mode": account_mode,
    }
    with payout_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payout_observation, sort_keys=True) + "\n")

    manifest_arg = getattr(args, "manifest", None)
    manifest_path = Path(manifest_arg) if manifest_arg else output.parent / "snapshot_manifest.jsonl"
    manifest_entry = make_snapshot_manifest_entry(
        candles,
        asset=args.asset,
        period_seconds=args.period_seconds,
        observed_at=observed_at,
        account_mode=account_mode,
        relative_path=str(output),
    )
    append_snapshot_manifest(manifest_path, manifest_entry)

    diagnostics = diagnose_dataset(candles)
    metadata = {
        "source": "pocket",
        "asset": args.asset,
        "period_seconds": args.period_seconds,
        "duration_seconds_requested": args.duration_seconds,
        "account_mode": account_mode,
        "candle_rows": len(candles),
        "candle_fingerprint": dataframe_fingerprint(candles),
        "diagnostics": asdict(diagnostics),
        "payout_observation": payout_observation,
        "snapshot_manifest_entry": asdict(manifest_entry),
        "historical_payout_backfill": False,
        "credential_persisted": False,
    }
    metadata_path = output.with_suffix(".meta.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    return {
        "candles": str(output),
        "metadata": str(metadata_path),
        "payout_log": str(payout_log),
        "manifest": str(manifest_path),
        "snapshot_id": manifest_entry.snapshot_id,
        "rows": len(candles),
        "fingerprint": metadata["candle_fingerprint"],
        "payout_observed_at": payout_observation["observed_at"],
        "current_payout": current_payout,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(asyncio.run(_capture(args)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
