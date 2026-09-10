from types import SimpleNamespace

import pandas as pd

from confluence_lab.backtest import BacktestConfig, BacktestResult
from confluence_lab.metrics import calculate_metrics
from confluence_lab.ml_experiment import evidence_gate, run_logistic_experiment
from confluence_lab.synthetic import generate_synthetic_ohlc


def _result(*, wins: int, losses: int, payout: float = 0.82) -> BacktestResult:
    rows = []
    for _ in range(wins):
        rows.append({"result": "win", "pnl": payout})
    for _ in range(losses):
        rows.append({"result": "loss", "pnl": -1.0})
    trades = pd.DataFrame(rows)
    return BacktestResult(
        trades=trades,
        metrics=calculate_metrics(trades),
        config=BacktestConfig(expiry_bars=1, fixed_payout=payout),
    )


def test_evidence_gate_requires_confidence_not_just_positive_point_estimate():
    # 56/44 is economically positive at 82%, but 100 observations are far too
    # weak for the Wilson lower bound to clear the ~54.95% break-even rate.
    result = _result(wins=56, losses=44)
    assert result.metrics.expectancy > 0
    assert not evidence_gate(result, minimum_resolved_trades=100, fixed_payout=0.82)


def test_failed_validation_never_opens_locked_test(monkeypatch):
    development_result = _result(wins=180, losses=120)
    failed_validation = _result(wins=80, losses=70)
    assert failed_validation.metrics.expectancy is not None

    fake_research = SimpleNamespace(
        selected_threshold=0.60,
        development_oof_result=development_result,
        model=object(),
    )
    monkeypatch.setattr(
        "confluence_lab.ml_experiment.fit_logistic_research_baseline",
        lambda *args, **kwargs: fake_research,
    )

    calls = []

    def fake_evaluate(*args, **kwargs):
        calls.append(kwargs)
        return failed_validation

    monkeypatch.setattr(
        "confluence_lab.ml_experiment.evaluate_model_slice",
        fake_evaluate,
    )

    frame = generate_synthetic_ohlc(rows=600, seed=301)
    result = run_logistic_experiment(
        frame,
        expiries=(1,),
        thresholds=(0.60,),
        minimum_development_trades=1,
        minimum_validation_resolved_trades=150,
        minimum_locked_resolved_trades=150,
    )
    assert result.status == "rejected_validation"
    assert result.locked_test is None
    assert len(calls) == 1


def test_no_development_candidate_keeps_both_future_slices_sealed(monkeypatch):
    fake_research = SimpleNamespace(
        selected_threshold=None,
        development_oof_result=None,
        model=object(),
    )
    monkeypatch.setattr(
        "confluence_lab.ml_experiment.fit_logistic_research_baseline",
        lambda *args, **kwargs: fake_research,
    )

    def should_not_evaluate(*args, **kwargs):
        raise AssertionError("validation/locked evaluation should not occur")

    monkeypatch.setattr(
        "confluence_lab.ml_experiment.evaluate_model_slice",
        should_not_evaluate,
    )
    frame = generate_synthetic_ohlc(rows=600, seed=302)
    result = run_logistic_experiment(
        frame,
        expiries=(1,),
        thresholds=(0.60,),
        minimum_development_trades=1,
    )
    assert result.status == "no_development_candidate"
    assert result.validation is None
    assert result.locked_test is None
