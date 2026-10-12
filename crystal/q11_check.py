"""Q11 check: how much of P(more games after 32:00) comes from uncertainty in the target share.

Steps: (1) Worlds gap vs same-year internationals and pre-Worlds domestic, 2022-2026;
(2) out-of-sample backtest of projection methods for Worlds 2023-25; (3) simulation with a per-sim
target share, reusing crystal.estimate's durations and sim.tournament.run; (4) tie count.
Writes outputs/q11/*.csv and prints the tables.

    python -m crystal.q11_check [n_sims]
"""
from __future__ import annotations

import math
import sys

import duckdb
import numpy as np
import pandas as pd

from common.paths import DB_PATH, OUTPUTS
from crystal.estimate import duration_pools
from model.predict import matrix_sampler, teams_table
from sim.tournament import run

OUT = OUTPUTS / "q11"
THR = 1920                                   # 32:00 in seconds; under = duration < THR, so exactly 32:00 is "after"
DOM = ["LCK", "LPL", "LEC", "LCS", "LCP", "CBLOL"]
INTL = ["MSI", "FST", "EWC"]
W26_START = pd.Timestamp("2026-10-15")       # Worlds 2026 lock / Play-In start (config/worlds2026.yaml)
SEEDS = (11, 12)


def load(con) -> pd.DataFrame:
    g = con.sql("select league, date_utc, duration_sec from games where date_utc >= '2022-01-01'").df()
    g["u"] = g.duration_sec < THR
    g["yr"] = g.date_utc.dt.year
    return g


def worlds_start(g: pd.DataFrame, y: int) -> pd.Timestamp:
    return W26_START if y == 2026 else g[(g.league == "WLDs") & (g.yr == y)].date_utc.min()


def year_table(g: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in range(2022, 2027):
        s = worlds_start(g, y)
        pre = lambda lo: g[(g.date_utc >= s - pd.Timedelta(days=lo)) & (g.date_utc < s)]
        pct = lambda x: (100 * x.u.mean(), len(x)) if len(x) else (np.nan, 0)
        wl = pct(g[(g.league == "WLDs") & (g.yr == y)])
        intl = pct(g[g.league.isin(INTL) & (g.yr == y)])
        d42 = pct(pre(42)[pre(42).league.isin(DOM)])
        d56 = pct(pre(56)[pre(56).league.isin(DOM)])
        dyr = pct(g[g.league.isin(DOM) & (g.yr == y)])
        rows.append({"year": y, "worlds_under": wl[0], "worlds_n": wl[1],
                     "intl_under": intl[0], "intl_n": intl[1],
                     "dom6wk_under": d42[0], "dom6wk_n": d42[1], "dom8wk_under": d56[0], "dom8wk_n": d56[1],
                     "dom_year_under": dyr[0], "dom_year_n": dyr[1]})
    t = pd.DataFrame(rows)
    t["gap_vs_intl"] = t.worlds_under - t.intl_under
    t["gap_vs_dom6wk"] = t.worlds_under - t.dom6wk_under
    t["gap_vs_dom8wk"] = t.worlds_under - t.dom8wk_under
    t["gap_vs_dom_year"] = t.worlds_under - t.dom_year_under
    return t


def backtest(t: pd.DataFrame) -> pd.DataFrame:
    """Predict Worlds Y's under-share using only years before Y. Errors = predicted - actual (points)."""
    t = t.set_index("year")
    methods = {
        "last Worlds": lambda y, p: t.loc[y - 1, "worlds_under"],
        "mean of prior Worlds": lambda y, p: t.loc[p, "worlds_under"].mean(),
        "same-year intl + prior intl gap": lambda y, p: t.loc[y, "intl_under"] + t.loc[p, "gap_vs_intl"].mean(),
        "same-year intl, no gap": lambda y, p: t.loc[y, "intl_under"],
        "6wk domestic + prior 6wk gap": lambda y, p: t.loc[y, "dom6wk_under"] + t.loc[p, "gap_vs_dom6wk"].mean(),
        "6wk domestic, no gap": lambda y, p: t.loc[y, "dom6wk_under"],
        "8wk domestic + prior 8wk gap": lambda y, p: t.loc[y, "dom8wk_under"] + t.loc[p, "gap_vs_dom8wk"].mean(),
    }
    rows = []
    for name, f in methods.items():
        err = []
        for y in (2023, 2024, 2025):
            p = [x for x in t.index if x < y]
            err.append(f(y, p) - t.loc[y, "worlds_under"])
        rows.append({"method": name, **{f"err {y}": e for y, e in zip((2023, 2024, 2025), err)},
                     "rmse": math.sqrt(np.mean(np.square(err)))})
    return pd.DataFrame(rows)


def project(t: pd.DataFrame, name: str) -> float:
    """2026 projected under-share (percent) for one method, using all of 2022-2025 for the gap."""
    t = t.set_index("year")
    prior = [2022, 2023, 2024, 2025]
    return {"intl": t.loc[2026, "intl_under"] + t.loc[prior, "gap_vs_intl"].mean(),
            "dom6wk": t.loc[2026, "dom6wk_under"] + t.loc[prior, "gap_vs_dom6wk"].mean(),
            "dom8wk": t.loc[2026, "dom8wk_under"] + t.loc[prior, "gap_vs_dom8wk"].mean(),
            "mean Worlds": t.loc[prior, "worlds_under"].mean(),
            "last Worlds": t.loc[2025, "worlds_under"]}[name]


def simulate(n: int, seed: int):
    """Same draws as crystal.estimate.estimate (sampler uncertainty, then duration noise), before the shift."""
    rng = np.random.default_rng(seed)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    teams = teams_table()
    region = teams.set_index("team_id")["region"].to_dict()
    games, _, _ = run(None, region, n=n, seed=seed, sampler=matrix_sampler())
    G = len(games)
    sim = games["sim"].to_numpy()
    dpool = duration_pools(con, teams)
    overall = np.concatenate(list(dpool.values())).mean()
    speed = {t: 0.5 * (v.mean() - overall) for t, v in dpool.items()}
    p_w = np.where(games["winner"] == games["a"], games["p_a"], 1 - games["p_a"]).astype(float)
    dur = (-85 * np.log(p_w / (1 - p_w)) + games["winner"].map(speed).fillna(0).to_numpy()
           + rng.normal(0, 290, G))
    base = np.maximum(dur, 17 * 60 - 1943)
    return base, sim


def bisect_shift(base: np.ndarray, target: float) -> float:
    lo, hi = 0.0, 4000.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if np.mean(base + mid < THR) > target else (lo, mid)
    return (lo + hi) / 2


def stats(dur, sim, n):
    G = np.bincount(sim, minlength=n)
    U = np.bincount(sim, weights=(dur < THR).astype(float), minlength=n)
    return U / G, G


def variant(base, sim, n, mu, sd, rng) -> dict:
    """sd = 0: one fixed shift so the pooled share is mu (current method). sd > 0: each sim draws its own
    target t ~ Normal(mu, sd) and is shifted so its games hit t on average (quantile map of the base durations)."""
    if sd == 0:
        dur = base + bisect_shift(base, mu)
    else:
        t = np.clip(rng.normal(mu, sd, n), 0.02, 0.98)
        dur = base + (THR - np.quantile(base, t))[sim]
    share, G = stats(dur, sim, n)
    z = (0.5 - mu) / math.sqrt(sd ** 2 + np.mean(mu * (1 - mu) / G))
    return {"pooled under": float(np.mean(dur < THR)), "mean sim share": float(share.mean()),
            "P(After)": float(np.mean(share < 0.5)), "P(Before)": float(np.mean(share > 0.5)),
            "P(tie)": float(np.mean(share == 0.5)), "mean games": float(G.mean()),
            "P(After) normal approx": 0.5 * (1 + math.erf(z / math.sqrt(2)))}


def main(n: int = 20000) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    g = load(con)
    t = year_table(g)
    t.round(2).to_csv(OUT / "gap_by_year.csv", index=False)
    print(t.round(2).to_string())
    bt = backtest(t)
    bt.round(2).to_csv(OUT / "backtest.csv", index=False)
    print(bt.round(2).to_string())

    rmse = bt.set_index("method")["rmse"] / 100
    # (name, projected mean, sd, backtest weight): sd of each projection = its own backtest RMSE
    w = lambda m: 1 / rmse[m] ** 2
    specs = [("(a) current: fixed 0.44", 0.44, 0.0, 0.0),
             ("(b) fixed 0.44 + target sd", 0.44, rmse["same-year intl + prior intl gap"], 0.0),
             ("(c) rebuilt: intl + gap, with sd", project(t, "intl") / 100, rmse["same-year intl + prior intl gap"],
              w("same-year intl + prior intl gap")),
             ("s1 intl 2026, no gap", t.set_index("year").loc[2026, "intl_under"] / 100,
              rmse["same-year intl, no gap"], w("same-year intl, no gap")),
             ("s2 recent domestic 6wk + gap", project(t, "dom6wk") / 100, rmse["6wk domestic + prior 6wk gap"],
              w("6wk domestic + prior 6wk gap")),
             ("s3 mean of all Worlds 2022-25", project(t, "mean Worlds") / 100, rmse["mean of prior Worlds"],
              w("mean of prior Worlds")),
             ("s4 last Worlds (2025)", project(t, "last Worlds") / 100, rmse["last Worlds"], w("last Worlds")),
             ("s5 recent domestic 6wk, no gap", t.set_index("year").loc[2026, "dom6wk_under"] / 100,
              rmse["6wk domestic, no gap"], w("6wk domestic, no gap"))]
    rows = []
    for seed in SEEDS:
        base, sim = simulate(n, seed)
        rng = np.random.default_rng(seed + 100)
        res = {}
        for name, mu, sd, wt in specs:
            res[name] = variant(base, sim, n, mu, float(sd), rng)
            rows.append({"variant": name, "seed": seed, "mu": round(mu, 4), "sd": round(float(sd), 4),
                         **res[name]})
        wsum = sum(wt for *_, wt in specs)
        avg = sum(wt * res[name]["P(After)"] for name, _, _, wt in specs) / wsum
        rows.append({"variant": "avg of projection methods (inverse MSE)", "seed": seed, "P(After)": avg})
        print(f"seed {seed}: sims {n}, games {len(base)}", flush=True)
    v = pd.DataFrame(rows)
    v.round(4).to_csv(OUT / "variants.csv", index=False)
    print(v.round(3).to_string())
    print(f"\nprojections (under-share %): intl+gap {project(t, 'intl'):.2f}, 6wk dom+gap {project(t, 'dom6wk'):.2f}, "
          f"8wk dom+gap {project(t, 'dom8wk'):.2f}, mean Worlds {project(t, 'mean Worlds'):.2f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000)
