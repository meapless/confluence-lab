import pandas as pd

from confluence_lab.stress import performance_by_period


def test_monthly_period_breakdown_works_with_timezone_aware_trades():
    trades = pd.DataFrame(
        {
            "entry_timestamp": pd.to_datetime(
                ["2026-01-31T23:59:00Z", "2026-02-01T00:01:00Z", "2026-02-02T00:01:00Z"],
                utc=True,
            ),
            "result": ["win", "loss", "win"],
            "pnl": [0.82, -1.0, 0.82],
        }
    )
    report = performance_by_period(trades)
    assert list(report["period"]) == ["2026-01", "2026-02"]
    assert list(report["trades"]) == [1, 2]
