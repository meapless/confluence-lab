from confluence_lab.experiments import ValidationGate, passes_validation_gate
from confluence_lab.metrics import PerformanceMetrics


def _metrics(*, trades=100, expectancy=0.05, wilson_low=0.60):
    return PerformanceMetrics(
        trades=trades,
        wins=60,
        losses=40,
        ties=0,
        win_rate=0.60,
        wilson_low=wilson_low,
        wilson_high=0.69,
        expectancy=expectancy,
        total_pnl=5.0,
        max_drawdown=3.0,
        max_losing_streak=4,
        max_winning_streak=5,
    )


def test_validation_gate_can_require_wilson_lower_bound():
    gate = ValidationGate(min_trades=30, min_expectancy=0.0, min_wilson_low=0.55)
    assert passes_validation_gate(_metrics(wilson_low=0.56), gate)
    assert not passes_validation_gate(_metrics(wilson_low=0.54), gate)


def test_validation_gate_still_requires_positive_expectancy():
    gate = ValidationGate(min_trades=30, min_expectancy=0.0, min_wilson_low=0.55)
    assert not passes_validation_gate(_metrics(expectancy=-0.01, wilson_low=0.60), gate)


def test_validation_gate_rejects_tiny_sample():
    gate = ValidationGate(min_trades=30)
    assert not passes_validation_gate(_metrics(trades=29), gate)
