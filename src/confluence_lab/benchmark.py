from __future__ import annotations

from dataclasses import asdict
import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .splits import chronological_split
from .strategies import STRATEGIES


def benchmark_strategies(frame: pd.DataFrame, *, expiry_bars: int = 3, payout_column: str | None = "payout") -> pd.DataFrame:
    split = chronological_split(frame)
    rows: list[dict[str, object]] = []
    for split_name, data in (("development", split.development), ("validation", split.validation), ("test", split.test)):
        for strategy_name, strategy in STRATEGIES.items():
            result = run_backtest(data, strategy, BacktestConfig(expiry_bars=expiry_bars, payout_column=payout_column, fixed_payout=0.82))
            rows.append({"split": split_name, "strategy": strategy_name, **asdict(result.metrics)})
    return pd.DataFrame(rows)
