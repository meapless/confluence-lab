import pandas as pd
import pytest

from confluence_lab.forward import (
    append_forward_candidate,
    append_forward_outcome,
    candidate_id_for,
    forward_ledger_frame,
)
from confluence_lab.registry import verify_registry


def test_candidate_id_is_deterministic():
    kwargs = dict(
        model_version="v5-2014-frozen",
        asset="EURUSD_otc",
        market_type="otc",
        signal_timestamp="2026-09-11T08:00:00Z",
        direction="call",
        expiry_bars=3,
        entry_offset_bars=1,
        probability_threshold=0.625,
    )
    assert candidate_id_for(**kwargs) == candidate_id_for(**kwargs)


def test_forward_candidate_and_outcome_are_separate_append_only_events(tmp_path):
    path = tmp_path / "forward.jsonl"
    candidate = append_forward_candidate(
        path,
        model_version="v5-2014-frozen",
        asset="EURUSD_otc",
        market_type="otc",
        signal_timestamp="2026-09-11T08:00:00Z",
        direction="call",
        probability=0.71,
        probability_threshold=0.625,
        expiry_bars=3,
        payout=0.92,
        payout_observed_at="2026-09-11T07:59:50Z",
    )
    assert candidate["event_type"] == "candidate"
    assert candidate["outcome_known_at_append"] is False
    assert verify_registry(path)

    outcome = append_forward_outcome(
        path,
        candidate_id=candidate["candidate_id"],
        entry_timestamp="2026-09-11T08:01:00Z",
        expiry_timestamp="2026-09-11T08:03:00Z",
        entry_price=1.1000,
        exit_price=1.1010,
        result="win",
        pnl=0.92,
    )
    assert outcome["event_type"] == "outcome"
    assert verify_registry(path)

    frame = forward_ledger_frame(path)
    assert len(frame) == 1
    assert bool(frame.iloc[0]["settled"])
    assert frame.iloc[0]["outcome_result"] == "win"


def test_forward_ledger_refuses_duplicate_candidate_and_outcome(tmp_path):
    path = tmp_path / "forward.jsonl"
    kwargs = dict(
        model_version="v5",
        asset="EURUSD",
        market_type="regular",
        signal_timestamp="2026-09-11T08:00:00Z",
        direction="put",
        probability=0.20,
        probability_threshold=0.625,
        expiry_bars=3,
    )
    candidate = append_forward_candidate(path, **kwargs)
    with pytest.raises(ValueError, match="already exists"):
        append_forward_candidate(path, **kwargs)

    settlement = dict(
        candidate_id=candidate["candidate_id"],
        entry_timestamp="2026-09-11T08:01:00Z",
        expiry_timestamp="2026-09-11T08:03:00Z",
        entry_price=1.1,
        exit_price=1.2,
        result="loss",
        pnl=-1.0,
    )
    append_forward_outcome(path, **settlement)
    with pytest.raises(ValueError, match="already settled"):
        append_forward_outcome(path, **settlement)


def test_forward_candidate_rejects_future_payout_and_below_threshold_signal(tmp_path):
    path = tmp_path / "forward.jsonl"
    common = dict(
        model_version="v5",
        asset="EURUSD_otc",
        market_type="otc",
        signal_timestamp="2026-09-11T08:00:00Z",
        probability_threshold=0.625,
        expiry_bars=3,
    )
    with pytest.raises(ValueError, match="future payout"):
        append_forward_candidate(
            path,
            **common,
            direction="call",
            probability=0.7,
            payout=0.9,
            payout_observed_at="2026-09-11T08:00:01Z",
        )
    with pytest.raises(ValueError, match="does not clear"):
        append_forward_candidate(
            path,
            **common,
            direction="call",
            probability=0.60,
        )


def test_forward_outcome_requires_prior_candidate(tmp_path):
    path = tmp_path / "forward.jsonl"
    with pytest.raises(ValueError, match="exactly one prior candidate"):
        append_forward_outcome(
            path,
            candidate_id="missing",
            entry_timestamp=pd.Timestamp("2026-09-11T08:01:00Z"),
            expiry_timestamp=pd.Timestamp("2026-09-11T08:03:00Z"),
            entry_price=1.0,
            exit_price=1.1,
            result="win",
            pnl=0.9,
        )
