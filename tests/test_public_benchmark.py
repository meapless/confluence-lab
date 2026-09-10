import pandas as pd

from confluence_lab.public_benchmark import (
    PublicBenchmarkPolicy,
    PublicBenchmarkSource,
    normalize_csv_source,
    run_public_benchmark,
)


def _source():
    return PublicBenchmarkSource(
        name="fixture",
        repository="example/repo",
        commit="a" * 40,
        blob_sha="b" * 40,
        path="fixture.csv",
        timestamp_column="datetime",
        symbol="EURUSD",
        timeframe="1 minute",
        rename_columns={"tick_volume": "volume"},
        license="MIT",
    )


def test_public_source_normalizer_handles_iso_utc_csv():
    payload = (
        b"datetime,open,high,low,close,tick_volume\n"
        b"2026-09-01T10:00:00+00:00,1.10,1.11,1.09,1.105,10\n"
        b"2026-09-01T10:01:00+00:00,1.105,1.12,1.10,1.11,12\n"
    )
    frame = normalize_csv_source(payload, _source())
    assert list(frame.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert str(frame.iloc[0]["timestamp"].tz) == "UTC"


def test_public_benchmark_uses_strict_fixed_payout_validation_gate():
    # A deterministic rising/falling waveform gives the engine real OHLC input
    # while keeping this test about report policy, not strategy performance.
    rows = 600
    timestamp = pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC")
    base = pd.Series([1.10 + ((i % 40) - 20) * 0.0001 for i in range(rows)])
    frame = pd.DataFrame(
        {
            "datetime": timestamp.astype(str),
            "open": base,
            "high": base + 0.0002,
            "low": base - 0.0002,
            "close": base + 0.00005,
            "tick_volume": 1,
        }
    )
    payload = frame.to_csv(index=False).encode()
    report = run_public_benchmark(
        payload,
        _source(),
        policy=PublicBenchmarkPolicy(
            fixed_payout=0.82,
            expiries=(1,),
            min_development_trades=5,
            min_validation_trades=5,
            min_locked_test_trades=5,
        ),
        family_names=("breakout",),
    )
    policy = report["research_policy"]
    assert policy["validation_min_wilson_low"] == report["economics"]["break_even_win_rate"]
    assert report["development_configurations_evaluated"] == 192
