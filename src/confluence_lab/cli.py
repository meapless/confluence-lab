from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .backtest import BacktestConfig, run_backtest
from .data import dataframe_fingerprint, load_dataset
from .experiments import ValidationGate, run_research_experiment
from .registry import append_experiment_record
from .robustness import monte_carlo_trades
from .splits import chronological_split
from .strategies import build_trend_pullback
from .walkforward import WalkForwardConfig, walk_forward

DEFAULT_GRID = {
    "adx_min": [15.0, 20.0, 25.0, 30.0],
    "atr_pct_min": [0.05, 0.15, 0.25],
    "atr_pct_max": [0.75, 0.90],
    "ema_distance_atr": [0.20, 0.35, 0.50, 0.75],
    "rsi_trigger": [50.0, 52.5, 55.0],
}


def _metric_dict(metrics):
    return asdict(metrics) if metrics is not None else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a reproducible Confluence Lab research experiment"
    )
    parser.add_argument("dataset", help="CSV or Parquet OHLC dataset")
    parser.add_argument("--expiry-bars", type=int, default=3)
    parser.add_argument("--fixed-payout", type=float, default=0.82)
    parser.add_argument("--payout-column", default=None)
    parser.add_argument("--min-search-trades", type=int, default=30)
    parser.add_argument("--min-validation-trades", type=int, default=30)
    parser.add_argument("--min-validation-expectancy", type=float, default=0.0)
    parser.add_argument("--walk-train-bars", type=int, default=10_000)
    parser.add_argument("--walk-test-bars", type=int, default=2_000)
    parser.add_argument("--mc-simulations", type=int, default=5_000)
    parser.add_argument("--output", default="experiments/latest.json")
    parser.add_argument("--registry", default="experiments/registry.jsonl")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    frame, diagnostics = load_dataset(args.dataset)
    config = BacktestConfig(
        expiry_bars=args.expiry_bars,
        fixed_payout=args.fixed_payout,
        payout_column=args.payout_column,
    )
    gate = ValidationGate(
        min_trades=args.min_validation_trades,
        min_expectancy=args.min_validation_expectancy,
    )

    experiment = run_research_experiment(
        frame,
        build_trend_pullback,
        DEFAULT_GRID,
        config=config,
        search_min_trades=args.min_search_trades,
        gate=gate,
    )

    report = {
        "dataset": {
            "path": str(Path(args.dataset)),
            "fingerprint": dataframe_fingerprint(frame),
            "diagnostics": asdict(diagnostics),
        },
        "strategy_family": "trend_pullback",
        "parameter_grid_size": 4 * 3 * 2 * 4 * 3,
        "backtest_config": asdict(config),
        "status": experiment.status,
        "best_development": None,
        "validation": _metric_dict(experiment.validation_metrics),
        "locked_test": _metric_dict(experiment.test_metrics),
        "walk_forward": None,
        "monte_carlo": None,
    }

    if experiment.best_development is not None:
        report["best_development"] = {
            "params": experiment.best_development.params,
            "score": experiment.best_development.score,
            "metrics": asdict(experiment.best_development.metrics),
        }

    if (
        experiment.best_development is not None
        and len(frame) >= args.walk_train_bars + args.walk_test_bars
    ):
        walk = walk_forward(
            frame,
            build_trend_pullback,
            DEFAULT_GRID,
            backtest_config=config,
            config=WalkForwardConfig(
                train_bars=args.walk_train_bars,
                test_bars=args.walk_test_bars,
                min_trades=args.min_search_trades,
            ),
        )
        report["walk_forward"] = walk.to_dict(orient="records")

    if experiment.status == "tested" and experiment.best_development is not None:
        split = chronological_split(frame)
        locked_result = run_backtest(
            split.test,
            build_trend_pullback(experiment.best_development.params),
            config,
        )
        if not locked_result.trades.empty:
            report["monte_carlo"] = asdict(
                monte_carlo_trades(
                    locked_result.trades,
                    simulations=args.mc_simulations,
                    seed=42,
                )
            )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    record = append_experiment_record(args.registry, report)

    print(
        json.dumps(
            {
                "status": experiment.status,
                "run_id": record["run_id"],
                "report": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
