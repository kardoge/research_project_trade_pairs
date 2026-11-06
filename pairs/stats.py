"""Statistical tests and measures for a single pair.

Everything works on log prices: a spread of log prices is a portfolio whose
weights are stable as prices move, and hedge ratios become elasticities.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen


def hedge_ratio(y: pd.Series, x: pd.Series) -> tuple[float, float]:
    """OLS of y on x with intercept. Returns (alpha, beta)."""
    res = sm.OLS(y.values, sm.add_constant(x.values)).fit()
    return float(res.params[0]), float(res.params[1])


def spread(y: pd.Series, x: pd.Series, alpha: float, beta: float) -> pd.Series:
    return y - beta * x - alpha


def engle_granger(y: pd.Series, x: pd.Series) -> float:
    """Engle-Granger two-step cointegration test p-value (y on x)."""
    return float(coint(y.values, x.values, trend="c")[1])


def johansen_trace_ratio(y: pd.Series, x: pd.Series) -> float:
    """Johansen trace statistic for r=0 divided by its 95% critical value.

    A ratio > 1 rejects "no cointegration" at the 5% level. Unlike
    Engle-Granger it is symmetric in y and x.
    """
    with warnings.catch_warnings():
        # statsmodels emits spurious ComplexWarnings from the eigen-solver
        warnings.simplefilter("ignore", np.exceptions.ComplexWarning)
        res = coint_johansen(np.column_stack([y.values, x.values]), det_order=0, k_ar_diff=1)
    return float(res.lr1[0] / res.cvt[0, 1])


def adf_pvalue(s: pd.Series) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return float(adfuller(s.values, autolag="AIC")[1])


def half_life(s: pd.Series) -> float:
    """Mean-reversion half-life in bars, from an AR(1)/OU fit: ds = k*s_{t-1}."""
    lag = s.shift(1).iloc[1:]
    delta = s.diff().iloc[1:]
    k = sm.OLS(delta.values, sm.add_constant(lag.values)).fit().params[1]
    if k >= 0:
        return np.inf
    return float(-np.log(2) / np.log1p(k))


def hurst_exponent(s: pd.Series, max_lag: int = 20) -> float:
    """Hurst exponent via the scaling of lagged differences.

    H < 0.5 mean-reverting, H = 0.5 random walk, H > 0.5 trending. Short
    lags keep the estimate stable on a few years of daily data.
    """
    v = s.values
    lags = np.arange(2, min(max_lag, len(v) // 4))
    tau = np.array([np.std(v[lag:] - v[:-lag]) for lag in lags])
    ok = tau > 0
    return float(np.polyfit(np.log(lags[ok]), np.log(tau[ok]), 1)[0])


def zero_crossings_per_year(s: pd.Series, periods_per_year: int = 252) -> float:
    """How often the demeaned spread crosses zero — a proxy for trade count."""
    d = np.sign(s.values - s.values.mean())
    crossings = np.count_nonzero(d[1:] != d[:-1])
    return crossings * periods_per_year / len(s)


def return_correlation(y: pd.Series, x: pd.Series) -> float:
    return float(y.diff().corr(x.diff()))


def distance_ssd(y: pd.Series, x: pd.Series) -> float:
    """Gatev et al. (2006) distance: sum of squared differences of
    normalised price paths (each rebased to 1 at the start)."""
    ny = np.exp(y - y.iloc[0])
    nx = np.exp(x - x.iloc[0])
    return float(((ny - nx) ** 2).sum())
