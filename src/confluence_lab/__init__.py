"""Confluence Lab quantitative research engine."""

from .backtest import BacktestConfig, BacktestResult, run_backtest
from .payouts import break_even_win_rate, settle_binary_trade
from .splits import chronological_split

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "break_even_win_rate",
    "chronological_split",
    "run_backtest",
    "settle_binary_trade",
]
