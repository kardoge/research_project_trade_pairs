# trade_pairs

## Abstract


## Introduction

The concept of pairs trading, of which two related stocks are chosen based on appropriate modelling and forecasting of their time series data and an appropriate choice of distance measure to observe relative departures from their equilibrium, can create a relatively successful trading strategy through statistical arbitrage as a long/short dollar-neutral portfolio is chosen<sup>1</sup>. Huck and Afawubo (2015) evaluate whether cointegration selects better pairs than the common distance method, and report high, stable returns that are robust to transaction costs. The purpose of this project is to compare such methods performed on historical data and assess reproducibility across aggregated pricing data.

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

*Described for completeness; this method is not implemented in this project (see "How this project implements it" below).*

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


• The paper uses Johansen instead. It is a likelihood-ratio test in a VAR, with trace and maximum-eigenvalue statistics. It avoids Engle–Granger's asymmetry: the result does not depend on which stock is the dependent variable. Lag length (up to 10) is set by an LR test.
• The cointegrated pairs with the highest trace statistics (1% significance) are eligible.
• Trade when P1 − βP2 departs from its mean μ by more than k SDs.
• Cointegration vs correlation: Huck and Afawubo report that cointegration-selected pairs have lower return correlation (about 0.33, against about 0.55 for distance pairs) and higher spread volatility.

### How this project implements it

The methods above follow the literature. The code differs in several ways, so results here
are not a direct replication of Huck and Afawubo (2015):

| | Methods described above | This project (`pairs/`) |
|---|---|---|
| Selection methods | Distance, price-ratio ADF, cointegration | Distance, **correlation**, Engle–Granger, Johansen, and a **composite** rank. The price-ratio ADF method is not implemented |
| Prices | Normalised total-return prices | Log adjusted-close prices (Yahoo `auto_adjust=True`, so dividends are included) |
| Distance | SSD of normalised prices, traded 1:1 | SSD of prices rebased to 1 (`stats.distance_ssd`), used **only to rank pairs** |
| Correlation | Not described | Correlation of daily log returns over the formation window |
| Engle–Granger | OLS, then ADF on residuals | `statsmodels.coint` run in **both directions**; the lower p-value is kept, doubled, then Benjamini–Hochberg corrected across all pairs |
| Johansen | Lag length up to 10, chosen by LR test | **Fixed lag** (`k_ar_diff=1`), constant term; ranked by trace statistic ÷ its 95% critical value |
| Significance | 1% | **5%**, after the Benjamini–Hochberg correction |
| "Eligible" pair | Passes the cointegration test | Passes all four: BH-adjusted EG p < 0.05, Johansen ratio > 1, half-life of 1–60 days, Hurst < 0.5 |
| Trading rule | Each method trades its own spread (1:1 for distance, β for cointegration) | **Every method trades the same way**: OLS hedge ratio on log prices fitted in the formation window, then a z-score rule (enter ±2σ, exit ±0.5σ, stop ±4σ) |
| Costs | — | 5 bps per unit of gross exposure traded; positions closed at the end of each trading block |
| Pairs per method | Top 20 (Gatev et al.) | Top 3, equal-weighted |
| Re-selection | Monthly | Walk-forward: 504-day formation, 126-day trading block (25 windows); plus one 67/33 single split |

Because every method trades the same rule, differences in results come **only from which
pairs each method selects**.

Find, compare and backtest stock pairs for statistical-arbitrage pairs trading.
The tool tests every pair in a universe of stocks with several selection methods,
ranks them, and picks the best pair. Each method is then judged **out of sample**.

## Quick start

```bash
pip install -r requirements.txt

# Real data from Yahoo Finance (default universe: sector-matched US large caps)
python -m pairs --start 2012-01-01 --end xxxxx --walk-forward --out xxxx

# Your own tickers
python -m pairs --tickers KO PEP XOM CVX V MA --start 2012-01-01 --end xxxx

# Your own data: a wide CSV with a date column and one price column per ticker
python -m pairs --source csv --csv data/prices.csv

# Offline demo on a synthetic universe with known answers
python -m pairs --source synthetic

# Add a rolling walk-forward comparison of the methods
python -m pairs --start 2012-01-01 --end 2026-10-31 --walk-forward
python -m pairs --source synthetic --synthetic-days 2500 --walk-forward

# Only test pairs within the same sector (recommended)
python -m pairs --start 2012-01-01 --end 2026-10-31 --walk-forward --same-sector --out xxxx
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

### Reproduceable Results 

Ensure consistent end dates when performing any of the analysis such as walk_forward on same sector. The following modules and their versions were used during this analysis:

Python 3.13.5
matplotlib==3.10.0
yfinance==1.7.0

python -m pairs --start 2012-01-01 --end 2026-10-31 --walk-forward --same-sector --out results/sector_14
python -m pairs --start 2012-01-01 --end 2026-10-31 --walk-forward --out results/all_pairs_14

## Results

### Walk Forward (Main Result) (`walk_forward_summary.csv`):

| Method | Sharpe: sector (7) | Sharpe: all (91) | Return: sector | Return: all | Max DD: sector | Max DD: all | Trades: sector / all |
|---|---|---|---|---|---|---|---|
| distance | 0.45 | 0.45 | +16.1% | +23.3% | −6.2% | −8.8% | 71 / 84 |
| correlation | 0.43 | 0.55 | +14.7% | +18.4% | −5.1% | −5.1% | 71 / 72 |
| johansen | 0.33 | −0.12 | +13.6% | −11.4% | −7.5% | −19.5% | 71 / 81 |
| composite | 0.21 | 0.40 | +9.0% | +31.0% | −9.0% | −14.2% | 76 / 92 |
| engle_granger | 0.01 | −0.24 | −0.0% | −18.1% | −11.3% | −24.0% | 68 / 79 |
| eligible_only | −0.24 | −0.29 | −4.2% | −5.8% | −5.8% | −6.6% | 3 / 5 |

### Single Split (One Formation/Trading Split, Top 3 Pairs Each)

| Method | Picks: sector | Mean Sharpe: sector | Picks: all pairs | Mean Sharpe: all |
|---|---|---|---|---|
| engle_granger | BAC/JPM, KO/PEP, V/MA | −0.02 | BAC/JPM, KO/MSFT, KO/PEP | −0.21 |
| johansen | BAC/JPM, KO/PEP, V/MA | −0.02 | KO/V, KO/MA, KO/MSFT | −0.58 |
| composite | KO/PEP, V/MA, BAC/JPM | −0.02 | PEP/HD, KO/MSFT, KO/HD | −0.16 |
| correlation | BAC/JPM, V/MA, CVX/XOM | −0.40 | BAC/JPM, V/MA, CVX/XOM | −0.40 |
| distance | CVX/XOM, KO/PEP, V/MA | −0.42 | CVX/XOM, PEP/UPS, CVX/KO | −0.79 |

## Findings

Both experiments use the same 14 stocks, dates and strategy settings; they differ only in
whether candidate pairs are restricted to the same sector (7 pairs) or not (91 pairs).

1. **No selection method has a Sharpe ratio reliably above zero.** Walk-forward Sharpe ratios
   range from −0.29 to 0.55, and every 95% bootstrap confidence interval includes zero.
2. **Within the same-sector universe the methods cannot be told apart.** Distance (0.45) and
   correlation (0.43) have the highest Sharpe ratios, but their differences from the
   cointegration methods are well within the bootstrap uncertainty.
3. **Testing all pairs hurts the cointegration methods.** With 91 candidates, Engle–Granger and
   Johansen pick cross-sector pairs 85–87% of the time (e.g. KO/MSFT, PEP/HD), and their Sharpe
   ratios fall to −0.24 and −0.12. In the all-pairs run, distance outperforms Engle–Granger by
   0.69 Sharpe (95% CI 0.11 to 1.29).
4. **Multiple testing explains why.** 19 of 91 pairs pass Engle–Granger at p < 0.05, but none
   survive the Benjamini–Hochberg correction. Restricting to economically related pairs reduces
   false discoveries.
5. **Correlation is barely affected by the sector filter** because it picks same-sector pairs
   96% of the time on its own.
6. **Passing every statistical filter did not predict success.** Eligible pairs were rare
   (0–8% of picks) and still produced large losses, e.g. FDX/UPS in window 23 (−10.7%).

Limitations: 14 hand-picked large caps (survivorship and hindsight bias), 25 windows, a
single parameter setting, and a simplified cost model. See the roadmap for next steps.

## References

1. Huck N, Afawubo K. Pairs trading and selection methods: is cointegration superior? Appl Econ. 2015;47(6):599–613. doi:10.1080/00036846.2014.975417


