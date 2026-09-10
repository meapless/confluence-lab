import json

import pandas as pd

from confluence_lab.pocket_consolidate_cli import main
from confluence_lab.pocket_store import make_snapshot_manifest_entry


def _snapshot(start: str, closes: list[float]) -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=len(closes), freq="1min", tz="UTC")
    opens = [value - 0.01 for value in closes]
    highs = [max(o, c) + 0.01 for o, c in zip(opens, closes, strict=True)]
    lows = [min(o, c) - 0.01 for o, c in zip(opens, closes, strict=True)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "asset": "EURUSD_otc",
            "market_type": "otc",
            "period_seconds": 60,
            "payout": None,
            "source": "pocket",
        }
    )


def test_consolidate_cli_removes_identical_overlap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = _snapshot("2026-09-10T12:00:00Z", [1.10, 1.11, 1.12])
    second = _snapshot("2026-09-10T12:02:00Z", [1.12, 1.13, 1.14])
    paths = [tmp_path / "one.csv", tmp_path / "two.csv"]
    first.to_csv(paths[0], index=False)
    second.to_csv(paths[1], index=False)

    manifest = tmp_path / "manifest.jsonl"
    entries = [
        make_snapshot_manifest_entry(
            first,
            asset="EURUSD_otc",
            period_seconds=60,
            observed_at="2026-09-10T12:03:30Z",
            account_mode="demo",
            relative_path=str(paths[0]),
        ),
        make_snapshot_manifest_entry(
            second,
            asset="EURUSD_otc",
            period_seconds=60,
            observed_at="2026-09-10T12:05:30Z",
            account_mode="demo",
            relative_path=str(paths[1]),
        ),
    ]
    manifest.write_text(
        "".join(json.dumps(entry.__dict__) + "\n" for entry in entries),
        encoding="utf-8",
    )
    output = tmp_path / "combined.csv"
    assert main(
        [
            "--manifest",
            str(manifest),
            "--asset",
            "EURUSD_otc",
            "--period-seconds",
            "60",
            "--output",
            str(output),
        ]
    ) == 0
    combined = pd.read_csv(output)
    assert len(combined) == 5
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["snapshot_count"] == 2
    assert metadata["input_rows"] == 6
    assert metadata["consolidated_rows"] == 5
    assert metadata["overlapping_rows_removed"] == 1
    assert metadata["historical_payout_attached"] is False
