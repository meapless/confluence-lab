import pandas as pd
import pytest

from confluence_lab.pocket_store import (
    align_payouts_backward,
    consolidate_pocket_frames,
    make_snapshot_manifest_entry,
    normalize_payout_observations,
)


def _frame(start="2026-09-10T12:00:00Z"):
    ts = pd.date_range(start, periods=3, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [1.0, 1.1, 1.2],
            "high": [1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1],
            "close": [1.1, 1.2, 1.3],
        }
    )


def test_identical_overlapping_snapshots_are_deduplicated():
    first = _frame()
    second = first.iloc[1:].copy()
    merged = consolidate_pocket_frames([first, second])
    assert len(merged) == 3
    assert merged["timestamp"].is_unique


def test_conflicting_duplicate_candle_raises_by_default():
    first = _frame()
    second = first.iloc[1:].copy()
    second.loc[second.index[0], "close"] += 0.01
    second.loc[second.index[0], "high"] += 0.01
    with pytest.raises(ValueError, match="conflicting OHLC"):
        consolidate_pocket_frames([first, second])


def test_manifest_id_is_deterministic_for_same_snapshot():
    frame = _frame()
    kwargs = dict(
        asset="EURUSD_otc",
        period_seconds=60,
        observed_at="2026-09-10T12:03:00Z",
        account_mode="demo",
        relative_path="candles/part-1.parquet",
    )
    first = make_snapshot_manifest_entry(frame, **kwargs)
    second = make_snapshot_manifest_entry(frame, **kwargs)
    assert first == second
    assert len(first.snapshot_id) == 64


def test_payout_alignment_never_uses_future_observation():
    events = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-10T12:00:30Z", "2026-09-10T12:01:30Z"], utc=True
            )
        }
    )
    payouts = normalize_payout_observations(
        [
            {
                "asset": "EURUSD_otc",
                "observed_at": "2026-09-10T12:00:00Z",
                "payout": 0.82,
                "account_mode": "demo",
            },
            {
                "asset": "EURUSD_otc",
                "observed_at": "2026-09-10T12:02:00Z",
                "payout": 0.92,
                "account_mode": "demo",
            },
        ]
    )
    aligned = align_payouts_backward(
        events,
        payouts,
        asset="EURUSD_otc",
        max_age_seconds=120,
    )
    assert list(aligned["payout"]) == [0.82, 0.82]
    assert list(aligned["payout_age_seconds"]) == [30.0, 90.0]


def test_stale_payout_is_not_attached():
    events = pd.DataFrame(
        {"timestamp": pd.to_datetime(["2026-09-10T12:05:00Z"], utc=True)}
    )
    payouts = normalize_payout_observations(
        [
            {
                "asset": "EURUSD_otc",
                "observed_at": "2026-09-10T12:00:00Z",
                "payout": 0.82,
            }
        ]
    )
    aligned = align_payouts_backward(
        events,
        payouts,
        asset="EURUSD_otc",
        max_age_seconds=120,
    )
    assert pd.isna(aligned.loc[0, "payout"])
    assert pd.isna(aligned.loc[0, "payout_observed_at"])
