from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .cli import DEFAULT_GRID
from .data import dataframe_fingerprint, load_dataset
from .experiments import ValidationGate
from .matrix import ExecutionVariant, run_matrix_experiment
from .registry import append_experiment_record
from .strategies import build_trend_pullback, prepare_trend_pullback

DEFAULT_EXPIRIES = (1, 2, 3, 5)
DEFAULT_PAYOUT_FLOORS = (None, 0.75, 0.80, 0.85, 0.90)


def _parse_ints(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values or any(item < 1 for item in values):
        raise argparse.ArgumentTypeError("expiry bars must be positive comma-separated integers")
    return values


def _parse_payouts(value: str) -> tuple[float | None, ...]:
    parsed: list[float | None] = []
    for item in value.split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item in {"none", "any"}:
            parsed.append(None)
            continue
        number = float(item)
        if not 0 <= number <= 1:
            raise argparse.ArgumentTypeError("payout floors must be decimals from 0 to 1")
        parsed.append(number)
    if not parsed:
        raise argparse.ArgumentTypeError("provide at least one payout floor")
    return tuple(parsed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search strategy, expiry and payout settings with a locked-test gate"
    )
    parser.add_argument("dataset", help="CSV or Parquet OHLC dataset")
    parser.add_argument("--expiry-bars", type=_parse_ints, default=DEFAULT_EXPIRIES)
    parser.add_argument("--payout-floors", type=_parse_payouts, default=DEFAULT_PAYOUT_FLOORS)
    parser.add_argument("--payout-column", default="payout")
    parser.add_argument("--fixed-payout", type=float, default=0.82)
    parser.add_argument("--min-search-trades", type=int, default=50)
    parser.add_argument("--min-validation-trades", type=int, default=30)
    parser.add_argument("--min-validation-expectancy", type=float, default=0.0)
    parser.add_argument("--min-locked-test-trades", type=int, default=30)
    parser.add_argument(
        "--objective",
        choices=["expectancy", "win_rate", "wilson_low"],
        default="expectancy",
    )
    parser.add_argument("--output", default="experiments/matrix-latest.json")
    parser.add_argument("--registry", default="experiments/registry.jsonl")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    frame, diagnostics = load_dataset(args.dataset)
    payout_column = (
        args.payout_column
        if args.payout_column.lower() not in {"none", "null"}
        else None
    )

    variants = [
        ExecutionVariant(
            expiry_bars=expiry,
            min_payout=floor,
            fixed_payout=args.fixed_payout,
            payout_column=payout_column,
        )
        for expiry in args.expiry_bars
        for floor in args.payout_floors
    ]

    strategy_grid_size = 1
    for values in DEFAULT_GRID.values():
        strategy_grid_size *= len(values)
    configuration_count = strategy_grid_size * len(variants)

    result = run_matrix_experiment(
        frame,
        build_trend_pullback,
        DEFAULT_GRID,
        variants,
        objective=args.objective,
        search_min_trades=args.min_search_trades,
        gate=ValidationGate(
            min_trades=args.min_validation_trades,
            min_expectancy=args.min_validation_expectancy,
            min_locked_test_trades=args.min_locked_test_trades,
        ),
        prepared_factory=prepare_trend_pullback,
    )

    report = {
        "dataset": {
            "path": str(Path(args.dataset)),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnostics),
        },
        "strategy_family": "trend_pullback",
        "strategy_grid_size": strategy_grid_size,
        "execution_variants": len(variants),
        "development_configurations_evaluated": configuration_count,
        "objective": args.objective,
        "status": result.status,
        "best_development": None,
        "validation": asdict(result.validation_metrics) if result.validation_metrics else None,
        "locked_test": asdict(result.test_metrics) if result.test_metrics else None,
    }

    if result.best_development is not None:
        report["best_development"] = {
            "params": result.best_development.params,
            "execution": asdict(result.best_development.execution),
            "score": result.best_development.score,
            "metrics": asdict(result.best_development.metrics),
        }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    record = append_experiment_record(args.registry, report)

    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": record["run_id"],
                "development_configurations_evaluated": configuration_count,
                "report": str(output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
