import argparse
import asyncio
import json
from pathlib import Path

import pandas as pd

from confluence_lab import pocket_watch_cli


def _candles(asset: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-10T12:00:00Z", periods=3, freq="1min"),
            "open": [1.10, 1.11, 1.12],
            "high": [1.12, 1.13, 1.14],
            "low": [1.09, 1.10, 1.11],
            "close": [1.11, 1.12, 1.13],
            "asset": [asset] * 3,
            "market_type": ["otc"] * 3,
            "period_seconds": [60] * 3,
            "payout": [None] * 3,
        }
    )


def test_single_cycle_records_multiple_assets_without_persisting_secret(monkeypatch, tmp_path):
    class FakeAdapter:
        def __init__(self, ssid, demo=True):
            assert ssid == "private-session"
            self.closed = False

        async def get_payout(self, asset):
            return 0.92 if asset == "EURUSD_otc" else 0.85

        async def get_candles(self, asset, *, period_seconds, duration_seconds):
            assert period_seconds == 60
            assert duration_seconds == 3600
            return _candles(asset)

        async def close(self):
            self.closed = True

    monkeypatch.setenv("POCKET_SSID", "private-session")
    monkeypatch.setattr(pocket_watch_cli, "PocketResearchAdapter", FakeAdapter)

    args = argparse.Namespace(
        assets=["EURUSD_otc", "GBPUSD_otc"],
        period_seconds=60,
        interval_seconds=60,
        duration_hours=1.0,
        iterations=1,
        snapshot_every=1,
        snapshot_duration_seconds=3600,
        output_dir=str(tmp_path / "raw"),
        payout_log=str(tmp_path / "payouts.jsonl"),
        manifest=str(tmp_path / "manifest.jsonl"),
        live_account=False,
    )
    result = asyncio.run(pocket_watch_cli._watch(args))
    assert result["cycles"] == 1
    assert result["payout_observations"] == 2
    assert result["snapshots"] == 2
    assert result["credential_persisted"] is False

    payouts = [json.loads(line) for line in Path(args.payout_log).read_text().splitlines()]
    assert {row["asset"] for row in payouts} == {"EURUSD_otc", "GBPUSD_otc"}
    assert {row["payout"] for row in payouts} == {0.92, 0.85}

    manifest = [json.loads(line) for line in Path(args.manifest).read_text().splitlines()]
    assert len(manifest) == 2
    assert {row["asset"] for row in manifest} == {"EURUSD_otc", "GBPUSD_otc"}
    all_text = Path(args.payout_log).read_text() + Path(args.manifest).read_text()
    assert "private-session" not in all_text


def test_cycle_count_is_bounded_and_validated():
    base = dict(
        assets=["EURUSD_otc"],
        period_seconds=60,
        interval_seconds=60,
        duration_hours=1.0,
        iterations=None,
        snapshot_every=15,
        snapshot_duration_seconds=3600,
        output_dir="unused",
        payout_log="unused",
        manifest="unused",
        live_account=False,
    )
    args = argparse.Namespace(**base)
    assert pocket_watch_cli._cycle_count(args) == 60

    args.iterations = 3
    assert pocket_watch_cli._cycle_count(args) == 3

    args.interval_seconds = 5
    try:
        pocket_watch_cli._cycle_count(args)
    except ValueError as exc:
        assert "at least 10" in str(exc)
    else:
        raise AssertionError("too-fast polling should be rejected")
