"""Command-line entry point: ``python -m pairs --help``."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import backtest_pair
from .data import load_csv, load_yfinance, synthetic_universe
from .selection import analyse_pairs, compare_methods, pick_best_pair, same_sector_pairs, split_date
from .walkforward import best_pair_history, walk_forward

# Sector of each default ticker; used by --same-sector.
DEFAULT_SECTORS = {
    "KO": "beverages", "PEP": "beverages",
    "XOM": "oil", "CVX": "oil",
    "V": "payments", "MA": "payments",
    "HD": "home_improvement", "LOW": "home_improvement",
    "JPM": "banks", "BAC": "banks",
    "GOOGL": "tech", "MSFT": "tech",
    "UPS": "parcel", "FDX": "parcel",
}
DEFAULT_TICKERS = list(DEFAULT_SECTORS)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Find and compare stock pairs for pairs trading.")
    p.add_argument("--source", choices=["yfinance", "csv", "synthetic"], default="yfinance")
    p.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--csv", help="wide CSV of prices (date column + one column per ticker)")
    p.add_argument("--formation-frac", type=float, default=0.67,
                   help="share of history used for selection; the rest is out-of-sample")
    p.add_argument("--top-k", type=int, default=3, help="pairs each method selects")
    p.add_argument("--entry", type=float, default=2.0)
    p.add_argument("--exit", type=float, default=0.5)
    p.add_argument("--stop", type=float, default=4.0)
    p.add_argument("--cost-bps", type=float, default=5.0)
    p.add_argument("--walk-forward", action="store_true",
                   help="also run a rolling walk-forward comparison of the methods")
    p.add_argument("--formation-days", type=int, default=504,
                   help="walk-forward: days used to select pairs in each window (~2 years)")
    p.add_argument("--trading-days", type=int, default=126,
                   help="walk-forward: days traded before re-selecting (~6 months)")
    p.add_argument("--same-sector", action="store_true",
                   help="only test pairs within the same sector")
    p.add_argument("--sector-file",
                   help="CSV with columns ticker,sector (implies --same-sector); "
                        "defaults to the built-in map for the default tickers")
    p.add_argument("--synthetic-days", type=int, default=1000,
                   help="length of the synthetic universe")
    p.add_argument("--out", default="output")
    p.add_argument("--no-plots", action="store_true")
    return p.parse_args(argv)


def load(args) -> pd.DataFrame:
    if args.source == "synthetic":
        return synthetic_universe(n_days=args.synthetic_days)
    if args.source == "csv":
        if not args.csv:
            raise SystemExit("--csv is required with --source csv")
        return load_csv(args.csv)
    return load_yfinance(args.tickers, args.start, args.end)


def load_sectors(args, tickers) -> dict[str, str] | None:
    if not (args.same_sector or args.sector_file):
        return None
    if args.sector_file:
        df = pd.read_csv(args.sector_file)
        sectors = dict(zip(df["ticker"].astype(str), df["sector"].astype(str)))
    elif args.source == "synthetic":
        sectors = {t: t[0] for t in tickers}  # A1/A2 -> "A", etc.
    else:
        sectors = DEFAULT_SECTORS
    missing = [t for t in tickers if t not in sectors]
    if missing:
        print(f"No sector for {missing}; they will not be paired.")
    if not same_sector_pairs(tickers, sectors):
        raise SystemExit("No two tickers share a sector; add tickers or fix the sector map.")
    return sectors


def plot_best(prices, best, split, result, path: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(11, 9))
    legs = prices[[best["y"], best["x"]]]
    for col, series in (legs / legs.iloc[0]).items():
        axes[0].plot(series.index, series.values, lw=1, label=col)
    axes[0].axvline(split, color="grey", ls="--", lw=1)
    axes[0].legend(loc="upper left")
    axes[0].set_title(f"{best['pair']}: normalised prices (dashed = formation/trading split)")

    z = result.zscore
    axes[1].plot(z.index, z.values, lw=1, color="black")
    for lvl in (2, -2):
        axes[1].axhline(lvl, color="tab:red", ls=":", lw=1)
    axes[1].axhline(0, color="grey", lw=0.8)
    lo, hi = min(z.min(), -2.5), max(z.max(), 2.5)
    axes[1].fill_between(z.index, lo, hi, where=(result.position > 0).values, alpha=0.15, color="tab:green", label="long spread")
    axes[1].fill_between(z.index, lo, hi, where=(result.position < 0).values, alpha=0.15, color="tab:red", label="short spread")
    axes[1].legend(loc="upper left")
    axes[1].set_title("Out-of-sample spread z-score and positions")

    equity = (1 + result.returns).cumprod()
    axes[2].plot(equity.index, equity.values, color="tab:blue")
    axes[2].sharex(axes[1])
    axes[2].set_title(f"Out-of-sample equity — Sharpe {result.sharpe:.2f}, return {result.total_return:.1%}")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_walk_forward(returns: pd.DataFrame, path: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5))
    equity = (1 + returns).cumprod()
    order = equity.iloc[-1].sort_values(ascending=False).index
    for m in order:
        ax.plot(equity.index, equity[m].values, lw=1.4, label=f"{m} ({equity[m].iloc[-1] - 1:+.1%})")
    ax.axhline(1, color="grey", lw=0.8)
    ax.legend(loc="upper left")
    ax.set_title("Walk-forward out-of-sample equity by selection method")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run_walk_forward(prices, args, bt, out: Path, sectors):
    print(f"\nWalk-forward: {args.formation_days}-day formation, {args.trading_days}-day trading blocks, "
          f"top {args.top_k} pairs per method")
    wf = walk_forward(prices, args.formation_days, args.trading_days, top_k=args.top_k,
                      sectors=sectors, **bt)
    history = best_pair_history(wf)
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:.3f}".format):
        print("\nWalk-forward method comparison (all trading blocks joined):")
        print(wf.summary.to_string())
        print("\nComposite top pick in each window:")
        print(history.to_string(index=False))
    wf.summary.to_csv(out / "walk_forward_summary.csv")
    wf.windows.to_csv(out / "walk_forward_windows.csv", index=False)
    wf.picks.to_csv(out / "walk_forward_picks.csv", index=False)
    wf.returns.to_csv(out / "walk_forward_returns.csv")
    if not args.no_plots:
        plot_walk_forward(wf.returns, out / "walk_forward.png")


def main(argv=None):
    args = parse_args(argv)
    prices = load(args)
    if prices.shape[1] < 2:
        raise SystemExit("Need at least two tickers with data.")
    split = split_date(prices, args.formation_frac)
    print(f"Universe: {prices.shape[1]} tickers, {len(prices)} days "
          f"({prices.index[0].date()} → {prices.index[-1].date()}); split at {split.date()}\n")

    sectors = load_sectors(args, list(prices.columns))
    n_pairs = len(same_sector_pairs(prices.columns, sectors)) if sectors else prices.shape[1] * (prices.shape[1] - 1) // 2
    print(f"Testing {n_pairs} candidate pairs" + (" (same sector only)" if sectors else "") + "\n")
    table = analyse_pairs(prices, split, sectors=sectors)
    bt = dict(entry=args.entry, exit=args.exit, stop=args.stop, cost_bps=args.cost_bps)
    summary, detail = compare_methods(prices, table, split, top_k=args.top_k, **bt)

    cols = ["pair", "eligible", "score", "eg_pvalue", "eg_pvalue_bh", "johansen_ratio",
            "half_life", "hurst", "crossings_per_yr", "return_corr", "ssd"]
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:.3f}".format):
        print("Pair statistics (formation window), best first:")
        print(table[cols].head(15).to_string(index=False))
        print(f"\nMethod comparison — top {args.top_k} pairs each, out-of-sample:")
        print(summary.to_string())

    best = pick_best_pair(table)
    logp = np.log(prices)
    result = backtest_pair(logp[best["y"]], logp[best["x"]], split, **bt)
    print(f"\nBest pair: {best['pair']}  (long 1 {best['y']} / short {best['beta']:.2f} {best['x']})")
    print(f"  EG p={best['eg_pvalue']:.4f} (BH {best['eg_pvalue_bh']:.4f}), Johansen ratio "
          f"{best['johansen_ratio']:.2f}, half-life {best['half_life']:.1f}d, Hurst {best['hurst']:.2f}")
    print(f"  Out-of-sample: Sharpe {result.sharpe:.2f}, return {result.total_return:.1%}, "
          f"max DD {result.max_drawdown:.1%}, {result.n_trades} trades")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.walk_forward:
        run_walk_forward(prices, args, bt, out, sectors)
    table.to_csv(out / "pair_stats.csv", index=False)
    summary.to_csv(out / "method_comparison.csv")
    detail.to_csv(out / "method_detail.csv", index=False)
    if not args.no_plots:
        plot_best(prices, best, split, result, out / "best_pair.png")
    print(f"\nResults written to {out}/")


if __name__ == "__main__":
    main()
