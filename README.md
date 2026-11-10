# trade_pairs

## Abstract


## Introduction

The concept of pairs trading, of which two related stocks are chosen based on appropriate modelling and forecasting of their time series data and an appropriate choice of distance measure to observe relative departures from their equilibrium, can create a relatively successful trading strategy through statistical arbitrage as a long/short doller-neutral portfolio is chosen<sup>1</sup>. The research performed by Nicolas Husk and Komivi Afawubo, look to evaluate the effectiveness of cointigration over common distance methods in choosing such pairs. With mentions on generating high and stable returns robust to transaction costs. The purpose of this project is to compare such methods performed on historical data and assess reporducability across aggregated pricing data.

### Pairs Selection 

### 1. Minimum distance method: 

• Normalise each stock's total-return price to $1 at the start of the formation period.
• For every pair, compute the sum of squared differences (SSD) between the normalised prices:

**Normalised prices** (total return, scaled to \$1 at the start of the formation period):

$$
P_t^i = \prod_{s=1}^{t} \left(1 + r_s^i\right), \qquad P_0^i = 1
$$

**Selection statistic:** sum of squared differences (SSD); lower is better.

$$
SSD_{i,j} = \sum_{t=1}^{T} \left( P_t^i - P_t^j \right)^2
$$

**Spread:**

$$
S_t = P_t^i - P_t^j
$$

**Hedge ratio:** fixed at 1:1, i.e. \$1 long and \$1 short.

• The pairs with the lowest SSD (top 20 in Gatev et al.) become candidates.
• Open the trade when the normalised spread moves more than k historical SDs (usually 2). Close it on convergence or at the end of the trading period.

• Pros: model-free, so there is nothing to mis-specify or mis-estimate. It is also fast.
• Cons: no forecasting content. It simply assumes divergence will reverse. It also favours low-volatility pairs, whose spreads are too small to make much money.


### 2. Stationarity of the Price Ratio (ADF test)

• A tradable pair needs a price ratio y with constant mean and variance.
• Test with an Augmented Dickey–Fuller regression, no trend, with up to 10 lags chosen so the residuals are serially uncorrelated:

**Price ratio:**

$$
y_t = \frac{P_t^i}{P_t^j}
$$

**Augmented Dickey–Fuller regression** (no trend; $p \le 10$ lags chosen so that $\varepsilon_t$ is serially uncorrelated):

$$
y_t = c + \phi \, y_{t-1} + \sum_{k=1}^{p} \beta_k \, \Delta y_{t-k} + \varepsilon_t,
\qquad \Delta y_t = y_t - y_{t-1}
$$

**Hypotheses:**

$$
H_0: \phi = 1 \;\; \text{(unit root, not tradable)}
\qquad
H_1: \phi < 1 \;\; \text{(stationary, tradable)}
$$

**Selection statistic:** ADF $t$-statistic; most negative is best, significant at the 1% level.

**Spread:**

$$
S_t = y_t - \bar{y}
$$

• Each month the pairs with the lowest (most negative) ADF t-statistics are eligible, and must be significant at 1% or better.
• Open the trade when the ratio departs from its historical mean by more than k SDs of the error term.

### 3. Cointegration (Engle–Granger / Johansen)

• Two I(1) prices are cointegrated if some combination P1 − βP2 is stationary, meaning they share a long-run equilibrium.
• Engle–Granger (1987) is the familiar two-step version:

**Cointegrating regression** ($P^i$ and $P^j$ both $I(1)$):

$$
P_t^i - \beta \, P_t^j = \mu + \varepsilon_t
$$

The pair is cointegrated if $\varepsilon_t$ is stationary, i.e. $\varepsilon_t \sim I(0)$.

**Engle–Granger (two-step):** estimate $\beta$ by OLS, then ADF-test the residuals:

$$
\Delta \hat{\varepsilon}_t = \gamma \, \hat{\varepsilon}_{t-1} + \sum_{k=1}^{p} \delta_k \, \Delta \hat{\varepsilon}_{t-k} + u_t,
\qquad H_0: \gamma = 0
$$

**Johansen (used in Huck & Afawubo, 2015):** VECM representation of $\mathbf{P}_t = (P_t^i, P_t^j)'$:

$$
\Delta \mathbf{P}_t = \Pi \, \mathbf{P}_{t-1} + \sum_{k=1}^{p-1} \Gamma_k \, \Delta \mathbf{P}_{t-k} + \boldsymbol{\varepsilon}_t,
\qquad \Pi = \alpha \beta'
$$

**Trace statistic** (tests $H_0$: at most $r$ cointegrating vectors):

$$
\lambda_{\text{trace}}(r) = -T \sum_{k=r+1}^{n} \ln\left(1 - \hat{\lambda}_k\right)
$$

**Selection statistic:** trace statistic; highest is best, significant at the 1% level.

**Spread:**

$$
S_t = P_t^i - \hat{\beta} \, P_t^j - \hat{\mu}
$$

Regress one price on the other, then ADF-test the residuals.
• The paper uses Johansen instead. It is a likelihood-ratio test in a VAR, with trace and maximum-eigenvalue statistics. It avoids Engle–Granger's asymmetry: the result does not depend on which stock is the dependent variable. Lag length (up to 10) is set by an LR test.
• The cointegrated pairs with the highest trace statistics (1% significance) are eligible.
• Trade when P1 − βP2 departs from its mean μ by more than k SDs.
• Cointegration vs correlation: the selected pairs have lower return correlation (about 0.33, against about 0.55 for distance pairs) and higher spread volatility. Mean reversion, not co-movement, is what is being selected.

Find, compare and backtest stock pairs for statistical-arbitrage pairs trading.
The tool tests every pair in a universe of stocks with several selection methods,
ranks them, and picks the best pair. Each method is then judged **out of sample**.

## Quick start

```bash
pip install -r requirements.txt

# Real data from Yahoo Finance (default universe: sector-matched US large caps)
python -m pairs --start 2012-01-01 --end 2026-10-31

# Your own tickers
python -m pairs --tickers KO PEP XOM CVX V MA --start 2012-01-01 --end 2026-10-31

# Your own data: a wide CSV with a date column and one price column per ticker
python -m pairs --source csv --csv data/prices.csv

# Offline demo on a synthetic universe with known answers
python -m pairs --source synthetic

# Add a rolling walk-forward comparison of the methods
python -m pairs --start 2012-01-01 --end 2026-10-31 --walk-forward
python -m pairs --source synthetic --synthetic-days 2500 --walk-forward

# Only test pairs within the same sector (recommended)
python -m pairs --start 2012-01-01 --end 2026-10-31 --walk-forward --same-sector --out results/sector_14
python -m pairs --tickers ... --sector-file sectors.csv   # CSV columns: ticker,sector

pytest -q
```

Results go to `output/`:

| File | Contents |
|---|---|
| `pair_stats.csv` | every pair with all statistics, best first |
| `method_comparison.csv` | out-of-sample performance of each selection method |
| `method_detail.csv` | the pairs each method picked and how each one did |
| `best_pair.png` | prices, spread z-score with trades, and the equity curve for the best pair |
| `walk_forward_summary.csv` | with `--walk-forward`: each method's performance over all trading blocks joined |
| `walk_forward_windows.csv` | each method's picks and performance in every window |
| `walk_forward_picks.csv` | every pair picked in every window, with its result |
| `walk_forward_returns.csv` | daily out-of-sample returns, one column per method |
| `walk_forward.png` | out-of-sample equity curve for each method |


## Results: Same-sector pairs (14 tickers: KO, PEP, V, MA, BAC, JPM, HD, LOW, GOOGL, MSFT, CVX, XOM, FDX, UPS)

### Method Comparison - Top 3 Pairs Each, Out of Sample (`method_comparison.csv`):

| Method | Pairs | Mean Sharpe | Mean Return | Worst Drawdown | Trades |
|---|---|---|---|---|---|
| engle_granger | BAC/JPM, KO/PEP, V/MA | -0.022 | -0.005 | -0.076 | 4 |
| johansen | BAC/JPM, KO/PEP, V/MA | -0.022 | -0.005 | -0.076 | 4 |
| composite | KO/PEP, V/MA, BAC/JPM | -0.022 | -0.005 | -0.076 | 4 |
| correlation | BAC/JPM, V/MA, CVX/XOM | -0.400 | -0.069 | -0.212 | 3 |
| distance | CVX/XOM, KO/PEP, V/MA | -0.422 | -0.072 | -0.212 | 3 |

### Best Pair (Out-of-Sample) (`pairs_stats.csv`):

**KO/PEP** — long 1 KO / short 0.65 PEP

| Statistic | Value |
|---|---|
| Engle-Granger p-value | 0.0032 (BH-adjusted: 0.0224) |
| Johansen ratio | 1.21 |
| Half-life | 47.8 days |
| Hurst exponent | 0.46 |
| Sharpe (OOS) | -0.07 |
| Return (OOS) | -1.2% |
| Max Drawdown (OOS) | -7.6% |
| Trades | 2 |

### Walk-forward performance by method (`walk_forward_summary.csv`):

| Method | Sharpe | Total Return | Max Drawdown | % Windows Positive | Mean Window Sharpe | Trades | % Picks Eligible |
|---|---|---|---|---|---|---|---|
| distance | 0.454 | 0.161 | -0.062 | 0.720 | 0.682 | 71 | 0.000 |
| correlation | 0.433 | 0.147 | -0.051 | 0.640 | 0.575 | 71 | 0.013 |
| johansen | 0.332 | 0.136 | -0.075 | 0.480 | 0.378 | 71 | 0.053 |
| composite | 0.206 | 0.090 | -0.090 | 0.520 | 0.367 | 76 | 0.053 |
| engle_granger | 0.015 | -0.000 | -0.113 | 0.480 | 0.033 | 68 | 0.053 |
| eligible_only | -0.242 | -0.042 | -0.058 | 0.040 | -0.089 | 3 | 1.000 |

### Composite Top Pick in Each Window (`walk_forward_windows.csv`)

| Window | Pair | Eligible | Sharpe | Total Return | Trades |
|---|---|---|---|---|---|
| 1 | KO/PEP | False | 0.000 | 0.000 | 0 |
| 2 | KO/PEP | False | 2.597 | 0.091 | 2 |
| 3 | KO/PEP | False | 0.208 | 0.003 | 1 |
| 4 | MA/V | False | 0.000 | 0.000 | 0 |
| 5 | MA/V | True | -1.694 | -0.029 | 1 |
| 6 | PEP/KO | False | -2.066 | -0.028 | 1 |
| 7 | XOM/CVX | False | -0.102 | -0.004 | 1 |
| 8 | GOOGL/MSFT | True | 0.000 | 0.000 | 0 |
| 9 | GOOGL/MSFT | False | -0.278 | -0.008 | 2 |
| 10 | BAC/JPM | False | -1.377 | -0.027 | 1 |
| 11 | V/MA | False | 2.089 | 0.029 | 1 |
| 12 | V/MA | False | 0.000 | 0.000 | 0 |
| 13 | MA/V | False | 1.586 | 0.017 | 1 |
| 14 | V/MA | False | 1.345 | 0.029 | 2 |
| 15 | MA/V | False | 1.536 | 0.028 | 2 |
| 16 | CVX/XOM | True | 0.479 | 0.005 | 1 |
| 17 | CVX/XOM | False | -2.671 | -0.048 | 1 |
| 18 | MA/V | False | 0.000 | 0.000 | 0 |
| 19 | MA/V | False | 0.000 | 0.000 | 0 |
| 20 | MA/V | False | 2.621 | 0.025 | 1 |
| 21 | MA/V | False | 2.139 | 0.020 | 1 |
| 22 | MA/V | False | -1.055 | -0.018 | 1 |
| 23 | FDX/UPS | True | -1.000 | -0.107 | 1 |
| 24 | CVX/XOM | False | 0.000 | 0.000 | 0 |
| 25 | PEP/KO | False | 0.444 | 0.033 | 1 |

## Reproduceable Results 

Ensure consistent end dates when performing any of the analysis such as walk_forward on same sector. The following modules and their versions were used during this analysis:

numpy>=1.26
pandas>=2.1
scipy>=1.11
statsmodels>=0.14
matplotlib>=3.8
yfinance>=0.2.40
pytest>=8

2012-01-01 --end 2026-10-31

### Findings

1. **Simple methods beat statistical ones again.** Distance and correlation have the highest performance by Sharpe, total return, and win rate. Whether those differences are significant are discussed in **EVALUATION SECTION**  — Engle-Granger and eligible_only are the weakest.

2. **The top pick is highly stable in this small universe.** From `walk_forward_picks.csv`, composite's top pair across the 25 windows was:
   - **MA/V**: 12 windows
   - **KO/PEP**: 5 windows
   - **CVX/XOM**: 4 windows
   - **GOOGL/MSFT**, **BAC/JPM**, **FDX/UPS**: 1–2 windows each

   This matches the 14-ticker same-sector result, suggesting the stable pick is driven by the sector structure, not the specific universe size.

3. **Eligible picks are rare and not obviously better.** Only percentage of ~1–5% passed every filter for most methods. The one clear eligible pick that produced a large loss was **FDX/UPS in window 23** (−10.7%, matching the earlier 14-ticker run's finding) — the same cautionary example recurs even in this smaller universe.

4. **Composite's extra trades didn't help.** Composite made 76 trades (vs. 71 for distance/correlation) but had a lower Sharpe and the worst drawdown (−9.0%) of the non-eligible methods — again echoing the broader 14-ticker conclusion that added statistical filtering doesn't translate into better risk-adjusted returns.


## References

1. Huck N, Afawubo K. Pairs trading and selection methods: is cointegration superior? Appl Econ. 2015;47(6):599–613. doi:10.1080/00036846.2014.975417


