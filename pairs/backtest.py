"""Z-score mean-reversion backtest for one pair.

Parameters (hedge ratio, spread mean and std) are estimated on the formation
window only and then frozen for the trading window, so the out-of-sample
result has no look-ahead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .stats import hedge_ratio, spread


@dataclass
class BacktestResult:
    returns: pd.Series
    zscore: pd.Series
    position: pd.Series
    sharpe: float
    total_return: float
    max_drawdown: float
    n_trades: int

    def summary(self) -> dict:
        return {
            "sharpe": self.sharpe,
            "total_return": self.total_return,
            "max_drawdown": self.max_drawdown,
            "n_trades": self.n_trades,
        }


def _positions(z: np.ndarray, entry: float, exit: float, stop: float) -> np.ndarray:
    """State machine: +1 long spread, -1 short spread, 0 flat.

    After a stop-out, new entries are blocked until the spread comes back
    within ``exit`` of its mean. Otherwise a spread that breaks down and
    hovers just under ``stop`` keeps re-entering and getting stopped out.
    """
    pos = np.zeros(len(z))
    cur = 0.0
    blocked = False
    for t, zt in enumerate(z):
        if blocked and abs(zt) <= exit:
            blocked = False
        if cur == 0:
            if not blocked:
                if entry <= zt < stop:
                    cur = -1.0
                elif -stop < zt <= -entry:
                    cur = 1.0
        elif cur == 1:
            if zt <= -stop:
                cur, blocked = 0.0, True
            elif zt >= -exit:
                cur = 0.0
        elif cur == -1:
            if zt >= stop:
                cur, blocked = 0.0, True
            elif zt <= exit:
                cur = 0.0
        pos[t] = cur
    return pos


def backtest_pair(
    log_y: pd.Series,
    log_x: pd.Series,
    split: pd.Timestamp,
    entry: float = 2.0,
    exit: float = 0.5,
    stop: float = 4.0,
    cost_bps: float = 5.0,
    periods_per_year: int = 252,
    close_at_end: bool = True,
) -> BacktestResult:
    """Fit on dates < split, trade on dates >= split.

    Long the spread = long 1 unit of y, short ``beta`` units of x, with gross
    exposure normalised to 1. ``cost_bps`` is charged per unit of gross
    exposure traded. With ``close_at_end`` any open position is closed (and
    charged costs) on the last bar, so consecutive windows chain cleanly.
    """
    form_y, form_x = log_y[log_y.index < split], log_x[log_x.index < split]
    alpha, beta = hedge_ratio(form_y, form_x)
    form_s = spread(form_y, form_x, alpha, beta)
    mu, sd = form_s.mean(), form_s.std()

    y, x = log_y[log_y.index >= split], log_x[log_x.index >= split]
    z = (spread(y, x, alpha, beta) - mu) / sd

    pos = pd.Series(_positions(z.values, entry, exit, stop), index=z.index)
    if close_at_end:
        pos.iloc[-1] = 0.0
    held = pos.shift(1).fillna(0.0)  # trade at close, earn from next bar

    gross = 1.0 + abs(beta)
    spread_ret = (np.expm1(y.diff()) - beta * np.expm1(x.diff())).fillna(0.0) / gross
    turnover = pos.diff().abs().fillna(pos.abs())
    rets = held * spread_ret - turnover * cost_bps / 1e4

    equity = (1 + rets).cumprod()
    sd_r = rets.std()
    sharpe = float(np.sqrt(periods_per_year) * rets.mean() / sd_r) if sd_r > 0 else 0.0
    mdd = float((equity / equity.cummax() - 1).min())
    n_trades = int(((pos != 0) & (pos.shift(1).fillna(0) == 0)).sum())

    return BacktestResult(
        returns=rets,
        zscore=z,
        position=pos,
        sharpe=sharpe,
        total_return=float(equity.iloc[-1] - 1),
        max_drawdown=mdd,
        n_trades=n_trades,
    )
