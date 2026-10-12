"""Hierarchical Bradley-Terry team ratings: strength = region effect + team effect.

logit P(blue wins) = side + R[region_blue] - R[region_red] + T[blue] - T[red]

- Games are weighted by recency (exponential half-life) and international games get extra weight,
  because they are the only games that pin down region gaps.
- Team effects are L2-shrunk toward 0, i.e. toward their region's mean, so teams with no
  international games (C9, MVK) are rated through their league opponents.

Usage:
    python -m model.ratings              # backtest grid + current ratings for Worlds teams
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import minimize

DB = "data/pickems.duckdb"

DOMESTIC = {
    "LCK": "LCK", "LPL": "LPL", "LEC": "LEC",
    "LCS": "LCS", "LTA N": "LCS",
    "CBLOL": "CBLOL", "LTA S": "CBLOL",
    "LCP": "LCP", "VCS": "LCP", "PCS": "LCP", "LJL": "LCP",
}
EXTRA = {"WLDs", "WLDQ", "MSI", "FST", "EWC", "EWCQ"}
INTERNATIONAL = {"WLDs", "MSI", "FST", "EWC"}


@dataclass
class Params:
    # chosen by backtest on 8 international events 2024-26 (log-loss 0.627 vs 0.693 coin);
    # the top of the grid is flat, so the shorter half-life is preferred for roster turnover
    half_life_days: float = 365.0
    intl_weight: float = 1.0
    lam_team: float = 30.0
    lam_region: float = 0.3
    window_days: int = 730


def load_games(con) -> pd.DataFrame:
    leagues = ",".join(f"'{x}'" for x in set(DOMESTIC) | EXTRA)
    return con.sql(f"""
        select game_id, league, date_utc, blue_team, red_team, blue_team_id, red_team_id, blue_win, is_international
        from games where league in ({leagues}) and blue_team_id is not null and red_team_id is not null
        order by date_utc""").df()


def team_regions(games: pd.DataFrame) -> pd.Series:
    """Region per team_id = most frequent region among its domestic games."""
    dom = games[games["league"].isin(DOMESTIC)]
    long = pd.concat([
        pd.DataFrame({"team_id": dom["blue_team_id"], "region": dom["league"].map(DOMESTIC), "date": dom["date_utc"]}),
        pd.DataFrame({"team_id": dom["red_team_id"], "region": dom["league"].map(DOMESTIC), "date": dom["date_utc"]}),
    ])
    # latest season dominates: count only the last 365 days a team played domestically
    last = long.groupby("team_id")["date"].transform("max")
    long = long[long["date"] > last - pd.Timedelta(days=365)]
    return long.groupby("team_id")["region"].agg(lambda s: s.value_counts().index[0])


class BTModel:
    def __init__(self, params: Params | None = None):
        self.p = params or Params()

    def fit(self, games: pd.DataFrame, as_of: pd.Timestamp, regions: pd.Series) -> "BTModel":
        p = self.p
        g = games[(games["date_utc"] < as_of) & (games["date_utc"] >= as_of - pd.Timedelta(days=p.window_days))]
        g = g[g["blue_team_id"].isin(regions.index) & g["red_team_id"].isin(regions.index)]
        self.teams = pd.Index(sorted(set(g["blue_team_id"]) | set(g["red_team_id"])))
        self.regions = pd.Index(sorted(regions.loc[self.teams].unique()))
        self.team_region = regions.loc[self.teams]

        bi, ri = self.teams.get_indexer(g["blue_team_id"]), self.teams.get_indexer(g["red_team_id"])
        rr = self.regions.get_indexer(self.team_region.values)
        y = g["blue_win"].astype(float).values
        age = (as_of - g["date_utc"]).dt.total_seconds().values / 86400
        w = 0.5 ** (age / p.half_life_days) * np.where(g["is_international"], p.intl_weight, 1.0)

        nT, nR = len(self.teams), len(self.regions)

        def unpack(x):
            return x[0], x[1:1 + nR], x[1 + nR:]

        def loss(x):
            side, R, T = unpack(x)
            z = side + R[rr[bi]] - R[rr[ri]] + T[bi] - T[ri]
            pr = 1 / (1 + np.exp(-z))
            ll = -(w * (y * np.log(pr + 1e-12) + (1 - y) * np.log(1 - pr + 1e-12))).sum()
            ll += p.lam_team * (T ** 2).sum() + p.lam_region * (R ** 2).sum()
            r = w * (pr - y)
            gT = np.bincount(bi, r, nT) - np.bincount(ri, r, nT) + 2 * p.lam_team * T
            gR = np.bincount(rr[bi], r, nR) - np.bincount(rr[ri], r, nR) + 2 * p.lam_region * R
            return ll, np.concatenate([[r.sum()], gR, gT])

        res = minimize(loss, np.zeros(1 + nR + nT), jac=True, method="L-BFGS-B")
        self.side, R, T = unpack(res.x)
        self.R = pd.Series(R - R.mean(), self.regions)
        self.T = pd.Series(T, self.teams)
        self._laplace = (bi, ri, rr, w, res.x)
        return self

    def strength_cov(self, team_ids: list[str]) -> np.ndarray:
        """Laplace approximation: covariance of (region + team) strength for the given teams,
        from the inverse Hessian of the penalized weighted log-likelihood at the optimum.
        Only differences between strengths matter, and those are unaffected by centering R."""
        from scipy import sparse
        bi, ri, rr, w, x = self._laplace
        nT, nR, n = len(self.teams), len(self.regions), len(bi)
        side, R, T = x[0], x[1:1 + nR], x[1 + nR:]
        pr = 1 / (1 + np.exp(-(side + R[rr[bi]] - R[rr[ri]] + T[bi] - T[ri])))
        rows = np.repeat(np.arange(n), 5)
        cols = np.stack([np.zeros(n, int), 1 + rr[bi], 1 + rr[ri], 1 + nR + bi, 1 + nR + ri], 1).ravel()
        vals = np.tile([1.0, 1.0, -1.0, 1.0, -1.0], n)
        X = sparse.csr_matrix((vals, (rows, cols)), shape=(n, 1 + nR + nT))   # duplicates (same region) sum to 0
        v = w * pr * (1 - pr)
        H = (X.T @ sparse.diags(v) @ X).toarray()
        H[np.arange(1, 1 + nR), np.arange(1, 1 + nR)] += 2 * self.p.lam_region
        H[np.arange(1 + nR, 1 + nR + nT), np.arange(1 + nR, 1 + nR + nT)] += 2 * self.p.lam_team
        A = np.zeros((len(team_ids), 1 + nR + nT))
        for k, t in enumerate(team_ids):
            A[k, 1 + self.regions.get_loc(self.team_region[t])] = 1
            A[k, 1 + nR + self.teams.get_loc(t)] = 1
        return A @ np.linalg.solve(H, A.T)

    def strength(self, team_id: str) -> float:
        if team_id in self.T.index:
            return self.R[self.team_region[team_id]] + self.T[team_id]
        return np.nan

    def p_game(self, a: str, b: str, a_blue: bool | None = None) -> float:
        """P(a beats b). Side unknown -> average of both sides."""
        d = self.strength(a) - self.strength(b)
        if a_blue is None:
            return 0.5 * (1 / (1 + np.exp(-(d + self.side))) + 1 / (1 + np.exp(-(d - self.side))))
        return 1 / (1 + np.exp(-(d + (self.side if a_blue else -self.side))))


def series_prob(p: float, best_of: int) -> float:
    """P(win a best-of series) with constant per-game win probability p."""
    from math import comb
    need = best_of // 2 + 1
    return sum(comb(need - 1 + k, k) * p ** need * (1 - p) ** k for k in range(need))


# --- backtest -------------------------------------------------------------------------------

EVENTS = {  # name: (league, start, end)
    "Worlds 2024": ("WLDs", "2024-09-25", "2024-11-03"),
    "First Stand 2025": ("FST", "2025-03-10", "2025-03-17"),
    "MSI 2025": ("MSI", "2025-06-27", "2025-07-14"),
    "EWC 2025": ("EWC", "2025-07-01", "2025-07-21"),
    "Worlds 2025": ("WLDs", "2025-10-14", "2025-11-10"),
    "First Stand 2026": ("FST", "2026-03-16", "2026-03-23"),
    "MSI 2026": ("MSI", "2026-06-28", "2026-07-13"),
    "EWC 2026": ("EWC", "2026-07-01", "2026-07-20"),
}


def backtest(games: pd.DataFrame, regions: pd.Series, params: Params) -> pd.DataFrame:
    rows = []
    for name, (league, start, end) in EVENTS.items():
        start = pd.Timestamp(start)
        ev = games[(games["league"] == league) & (games["date_utc"] >= start) & (games["date_utc"] < pd.Timestamp(end))]
        if ev.empty:
            continue
        m = BTModel(params).fit(games, start, regions)
        known = ev["blue_team_id"].isin(m.T.index) & ev["red_team_id"].isin(m.T.index)
        ev = ev[known]
        y = ev["blue_win"].astype(float).values
        pm = np.array([m.p_game(b, r, True) for b, r in zip(ev["blue_team_id"], ev["red_team_id"])])
        # baseline: region strength only (what "trust the region seeding" gives)
        pr = np.array([1 / (1 + np.exp(-(m.side + m.R[m.team_region[b]] - m.R[m.team_region[r]])))
                       for b, r in zip(ev["blue_team_id"], ev["red_team_id"])])
        ll = lambda q: -np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))
        rows.append({"event": name, "games": len(ev), "ll_model": ll(pm), "ll_region": ll(pr), "ll_coin": np.log(2),
                     "brier_model": np.mean((pm - y) ** 2), "acc_model": np.mean((pm > .5) == y)})
    return pd.DataFrame(rows)


def main():
    con = duckdb.connect(DB, read_only=True)
    games = load_games(con)
    regions = team_regions(games)

    grid = []
    for hl in (60, 120, 240):
        for lam in (1.0, 3.0, 10.0):
            for iw in (1.0, 3.0):
                bt = backtest(games, regions, Params(half_life_days=hl, lam_team=lam, intl_weight=iw))
                grid.append({"half_life": hl, "lam_team": lam, "intl_w": iw,
                             "ll_model": np.average(bt.ll_model, weights=bt.games),
                             "ll_region": np.average(bt.ll_region, weights=bt.games),
                             "acc": np.average(bt.acc_model, weights=bt.games)})
    grid = pd.DataFrame(grid).sort_values("ll_model")
    print("== backtest grid (game-weighted mean log-loss; coin = 0.693)\n", grid.to_string(index=False))
    best = grid.iloc[0]
    params = Params(half_life_days=best.half_life, lam_team=best.lam_team, intl_weight=best.intl_w)
    print("\n== per-event, best params\n", backtest(games, regions, params).round(3).to_string(index=False))

    m = BTModel(params).fit(games, pd.Timestamp("2026-10-15"), regions)
    print(f"\nside advantage (blue, log-odds): {m.side:.3f}")
    print("region effects:\n", m.R.sort_values(ascending=False).round(3).to_string())
    return m, params


if __name__ == "__main__":
    main()
