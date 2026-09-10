from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .data import dataframe_fingerprint, diagnose_dataset
from .pocket_store import consolidate_pocket_frames


def _read_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"unsupported snapshot format: {path}")


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame.to_csv(path, index=False)
    elif suffix in {".parquet", ".pq"}:
        frame.to_parquet(path, index=False)
    else:
        raise ValueError("output must end in .csv, .parquet, or .pq")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consolidate overlapping Pocket research snapshots into one deduplicated dataset"
    )
    parser.add_argument(
        "--manifest",
        default="data/raw/pocket/snapshot_manifest.jsonl",
        help="Snapshot manifest written by confluence-pocket-capture",
    )
    parser.add_argument("--asset", required=True)
    parser.add_argument("--period-seconds", type=int, default=60)
    parser.add_argument(
        "--output",
        default=None,
        help="Consolidated output path; defaults under data/processed/pocket",
    )
    parser.add_argument(
        "--conflict-policy",
        choices=["raise", "prefer_last"],
        default="raise",
        help="How to handle snapshots that disagree on OHLC for the same timestamp",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"snapshot manifest not found: {manifest_path}")

    entries: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("asset") != args.asset:
            continue
        if int(entry.get("period_seconds", -1)) != args.period_seconds:
            continue
        snapshot_id = str(entry.get("snapshot_id", ""))
        if not snapshot_id or snapshot_id in seen_ids:
            continue
        seen_ids.add(snapshot_id)
        entries.append(entry)

    if not entries:
        raise SystemExit(
            f"no snapshots found for asset={args.asset} period_seconds={args.period_seconds}"
        )

    frames: list[pd.DataFrame] = []
    verified_entries: list[dict[str, object]] = []
    for entry in entries:
        path = Path(str(entry["relative_path"]))
        if not path.exists():
            raise SystemExit(f"snapshot file from manifest does not exist: {path}")
        frame = _read_frame(path)
        frames.append(frame)
        verified_entries.append(
            {
                "snapshot_id": entry["snapshot_id"],
                "relative_path": str(path),
                "manifest_rows": entry.get("rows"),
                "manifest_fingerprint": entry.get("candle_fingerprint"),
                "loaded_rows": len(frame),
            }
        )

    input_rows = sum(len(frame) for frame in frames)
    consolidated = consolidate_pocket_frames(
        frames,
        conflict_policy=args.conflict_policy,
    )
    output = Path(
        args.output
        or f"data/processed/pocket/{args.asset}_{args.period_seconds}s_consolidated.parquet"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_frame(consolidated, output)

    metadata = {
        "kind": "pocket_snapshot_consolidation",
        "asset": args.asset,
        "period_seconds": args.period_seconds,
        "conflict_policy": args.conflict_policy,
        "manifest": str(manifest_path),
        "snapshots": verified_entries,
        "snapshot_count": len(verified_entries),
        "input_rows": input_rows,
        "consolidated_rows": len(consolidated),
        "overlapping_rows_removed": input_rows - len(consolidated),
        "fingerprint": dataframe_fingerprint(consolidated),
        "diagnostics": asdict(diagnose_dataset(consolidated)),
        "historical_payout_attached": False,
    }
    metadata_path = output.with_suffix(".meta.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output": str(output),
                "metadata": str(metadata_path),
                "snapshots": len(verified_entries),
                "input_rows": input_rows,
                "consolidated_rows": len(consolidated),
                "overlapping_rows_removed": input_rows - len(consolidated),
                "fingerprint": metadata["fingerprint"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
