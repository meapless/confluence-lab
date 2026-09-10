import argparse
import asyncio
import json

import pandas as pd
import pytest

from confluence_lab import fx_cli, pocket_capture_cli
from confluence_lab.dukascopy import DukascopyDownloadResult


def _candles():
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-10T12:00:00Z", periods=3, freq="min"),
            "open": [1.10, 1.11, 1.12],
            "high": [1.12, 1.13, 1.14],
            "low": [1.09, 1.10, 1.11],
            "close": [1.11, 1.12, 1.13],
        }
    )


def test_fx_cli_writes_candles_and_provenance(monkeypatch, tmp_path):
    candles = _candles()
    ticks = pd.DataFrame(
        {
            "timestamp": candles["timestamp"],
            "ask": [1.11, 1.12, 1.13],
            "bid": [1.10, 1.11, 1.12],
            "ask_volume": [1.0, 1.0, 1.0],
            "bid_volume": [1.0, 1.0, 1.0],
        }
    )
    start = fx_cli._parse_datetime("2026-09-10T12:00:00Z")
    end = fx_cli._parse_datetime("2026-09-10T13:00:00Z")
    monkeypatch.setattr(
        fx_cli,
        "download_range",
        lambda *args, **kwargs: DukascopyDownloadResult("EURUSD", start, end, ticks, candles),
    )
    output = tmp_path / "fx.csv"
    assert fx_cli.main(
        ["EURUSD", "--start", start.isoformat(), "--end", end.isoformat(), "--output", str(output)]
    ) == 0
    assert output.exists()
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["source"] == "dukascopy"
    assert metadata["payout_history_available"] is False
    saved = pd.read_csv(output)
    assert (saved["source"] == "dukascopy").all()


def test_pocket_capture_does_not_backfill_current_payout(monkeypatch, tmp_path):
    class FakeAdapter:
        def __init__(self, ssid, demo=True):
            assert ssid == "secret-session"
            self.demo = demo

        async def get_candles(self, asset, *, period_seconds, duration_seconds):
            frame = _candles()
            frame["asset"] = asset
            frame["market_type"] = "otc"
            frame["period_seconds"] = period_seconds
            frame["payout"] = None
            return frame

        async def get_payout(self, asset):
            return 0.92

        async def close(self):
            return None

    monkeypatch.setenv("POCKET_SSID", "secret-session")
    monkeypatch.setattr(pocket_capture_cli, "PocketResearchAdapter", FakeAdapter)
    output = tmp_path / "pocket.csv"
    payout_log = tmp_path / "payouts.jsonl"
    args = argparse.Namespace(
        asset="EURUSD_otc",
        period_seconds=60,
        duration_seconds=3600,
        output=str(output),
        payout_log=str(payout_log),
        live_account=False,
    )
    result = asyncio.run(pocket_capture_cli._capture(args))
    saved = pd.read_csv(output)
    assert saved["payout"].isna().all()
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["historical_payout_backfill"] is False
    assert metadata["credential_persisted"] is False
    observation = json.loads(payout_log.read_text().strip())
    assert observation["payout"] == pytest.approx(0.92)
    assert "secret-session" not in output.with_suffix(".meta.json").read_text()
    assert result["current_payout"] == pytest.approx(0.92)


def test_pocket_capture_requires_environment_credential(monkeypatch):
    monkeypatch.delenv("POCKET_SSID", raising=False)
    args = argparse.Namespace(
        asset="EURUSD_otc",
        period_seconds=60,
        duration_seconds=3600,
        output=None,
        payout_log="unused.jsonl",
        live_account=False,
    )
    with pytest.raises(SystemExit, match="POCKET_SSID"):
        asyncio.run(pocket_capture_cli._capture(args))
