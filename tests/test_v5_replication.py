import pandas as pd
import pytest

import confluence_lab.v5_replication as replication
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_v5_replication_constants_match_preregistration():
    assert replication.TRAIN_YEAR == 2014
    assert replication.REPLICATION_YEAR == 2015
    assert replication.SYMBOL == "EURUSD"
    assert replication.EXPIRY_BARS == 3
    assert replication.ENTRY_OFFSET_BARS == 1
    assert replication.PROBABILITY_THRESHOLD == 0.625
    assert replication.FIXED_PAYOUT == 0.82
    assert replication.MINIMUM_REPLICATION_RESOLVED_TRADES == 150
    assert replication.EXPECTED_TRAIN_FINGERPRINT == (
        "3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71"
    )


def test_fit_frozen_v5_refuses_training_history_revision(monkeypatch):
    frame = generate_synthetic_ohlc(rows=2_000, seed=501)
    monkeypatch.setattr(replication, "dataframe_fingerprint", lambda _: "changed-history")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        replication.fit_frozen_v5(frame)


def test_fit_frozen_v5_uses_exact_model_specification(monkeypatch):
    frame = generate_synthetic_ohlc(rows=3_000, seed=502)
    monkeypatch.setattr(
        replication,
        "dataframe_fingerprint",
        lambda _: replication.EXPECTED_TRAIN_FINGERPRINT,
    )
    fit = replication.fit_frozen_v5(frame)
    params = fit.model.get_params()
    assert fit.training_rows == len(frame)
    assert fit.labeled_training_rows > 200
    assert fit.class_zero_rows > 0
    assert fit.class_one_rows > 0
    assert params["learning_rate"] == 0.05
    assert params["max_iter"] == 200
    assert params["max_leaf_nodes"] == 15
    assert params["max_depth"] is None
    assert params["min_samples_leaf"] == 100
    assert params["l2_regularization"] == 1.0
    assert params["early_stopping"] is False
    assert params["random_state"] == 42


def test_evaluate_frozen_v5_cannot_change_expiry_or_threshold(monkeypatch):
    captured = {}

    def fake_evaluate(model, frame, **kwargs):
        captured.update(kwargs)
        return "result"

    monkeypatch.setattr(replication, "evaluate_model_slice", fake_evaluate)
    fit = replication.FrozenV5Fit(
        model=object(),
        training_rows=1,
        labeled_training_rows=1,
        class_zero_rows=1,
        class_one_rows=1,
        feature_columns=(),
        training_fingerprint=replication.EXPECTED_TRAIN_FINGERPRINT,
    )
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2015-01-01", periods=3, freq="min", tz="UTC"),
            "open": [1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
        }
    )
    assert replication.evaluate_frozen_v5(fit, frame) == "result"
    assert captured["threshold"] == 0.625
    assert captured["expiry_bars"] == 3
    assert captured["fixed_payout"] == 0.82
    assert captured["entry_offset_bars"] == 1
    assert captured["allow_overlapping_positions"] is True
    assert captured["cooldown_bars"] == 0
