"""Walk-forward (rolling) evaluation of pair-selection methods.

A single formation/trading split gives each method only a handful of trades.
Walk-forward repeats the whole process on a rolling window:

    |---- formation ----|-- trade --|
              |---- formation ----|-- trade --|
                        |---- formation ----|-- trade --|

In each window, every method re-selects its pairs and re-fits hedge ratios
using only that window's formation data, then trades the next block. The
trading blocks don't overlap, so they join into one continuous out-of-sample
return series per method.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import backtest_pair
from .selection import METHODS, analyse_pairs, rank_by

# Extra walk-forward-only method: the composite ranking, but only pairs that
# pass every filter are traded. If none qualify, the method stays in cash.
ELIGIBLE_ONLY = "eligible_only"


@dataclass
class WalkForwardResult:
    summary: pd.DataFrame  # one row per method, over the joined trading blocks
    windows: pd.DataFrame  # one row per (window, method)
    picks: pd.DataFrame  # one row per (window, method, pair)
    returns: pd.DataFrame  # daily out-of-sample returns, one column per method


def _select(table: pd.DataFrame, method: str, top_k: int) -> pd.DataFrame:
    if method == ELIGIBLE_ONLY:
        return rank_by(table, "composite").query("eligible").head(top_k)
    return rank_by(table, method).head(top_k)


def _perf(rets: pd.Series, periods_per_year: int = 252) -> dict:
    equity = (1 + rets).cumprod()
    sd = rets.std()
    return {
        "sharpe": float(np.sqrt(periods_per_year) * rets.mean() / sd) if sd > 0 else 0.0,
        "total_return": float(equity.iloc[-1] - 1),
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
    }


def walk_forward(
    prices: pd.DataFrame,
    formation_days: int = 504,
    trading_days: int = 126,
    top_k: int = 3,
    verbose: bool = True,
    sectors: dict[str, str] | None = None,
    **bt_kwargs,
) -> WalkForwardResult:
    """Roll forward ``trading_days`` at a time, re-selecting pairs each window.

    Each method holds an equal-weight portfolio of its ``top_k`` pairs (gross
    exposure 1 in total) during each trading block. ``sectors`` restricts
    candidates to same-sector pairs (see ``analyse_pairs``).
    """
    n = len(prices)
    if formation_days + trading_days > n:
        raise ValueError(f"Need at least {formation_days + trading_days} days for one window, have {n}.")
    logp = prices.apply(np.log)
    methods = [*METHODS, ELIGIBLE_ONLY]
    daily: dict[str, list[pd.Series]] = {m: [] for m in methods}
    window_rows, pick_rows = [], []

    starts = range(0, n - formation_days - trading_days + 1, trading_days)
    for w, start in enumerate(starts, 1):
        idx = prices.index[start : start + formation_days + trading_days]
        split = idx[formation_days]
        trade_idx = idx[formation_days:]
        if verbose:
            print(f"  window {w}/{len(starts)}: trade {trade_idx[0].date()} → {trade_idx[-1].date()}")

        table = analyse_pairs(prices.loc[idx], split, sectors=sectors)
        cache = {}
        for method in methods:
            chosen = _select(table, method, top_k)
            pair_rets = []
            for _, row in chosen.iterrows():
                if row["pair"] not in cache:
                    cache[row["pair"]] = backtest_pair(
                        logp.loc[idx, row["y"]], logp.loc[idx, row["x"]], split, **bt_kwargs
                    )
                res = cache[row["pair"]]
                pair_rets.append(res.returns)
                pick_rows.append(
                    {
                        "window": w,
                        "method": method,
                        "pair": row["pair"],
                        "eligible": bool(row["eligible"]),
                        **res.summary(),
                    }
                )
            # Unused slots sit in cash, so fewer picks means less exposure.
            if pair_rets:
                block = pd.concat(pair_rets, axis=1).sum(axis=1) / top_k
            else:
                block = pd.Series(0.0, index=trade_idx)
            daily[method].append(block)
            window_rows.append(
                {
                    "window": w,
                    "trade_start": trade_idx[0].date(),
                    "trade_end": trade_idx[-1].date(),
                    "method": method,
                    "n_pairs": len(pair_rets),
                    "pairs": ", ".join(chosen["pair"]),
                    **_perf(block),
                }
            )

    returns = pd.DataFrame({m: pd.concat(daily[m]) for m in methods})
    windows = pd.DataFrame(window_rows)
    picks = pd.DataFrame(pick_rows)

    rows = []
    for m in methods:
        wm = windows[windows["method"] == m]
        pm = picks[picks["method"] == m]
        rows.append(
            {
                "method": m,
                **_perf(returns[m]),
                "pct_windows_positive": float((wm["total_return"] > 0).mean()),
                "mean_window_sharpe": float(wm["sharpe"].mean()),
                "trades": int(pm["n_trades"].sum()) if len(pm) else 0,
                "pct_picks_eligible": float(pm["eligible"].mean()) if len(pm) else np.nan,
            }
        )
    summary = pd.DataFrame(rows).set_index("method").sort_values("sharpe", ascending=False)
    return WalkForwardResult(summary=summary, windows=windows, picks=picks, returns=returns)


def best_pair_history(result: WalkForwardResult) -> pd.DataFrame:
    """The composite method's top pick in each window: shows whether the
    'best pair' is stable or changes from one window to the next."""
    first = result.picks[result.picks["method"] == "composite"].groupby("window").head(1)
    return first[["window", "pair", "eligible", "sharpe", "total_return", "n_trades"]].reset_index(drop=True)
