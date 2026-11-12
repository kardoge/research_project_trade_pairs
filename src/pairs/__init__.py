"""Pairs-trading analysis: find, compare and backtest stock pairs."""

from .data import load_csv, load_yfinance, synthetic_universe
from .selection import analyse_pairs, compare_methods, pick_best_pair
from .backtest import backtest_pair

__all__ = [
    "load_csv",
    "load_yfinance",
    "synthetic_universe",
    "analyse_pairs",
    "compare_methods",
    "pick_best_pair",
    "backtest_pair",
]
