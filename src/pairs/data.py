"""Price data loaders.

All loaders return a DataFrame of adjusted close prices: a DatetimeIndex and
one column per ticker, with no missing values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _clean(prices: pd.DataFrame, min_coverage: float = 0.95) -> pd.DataFrame:
    """Drop tickers with poor coverage, then drop dates with any gap."""
    prices = prices.sort_index()
    coverage = prices.notna().mean()
    dropped = coverage[coverage < min_coverage].index.tolist()
    if dropped:
        print(f"Dropping tickers with <{min_coverage:.0%} data: {dropped}")
    prices = prices.drop(columns=dropped).dropna()
    prices = prices.loc[:, (prices > 0).all()]
    return prices


def load_yfinance(tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
    """Download daily adjusted closes from Yahoo Finance."""
    import yfinance as yf

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError("yfinance returned no data (network blocked or bad tickers?)")
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return _clean(close)


def load_csv(path: str) -> pd.DataFrame:
    """Load a wide CSV: first column is the date, remaining columns are tickers."""
    prices = pd.read_csv(path, index_col=0, parse_dates=True)
    return _clean(prices.apply(pd.to_numeric, errors="coerce"))


def synthetic_universe(n_days: int = 1000, seed: int = 7) -> pd.DataFrame:
    """Build a toy universe with known structure, for demos and tests.

    - ``A1``/``A2`` and ``B1``/``B2`` are truly cointegrated (shared random
      walk plus a mean-reverting OU spread).
    - ``C1``/``C2`` are highly correlated in returns but NOT cointegrated
      (separate random walks driven by a common factor) — the classic trap
      for correlation-based selection.
    - ``D1``..``D3`` are independent random walks.
    """
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n_days)

    def walk(vol=0.012, drift=0.0002):
        return np.cumsum(rng.normal(drift, vol, n_days))

    def ou(theta, vol):
        s = np.zeros(n_days)
        for t in range(1, n_days):
            s[t] = s[t - 1] - theta * s[t - 1] + rng.normal(0, vol)
        return s

    logp = {}
    base_a = walk()
    logp["A1"] = 4.0 + base_a
    logp["A2"] = 3.0 + 1.2 * base_a + ou(0.08, 0.010)

    base_b = walk(vol=0.015)
    logp["B1"] = 3.5 + base_b
    logp["B2"] = 3.8 + 0.8 * base_b + ou(0.04, 0.008)

    factor = rng.normal(0.0002, 0.012, n_days)
    logp["C1"] = 4.2 + np.cumsum(factor + rng.normal(0, 0.006, n_days))
    logp["C2"] = 4.0 + np.cumsum(factor + rng.normal(0, 0.006, n_days))

    for name in ("D1", "D2", "D3"):
        logp[name] = 3.0 + rng.uniform(0, 1) + walk()

    return np.exp(pd.DataFrame(logp, index=idx))
