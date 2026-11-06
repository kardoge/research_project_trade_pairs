"""Score every pair in a universe and compare selection methods.

Workflow
--------
1. Split history into a formation window (selection + parameter fitting) and
   a trading window (out-of-sample evaluation).
2. ``analyse_pairs`` computes every statistic on the formation window only.
3. ``compare_methods`` lets each method pick its top-k pairs, then backtests
   them on the trading window, so methods are judged on data they never saw.
4. ``pick_best_pair`` returns the top pair by the composite score.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from . import stats
from .backtest import backtest_pair

# How each method ranks pairs: (column, ascending?) — first row = best.
METHODS: dict[str, tuple[str, bool]] = {
    "distance": ("ssd", True),
    "correlation": ("return_corr", False),
    "engle_granger": ("eg_pvalue", True),
    "johansen": ("johansen_ratio", False),
    "composite": ("score", False),
}


def same_sector_pairs(tickers, sectors: dict[str, str]) -> list[tuple[str, str]]:
    return [(a, b) for a, b in combinations(tickers, 2) if a in sectors and sectors.get(a) == sectors.get(b)]


def split_date(prices: pd.DataFrame, formation_frac: float) -> pd.Timestamp:
    return prices.index[int(len(prices) * formation_frac)]


def analyse_pairs(
    prices: pd.DataFrame,
    split: pd.Timestamp,
    max_half_life: float = 60.0,
    alpha_level: float = 0.05,
    sectors: dict[str, str] | None = None,
) -> pd.DataFrame:
    """One row per pair with formation-window statistics, best first.

    If ``sectors`` (ticker -> sector) is given, only pairs within the same
    sector are tested; tickers without a sector are left out. Testing fewer,
    economically related pairs means fewer chance fits and a milder
    multiple-testing correction.
    """
    logp = np.log(prices[prices.index < split])
    candidates = (
        list(combinations(logp.columns, 2)) if sectors is None
        else same_sector_pairs(logp.columns, sectors)
    )
    if not candidates:
        raise ValueError("No candidate pairs to test (check the sector mapping).")
    rows = []
    for a, b in candidates:
        # Engle-Granger depends on which leg is the dependent variable; test
        # both and keep the stronger direction (corrected for below via BH).
        p_ab = stats.engle_granger(logp[a], logp[b])
        p_ba = stats.engle_granger(logp[b], logp[a])
        y, x = (a, b) if p_ab <= p_ba else (b, a)
        alpha, beta = stats.hedge_ratio(logp[y], logp[x])
        s = stats.spread(logp[y], logp[x], alpha, beta)
        rows.append(
            {
                "pair": f"{y}/{x}",
                "y": y,
                "x": x,
                "beta": beta,
                "eg_pvalue": min(p_ab, p_ba),
                "johansen_ratio": stats.johansen_trace_ratio(logp[y], logp[x]),
                "spread_adf_p": stats.adf_pvalue(s),
                "half_life": stats.half_life(s),
                "hurst": stats.hurst_exponent(s),
                "crossings_per_yr": stats.zero_crossings_per_year(s),
                "return_corr": stats.return_correlation(logp[y], logp[x]),
                "ssd": stats.distance_ssd(logp[y], logp[x]),
            }
        )
    df = pd.DataFrame(rows)

    # Testing many pairs guarantees some false positives; control the
    # false discovery rate with Benjamini-Hochberg. The doubled p-value is a
    # Bonferroni-style penalty for having tried both EG directions.
    df["eg_pvalue_bh"] = multipletests(
        np.minimum(2 * df["eg_pvalue"], 1.0), method="fdr_bh"
    )[1]

    df["eligible"] = (
        (df["eg_pvalue_bh"] < alpha_level)
        & (df["johansen_ratio"] > 1.0)
        & df["half_life"].between(1.0, max_half_life)
        & (df["hurst"] < 0.5)
    )

    # Composite: average percentile rank across complementary criteria —
    # strength of cointegration (EG, Johansen), speed of reversion
    # (half-life, Hurst) and tradability (zero crossings).
    ranks = pd.concat(
        [
            df["eg_pvalue"].rank(pct=True, ascending=False),
            df["johansen_ratio"].rank(pct=True),
            df["half_life"].rank(pct=True, ascending=False),
            df["hurst"].rank(pct=True, ascending=False),
            df["crossings_per_yr"].rank(pct=True),
        ],
        axis=1,
    )
    df["score"] = ranks.mean(axis=1) + df["eligible"].astype(float)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def rank_by(table: pd.DataFrame, method: str) -> pd.DataFrame:
    col, asc = METHODS[method]
    return table.sort_values(col, ascending=asc).reset_index(drop=True)


def compare_methods(
    prices: pd.DataFrame,
    table: pd.DataFrame,
    split: pd.Timestamp,
    top_k: int = 3,
    **bt_kwargs,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backtest each method's top-k pairs out of sample.

    Returns (per_method_summary, per_pair_detail).
    """
    logp = np.log(prices)
    cache: dict[str, dict] = {}
    detail = []
    for method in METHODS:
        for rank, row in rank_by(table, method).head(top_k).iterrows():
            if row["pair"] not in cache:
                res = backtest_pair(logp[row["y"]], logp[row["x"]], split, **bt_kwargs)
                cache[row["pair"]] = res.summary()
            detail.append({"method": method, "rank": rank + 1, "pair": row["pair"], **cache[row["pair"]]})
    detail_df = pd.DataFrame(detail)
    summary = (
        detail_df.groupby("method", sort=False)
        .agg(
            pairs=("pair", ", ".join),
            mean_sharpe=("sharpe", "mean"),
            mean_return=("total_return", "mean"),
            worst_drawdown=("max_drawdown", "min"),
            trades=("n_trades", "sum"),
        )
        .sort_values("mean_sharpe", ascending=False)
    )
    return summary, detail_df


def pick_best_pair(table: pd.DataFrame) -> pd.Series:
    """Top pair by composite score (eligible pairs always outrank the rest)."""
    best = table.iloc[0]
    if not best["eligible"]:
        print("Warning: no pair passes all filters; best pair is the top-scoring ineligible one.")
    return best
