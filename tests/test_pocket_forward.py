from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

import confluence_lab.pocket_forward as pocket_forward


class _FixedProbabilityModel:
    def __init__(self, probability_up: float):
        self.probability_up = probability_up

    def predict_proba(self, features):
        return [[1.0 - self.probability_up, self.probability_up] for _ in range(len(features))]


def _fit(probability_up: float = 0.70):
    return SimpleNamespace(model=_FixedProbabilityModel(probability_up))


def _candles():
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-09-14T08:00:00Z",
                    "2026-09-14T08:01:00Z",
                ],
                utc=True,
            ),
            "open": [1.1000, 9.0],
            "high": [1.1005, 10.0],
            "low": [1.0995, 8.0],
            "close": [1.1002, 9.5],
            "asset": ["EURUSD_otc", "EURUSD_otc"],
            "market_type": ["otc", "otc"],
            "period_seconds": [60, 60],
        }
    )


def _payouts(observed_at="2026-09-14T08:01:04Z", payout=0.82):
    return pd.DataFrame(
        {
            "asset": ["EURUSD_otc"],
            "observed_at": pd.to_datetime([observed_at], utc=True),
            "payout": [payout],
            "account_mode": ["demo"],
        }
    )


def _simple_features(frame):
    # The scorer is responsible for truncating the supplied candle frame before
    # feature construction. The fake model ignores feature names/values.
    return pd.DataFrame({"feature": [1.0] * len(frame)})


def test_open_timestamp_semantics_never_uses_forming_future_candle(monkeypatch):
    seen_lengths = []

    def features(frame):
        seen_lengths.append(len(frame))
        return _simple_features(frame)

    monkeypatch.setattr(pocket_forward, "build_ml_features", features)
    result = pocket_forward.score_latest_completed_pocket_bar(
        _fit(0.70),
        _candles(),
        _payouts(),
        asset="EURUSD_otc",
        period_seconds=60,
        timestamp_semantics="open",
        as_of="2026-09-14T08:01:05Z",
        max_decision_delay_seconds=10,
    )

    # 08:01 candle is still forming until 08:02 under open-time semantics, so
    # only the 08:00 candle may enter feature generation.
    assert seen_lengths == [1]
    assert result.direction == "call"
    assert result.source_candle_timestamp == pd.Timestamp("2026-09-14T08:00:00Z")
    assert result.source_candle_completed_at == pd.Timestamp("2026-09-14T08:01:00Z")
    assert result.decision_delay_seconds == 5.0
    assert result.payout == 0.82
    assert result.payout_observed_at == pd.Timestamp("2026-09-14T08:01:04Z")
    assert result.payout_age_seconds == 1.0
    assert result.probability_above_payout_break_even is True


def test_stale_completed_candle_is_no_trade_before_model_scoring(monkeypatch):
    def forbidden(_):
        raise AssertionError("stale decision must not reach model features")

    monkeypatch.setattr(pocket_forward, "build_ml_features", forbidden)
    result = pocket_forward.score_latest_completed_pocket_bar(
        _fit(),
        _candles().iloc[[0]],
        _payouts(),
        asset="EURUSD_otc",
        period_seconds=60,
        timestamp_semantics="open",
        as_of="2026-09-14T08:02:00Z",
        max_decision_delay_seconds=15,
    )
    assert result.direction == "no_trade"
    assert result.reason == "completed_candle_is_stale"
    assert result.decision_delay_seconds == 60.0


def test_future_or_stale_payout_is_never_attached(monkeypatch):
    monkeypatch.setattr(pocket_forward, "build_ml_features", _simple_features)
    future = _payouts(observed_at="2026-09-14T08:01:06Z")
    result = pocket_forward.score_latest_completed_pocket_bar(
        _fit(0.70),
        _candles(),
        future,
        asset="EURUSD_otc",
        period_seconds=60,
        timestamp_semantics="open",
        as_of="2026-09-14T08:01:05Z",
        max_decision_delay_seconds=10,
        max_payout_age_seconds=120,
    )
    assert result.direction == "call"
    assert result.reason == "frozen_signal_without_fresh_payout"
    assert result.payout is None
    assert result.payout_observed_at is None

    stale = _payouts(observed_at="2026-09-14T07:58:00Z")
    result = pocket_forward.score_latest_completed_pocket_bar(
        _fit(0.70),
        _candles(),
        stale,
        asset="EURUSD_otc",
        period_seconds=60,
        timestamp_semantics="open",
        as_of="2026-09-14T08:01:05Z",
        max_decision_delay_seconds=10,
        max_payout_age_seconds=120,
    )
    assert result.payout is None
    assert result.reason == "frozen_signal_without_fresh_payout"


def test_probability_threshold_produces_explicit_no_trade(monkeypatch):
    monkeypatch.setattr(pocket_forward, "build_ml_features", _simple_features)
    result = pocket_forward.score_latest_completed_pocket_bar(
        _fit(0.55),
        _candles(),
        _payouts(),
        asset="EURUSD_otc",
        period_seconds=60,
        timestamp_semantics="open",
        as_of="2026-09-14T08:01:05Z",
        max_decision_delay_seconds=10,
    )
    assert result.direction == "no_trade"
    assert result.reason == "frozen_probability_threshold_not_cleared"
    assert result.probability_up == 0.55


def test_pocket_forward_requires_v5_timeframe_and_explicit_timestamp_semantics():
    with pytest.raises(ValueError, match="requires 60-second"):
        pocket_forward.score_latest_completed_pocket_bar(
            _fit(),
            _candles(),
            _payouts(),
            asset="EURUSD_otc",
            period_seconds=30,
            timestamp_semantics="open",
            as_of="2026-09-14T08:01:05Z",
        )
    with pytest.raises(ValueError, match="timestamp_semantics"):
        pocket_forward.score_latest_completed_pocket_bar(
            _fit(),
            _candles(),
            _payouts(),
            asset="EURUSD_otc",
            period_seconds=60,
            timestamp_semantics="unknown",  # type: ignore[arg-type]
            as_of="2026-09-14T08:01:05Z",
        )
