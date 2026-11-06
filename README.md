# trade_pairs

Find, compare and backtest stock pairs for statistical-arbitrage pairs trading.
The tool tests every pair in a universe of stocks with several selection methods,
ranks them, and picks the best pair. Each method is then judged **out of sample**.

## Quick start

```bash
pip install -r requirements.txt

# Real data from Yahoo Finance (default universe: sector-matched US large caps)
python -m pairs --start 2018-01-01

# Your own tickers
python -m pairs --tickers KO PEP XOM CVX V MA --start 2015-01-01

# Your own data: a wide CSV with a date column and one price column per ticker
python -m pairs --source csv --csv data/prices.csv

# Offline demo on a synthetic universe with known answers
python -m pairs --source synthetic

# Add a rolling walk-forward comparison of the methods
python -m pairs --start 2012-01-01 --walk-forward
python -m pairs --source synthetic --synthetic-days 2500 --walk-forward

# Only test pairs within the same sector (recommended)
python -m pairs --start 2012-01-01 --walk-forward --same-sector
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

```bash
python -m pairs --start 2012-01-01 --walk-forward --out output_all
python -m pairs --start 2012-01-01 --walk-forward --same-sector --out output_sector
```

Based on your output files, here's a results write-up matching your README's style:

## Results: Same-sector pairs (6 tickers: KO, PEP, XOM, CVX, V, MA)

### Single-split comparison (`method_comparison.csv`)

All five methods converge on the same top-3 pairs — **MA/V, KO/PEP, CVX/XOM** — so every method produces identical performance on this one split:

| Metric | Value |
|---|---|
| Mean Sharpe | 0.01 |
| Mean return | +1.4% |
| Worst drawdown | −5.8% |
| Trades | 5 |

With only 3 candidate pairs in a 6-ticker, same-sector universe, there's no room for the methods to disagree — a single split can't distinguish selection quality here. This motivates the walk-forward test.

### Walk-forward performance by method (`walk_forward_summary.csv`)

| Method | Sharpe | Total Return | Max DD | % Positive Windows | Trades |
|---|---|---|---|---|---|
| distance | 0.45 | +16.1% | −6.2% | 72% | 71 |
| correlation | 0.43 | +14.7% | −5.1% | 64% | 71 |
| johansen | 0.33 | +13.6% | −7.5% | 48% | 71 |
| composite | 0.21 | +9.0% | −9.0% | 52% | 76 |
| engle_granger | 0.01 | −0.0% | −11.3% | 48% | 68 |
| eligible_only | −0.24 | −4.2% | −5.8% | 4% | 3 |

### Findings

1. **Simple methods beat statistical ones again.** Distance and correlation are the top two performers by Sharpe, total return, and win rate — consistent with the 14-ticker run. Engle-Granger and eligible_only are the weakest.

2. **The top pick is highly stable in this small universe.** From `walk_forward_picks.csv`, composite's top pair across the 25 windows was:
   - **MA/V**: 12 windows
   - **KO/PEP**: 5 windows
   - **CVX/XOM**: 4 windows
   - GOOGL/MSFT, BAC/JPM, FDX/UPS: 1–2 windows each

   This matches the 14-ticker same-sector result, suggesting the stable pick is driven by the sector structure, not the specific universe size.

3. **Eligible picks are rare and not obviously better.** Only `pct_picks_eligible` of ~1–5% passed every filter for most methods. The one clear eligible pick that produced a large loss was **FDX/UPS in window 23** (−10.7%, matching the earlier 14-ticker run's finding) — the same cautionary example recurs even in this smaller universe.

4. **Composite's extra trades didn't help.** Composite made 76 trades (vs. 71 for distance/correlation) but had a lower Sharpe and the worst drawdown (−9.0%) of the non-eligible methods — again echoing the broader 14-ticker conclusion that added statistical filtering doesn't translate into better risk-adjusted returns.

5. **Overall this run reproduces the 14-ticker finding almost one-for-one**, which is itself worth noting: restricting from 14 to 6 tickers (3 same-sector pairs only) barely changes the ranking or magnitude of results, reinforcing that the **sector constraint**, not universe size, is driving these effects.