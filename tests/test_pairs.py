import numpy as np
import pandas as pd
import pytest

from pairs import stats
from pairs.backtest import _positions, backtest_pair
from pairs.cli import main
from pairs.data import synthetic_universe
from pairs.selection import analyse_pairs, compare_methods, pick_best_pair, split_date
from pairs.walkforward import walk_forward


@pytest.fixture(scope="module")
def prices():
    return synthetic_universe()


@pytest.fixture(scope="module")
def table(prices):
    return analyse_pairs(prices, split_date(prices, 0.67))


def ou_series(theta, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = (1 - theta) * s[t - 1] + rng.normal(0, 0.01)
    return pd.Series(s)


def test_half_life_recovers_ou_parameter():
    theta = 0.1
    expected = -np.log(2) / np.log(1 - theta)  # ~6.6 bars
    assert stats.half_life(ou_series(theta)) == pytest.approx(expected, rel=0.25)


def test_half_life_of_random_walk_is_long():
    rw = pd.Series(np.cumsum(np.random.default_rng(1).normal(size=2000)))
    assert stats.half_life(rw) > 100


def test_hurst_separates_mean_reversion_from_random_walk():
    rw = pd.Series(np.cumsum(np.random.default_rng(2).normal(size=2000)))
    assert stats.hurst_exponent(ou_series(0.2)) < 0.3
    assert stats.hurst_exponent(rw) == pytest.approx(0.5, abs=0.1)


def test_finds_planted_cointegrated_pair(table):
    best = pick_best_pair(table)
    assert {best["y"], best["x"]} == {"A1", "A2"}
    assert best["eligible"]


def test_correlated_but_not_cointegrated_pair_is_rejected(table):
    c = table[table["pair"].isin(["C1/C2", "C2/C1"])].iloc[0]
    assert c["return_corr"] > 0.7  # correlation would pick it...
    assert not c["eligible"]  # ...cointegration does not


def test_position_state_machine():
    z = np.array([0, 2.1, 1.0, 0.4, -2.5, -1.0, -0.2, 4.5, 3.0])
    assert _positions(z, entry=2, exit=0.5, stop=4).tolist() == [0, -1, -1, 0, 1, 1, 0, 0, -1]


def test_no_reentry_after_stop_until_spread_reverts():
    # stopped out at 4.5; 3.0 and 2.5 would normally re-enter, but must wait
    # until |z| <= exit (0.3) before the next entry (2.2) is allowed
    z = np.array([2.5, 4.5, 3.0, 2.5, 0.3, 2.2])
    assert _positions(z, entry=2, exit=0.5, stop=4).tolist() == [-1, 0, 0, 0, 0, -1]


def test_same_sector_only_tests_pairs_within_a_sector(prices):
    sectors = {t: t[0] for t in prices.columns}
    table = analyse_pairs(prices, split_date(prices, 0.67), sectors=sectors)
    assert len(table) == 6  # A1-A2, B1-B2, C1-C2 and the three D pairs
    assert all(sectors[y] == sectors[x] for y, x in zip(table["y"], table["x"]))
    assert {table.iloc[0]["y"], table.iloc[0]["x"]} == {"A1", "A2"}


def test_unknown_sector_tickers_are_left_out(prices):
    table = analyse_pairs(prices, split_date(prices, 0.67), sectors={"A1": "x", "A2": "x", "B1": "y"})
    assert table["pair"].tolist() in (["A2/A1"], ["A1/A2"])
    with pytest.raises(ValueError):
        analyse_pairs(prices, split_date(prices, 0.67), sectors={"A1": "x", "B1": "y"})


def test_backtest_has_no_lookahead(prices):
    logp = np.log(prices)
    split = split_date(prices, 0.67)
    base = backtest_pair(logp["A2"], logp["A1"], split)

    cutoff = base.position.index[100]
    shocked = logp["A2"].copy()
    shocked[shocked.index > cutoff] += 0.5  # change only the future
    alt = backtest_pair(shocked, logp["A1"], split)

    pd.testing.assert_series_equal(base.position[:cutoff], alt.position[:cutoff])
    pd.testing.assert_series_equal(base.returns[:cutoff], alt.returns[:cutoff])


def test_compare_methods_shape(prices, table):
    summary, detail = compare_methods(prices, table, split_date(prices, 0.67), top_k=2)
    assert set(summary.index) == {"distance", "correlation", "engle_granger", "johansen", "composite"}
    assert len(detail) == 10


def test_cli_same_sector_walk_forward(tmp_path):
    main(["--source", "synthetic", "--same-sector", "--walk-forward", "--formation-days", "500",
          "--trading-days", "250", "--no-plots", "--out", str(tmp_path)])
    picks = pd.read_csv(tmp_path / "walk_forward_picks.csv")
    assert all(p.split("/")[0][0] == p.split("/")[1][0] for p in picks["pair"])


def test_cli_end_to_end(tmp_path):
    main(["--source", "synthetic", "--out", str(tmp_path)])
    for name in ("pair_stats.csv", "method_comparison.csv", "method_detail.csv", "best_pair.png"):
        assert (tmp_path / name).exists()


@pytest.fixture(scope="module")
def small_prices(prices):
    return prices[["A1", "A2", "C1", "C2", "D1"]]


def test_walk_forward_blocks_are_contiguous(small_prices):
    wf = walk_forward(small_prices, formation_days=500, trading_days=150, top_k=2, verbose=False)
    n_windows = (len(small_prices) - 500 - 150) // 150 + 1
    assert wf.windows["window"].nunique() == n_windows
    assert len(wf.returns) == n_windows * 150
    assert wf.returns.index.is_unique and wf.returns.index.is_monotonic_increasing
    assert wf.returns.index[0] == small_prices.index[500]
    assert "eligible_only" in wf.summary.index


def test_walk_forward_has_no_lookahead(small_prices):
    kw = dict(formation_days=500, trading_days=150, top_k=2, verbose=False)
    base = walk_forward(small_prices, **kw)
    cutoff = small_prices.index[720]  # inside the second trading block
    shocked = small_prices.copy()
    shocked.loc[shocked.index > cutoff, "A2"] *= 1.5
    alt = walk_forward(shocked, **kw)
    pd.testing.assert_frame_equal(base.returns[:cutoff], alt.returns[:cutoff])
