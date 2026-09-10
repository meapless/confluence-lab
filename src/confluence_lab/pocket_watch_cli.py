from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from .pocket import PocketResearchAdapter
from .pocket_capture_cli import _write_frame
from .pocket_store import append_snapshot_manifest, make_snapshot_manifest_entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Observe Pocket payouts frequently and capture overlapping candle snapshots locally"
    )
    parser.add_argument("assets", nargs="+", help="Pocket assets, e.g. EURUSD_otc GBPUSD_otc")
    parser.add_argument("--period-seconds", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--duration-hours", type=float, default=6.0)
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Optional exact cycle count, mainly for controlled runs/tests; overrides duration-hours",
    )
    parser.add_argument(
        "--snapshot-every",
        type=int,
        default=15,
        help="Capture candles every N payout-observation cycles",
    )
    parser.add_argument("--snapshot-duration-seconds", type=int, default=3600)
    parser.add_argument("--output-dir", default="data/raw/pocket")
    parser.add_argument(
        "--payout-log",
        default="data/raw/pocket/payout_observations.jsonl",
    )
    parser.add_argument(
        "--manifest",
        default="data/raw/pocket/snapshot_manifest.jsonl",
    )
    parser.add_argument("--live-account", action="store_true")
    return parser


def _cycle_count(args: argparse.Namespace) -> int:
    if args.interval_seconds < 10:
        raise ValueError("interval-seconds must be at least 10")
    if args.snapshot_every < 1:
        raise ValueError("snapshot-every must be positive")
    if args.period_seconds < 1 or args.snapshot_duration_seconds < 1:
        raise ValueError("period and snapshot duration must be positive")
    if args.iterations is not None:
        if args.iterations < 1:
            raise ValueError("iterations must be positive")
        return args.iterations
    if args.duration_hours <= 0:
        raise ValueError("duration-hours must be positive")
    return max(1, math.ceil(args.duration_hours * 3600.0 / args.interval_seconds))


async def _watch(args: argparse.Namespace) -> dict[str, object]:
    ssid = os.environ.get("POCKET_SSID")
    if not ssid:
        raise SystemExit(
            "POCKET_SSID is not set. Keep the session value in your local shell environment; "
            "never commit it to the repository."
        )

    cycles = _cycle_count(args)
    output_dir = Path(args.output_dir)
    payout_log = Path(args.payout_log)
    manifest = Path(args.manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    payout_log.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    account_mode = "live" if args.live_account else "demo"

    adapter = PocketResearchAdapter(ssid=ssid, demo=not args.live_account)
    payout_observations = 0
    snapshots = 0
    started_at = datetime.now(timezone.utc)
    try:
        for cycle in range(cycles):
            observed_at = datetime.now(timezone.utc)
            for asset in args.assets:
                payout = await adapter.get_payout(asset)
                observation = {
                    "asset": asset,
                    "observed_at": observed_at.isoformat(),
                    "payout": payout,
                    "account_mode": account_mode,
                    "observer": "confluence-pocket-watch",
                }
                with payout_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(observation, sort_keys=True) + "\n")
                payout_observations += 1

                if cycle % args.snapshot_every == 0:
                    candles = await adapter.get_candles(
                        asset,
                        period_seconds=args.period_seconds,
                        duration_seconds=args.snapshot_duration_seconds,
                    )
                    if candles.empty:
                        continue
                    candles = candles.copy()
                    candles["source"] = "pocket"
                    filename = (
                        f"{asset}_{observed_at:%Y%m%dT%H%M%SZ}_"
                        f"{args.period_seconds}s.parquet"
                    )
                    output = output_dir / filename
                    _write_frame(candles, output)
                    entry = make_snapshot_manifest_entry(
                        candles,
                        asset=asset,
                        period_seconds=args.period_seconds,
                        observed_at=observed_at,
                        account_mode=account_mode,
                        relative_path=str(output),
                    )
                    append_snapshot_manifest(manifest, entry)
                    snapshots += 1

            if cycle + 1 < cycles:
                await asyncio.sleep(args.interval_seconds)
    finally:
        await adapter.close()

    finished_at = datetime.now(timezone.utc)
    return {
        "assets": list(args.assets),
        "account_mode": account_mode,
        "cycles": cycles,
        "interval_seconds": args.interval_seconds,
        "payout_observations": payout_observations,
        "snapshots": snapshots,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "payout_log": str(payout_log),
        "manifest": str(manifest),
        "credential_persisted": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = asyncio.run(_watch(args))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
