import pandas as pd

from confluence_lab.data import diagnose_dataset


def _frame(timestamps):
    n = len(timestamps)
    close = [1.10 + index * 0.0001 for index in range(n)]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps, utc=True),
            "open": close,
            "high": [value + 0.0001 for value in close],
            "low": [value - 0.0001 for value in close],
            "close": close,
        }
    )


def test_gap_diagnostics_separate_weekend_spanning_gap():
    diagnostics = diagnose_dataset(
        _frame(
            [
                "2026-09-04T20:58:00Z",  # Friday
                "2026-09-04T20:59:00Z",
                "2026-09-06T21:00:00Z",  # Sunday
                "2026-09-06T21:01:00Z",
            ]
        )
    )
    assert diagnostics.inferred_interval == pd.Timedelta(minutes=1)
    assert diagnostics.gap_events == 1
    assert diagnostics.weekend_spanning_gap_events == 1
    assert diagnostics.weekend_spanning_missing_intervals == diagnostics.missing_intervals
    assert diagnostics.non_weekend_missing_intervals == 0
    assert diagnostics.largest_gap == pd.Timedelta(days=2, minutes=1)


def test_gap_diagnostics_keep_intraday_holes_suspicious():
    diagnostics = diagnose_dataset(
        _frame(
            [
                "2026-09-07T10:00:00Z",
                "2026-09-07T10:01:00Z",
                "2026-09-07T10:03:00Z",
                "2026-09-07T10:04:00Z",
            ]
        )
    )
    assert diagnostics.missing_intervals == 1
    assert diagnostics.gap_events == 1
    assert diagnostics.weekend_spanning_gap_events == 0
    assert diagnostics.weekend_spanning_missing_intervals == 0
    assert diagnostics.non_weekend_missing_intervals == 1
