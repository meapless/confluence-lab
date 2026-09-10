import numpy as np

from confluence_lab.ml_v5 import (
    development_oof_probabilities_histgb,
    fit_histgb_research_baseline,
    make_histgb_classifier,
)
from confluence_lab.ml_v5_experiment import run_histgb_experiment
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_v5_histgb_parameters_match_preregistration():
    model = make_histgb_classifier()
    params = model.get_params()
    assert params["learning_rate"] == 0.05
    assert params["max_iter"] == 200
    assert params["max_leaf_nodes"] == 15
    assert params["max_depth"] is None
    assert params["min_samples_leaf"] == 100
    assert params["l2_regularization"] == 1.0
    assert params["early_stopping"] is False
    assert params["random_state"] == 42


def test_v5_oof_predictions_leave_training_prefix_unpredicted():
    frame = generate_synthetic_ohlc(rows=3_000, seed=501)
    probabilities, prepared = development_oof_probabilities_histgb(
        frame,
        expiry_bars=2,
        n_splits=3,
    )
    assert len(probabilities) == len(frame)
    assert prepared.label_horizon_bars == 2
    assert probabilities.notna().sum() > 0
    first_prediction = int(np.flatnonzero(probabilities.notna().to_numpy())[0])
    assert first_prediction > 0
    assert probabilities.dropna().between(0.0, 1.0).all()


def test_v5_baseline_retains_every_requested_threshold_result():
    frame = generate_synthetic_ohlc(rows=3_500, seed=502)
    thresholds = (0.55, 0.60, 0.65)
    result = fit_histgb_research_baseline(
        frame,
        expiry_bars=1,
        fixed_payout=0.82,
        thresholds=thresholds,
        n_splits=3,
        min_oof_trades=10,
    )
    assert [item.threshold for item in result.development_threshold_results] == list(thresholds)
    assert result.model.get_params()["max_leaf_nodes"] == 15


def test_v5_validation_failure_keeps_locked_slice_unopened():
    frame = generate_synthetic_ohlc(rows=4_000, seed=503)
    result = run_histgb_experiment(
        frame,
        expiries=(1,),
        thresholds=(0.51,),
        fixed_payout=10.0,
        development_oof_splits=3,
        minimum_development_trades=10,
        minimum_validation_resolved_trades=1_000_000,
        minimum_locked_resolved_trades=1,
    )
    assert len(result.development_searches) == 1
    assert len(result.development_searches[0].research.development_threshold_results) == 1
    assert result.candidate is not None
    assert result.status == "rejected_validation"
    assert result.validation is not None
    assert result.locked_test is None
