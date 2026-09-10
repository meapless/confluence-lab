from __future__ import annotations

import argparse
import json
from pathlib import Path

from confluence_lab.public_benchmark import (
    PublicBenchmarkPolicy,
    PublicBenchmarkSource,
    download_source,
    run_public_benchmark,
)

SOURCE = PublicBenchmarkSource(
    name="GetData EURUSD 1m evaluation sample 2026-07-14 to 2026-09-04",
    repository="getdata-finance/eurusd-1m-ohlcv-forex-historical-data",
    commit="c8526b6d1b7e629ff2fcf9eb585820c2e83ea4e1",
    blob_sha="7d56b0010bafb83e86cf3f27239337a723728187",
    path="EURUSD_1m.csv",
    timestamp_column="datetime",
    symbol="EURUSD",
    timeframe="1 minute",
    timestamp_interpretation="UTC (source CSV is ISO-8601 +00:00)",
    license="MIT",
)

POLICY = PublicBenchmarkPolicy(
    fixed_payout=0.82,
    expiries=(1, 2, 3, 5),
    search_objective="wilson_low",
    min_development_trades=30,
    min_validation_trades=30,
    min_locked_test_trades=30,
    require_validation_wilson_above_break_even=True,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the pinned GetData EUR/USD 1-minute public benchmark"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/getdata-eurusd-m1-2026-09.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = download_source(SOURCE)
    report = run_public_benchmark(payload, SOURCE, policy=POLICY)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": report["dataset"]["rows"],
                "development_configurations_evaluated": report[
                    "development_configurations_evaluated"
                ],
                "family_statuses": {
                    name: values["status"]
                    for name, values in report["strategy_families"].items()
                },
                "family_locked_evidence": {
                    name: values["locked_test_evidence_pass"]
                    for name, values in report["strategy_families"].items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
