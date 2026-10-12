"""Player-based Bradley-Terry ratings.

logit P(blue wins) = side + sum(theta[blue players]) - sum(theta[red players]) + T[blue] - T[red]

Priors (L2 penalties):
  theta_p ~ N(R[home_region_p] / 5, 1/lam_player)   -> a player is shrunk toward their region's mean
  T_team  ~ N(0, 1/lam_team)                          -> small team synergy/coaching effect
  R       ~ N(0, 1/lam_region)

Region gaps are identified by international games AND by players who changed region:
a player's skill travels with them, so transfers link the regions' scales.

    python -m model.player_ratings          # backtest vs team model + Play-In odds
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from model.ratings import DOMESTIC, EXTRA

DB = "data/pickems.duckdb"


@dataclass
class PParams:
    half_life_days: float = 365.0
    lam_player: float = 10.0
    lam_team: float = 30.0
    lam_region: float = 0.3
    window_days: int = 730
    use_team: bool = True


def load(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    leagues = ",".join(f"'{x}'" for x in set(DOMESTIC) | EXTRA)
    games = con.sql(f"""
        select game_id, league, date_utc, blue_team_id, red_team_id, blue_win, is_international
        from games where league in ({leagues}) and blue_team_id is not null and red_team_id is not null
        order by date_utc""").df()
    pg = con.sql(f"""
        select game_id, player_id, team_id, side, league, date_utc from player_games
        where league in ({leagues}) and player_id is not null""").df()
    return games, pg


def home_regions(pg: pd.DataFrame, as_of: pd.Timestamp, days: int = 365) -> pd.Series:
    """Home region per player = most frequent domestic region in the last `days` before as_of."""
    d = pg[(pg["date_utc"] < as_of) & (pg["date_utc"] >= as_of - pd.Timedelta(days=days)) & pg["league"].isin(DOMESTIC)]
    reg = d["league"].map(DOMESTIC)
    return reg.groupby(d["player_id"]).agg(lambda s: s.value_counts().index[0])


class PlayerModel:
    def __init__(self, params: PParams | None = None):
        self.p = params or PParams()

    def fit(self, games: pd.DataFrame, pg: pd.DataFrame, as_of: pd.Timestamp) -> "PlayerModel":
        p = self.p
        g = games[(games["date_utc"] < as_of) & (games["date_utc"] >= as_of - pd.Timedelta(days=p.window_days))]
        roster = pg[pg["game_id"].isin(g["game_id"])]
        # keep games with exactly 5 identified players per side
        cnt = roster.groupby(["game_id", "side"]).size().unstack()
        good = cnt[(cnt.get("Blue") == 5) & (cnt.get("Red") == 5)].index
        g = g[g["game_id"].isin(good)].reset_index(drop=True)
        roster = roster[roster["game_id"].isin(good)]

        home = home_regions(pg, as_of, days=p.window_days)
        self.players = pd.Index(sorted(roster["player_id"].unique()))
        # players with no domestic games in window (e.g. only internationals) -> region of their team's games
        fallback = roster.groupby("player_id")["league"].agg(lambda s: s.map(DOMESTIC).dropna().mode().iloc[0]
                                                              if s.map(DOMESTIC).notna().any() else "OTHER")
        self.home = home.reindex(self.players).fillna(fallback.reindex(self.players)).fillna("OTHER")
        self.regions = pd.Index(sorted(self.home.unique()))
        self.teams = pd.Index(sorted(set(g["blue_team_id"]) | set(g["red_team_id"])))

        gidx = pd.Index(g["game_id"])
        roster = roster.assign(gi=gidx.get_indexer(roster["game_id"]), pi=self.players.get_indexer(roster["player_id"]))
        roster = roster.sort_values(["gi", "side", "pi"])
        B = roster[roster["side"] == "Blue"]["pi"].values.reshape(-1, 5)
        Rd = roster[roster["side"] == "Red"]["pi"].values.reshape(-1, 5)
        tb, tr = self.teams.get_indexer(g["blue_team_id"]), self.teams.get_indexer(g["red_team_id"])
        hr = self.regions.get_indexer(self.home.values)

        y = g["blue_win"].astype(float).values
        age = (as_of - g["date_utc"]).dt.total_seconds().values / 86400
        w = 0.5 ** (age / p.half_life_days)
        nP, nT, nR = len(self.players), len(self.teams), len(self.regions)

        def unpack(x):
            return x[0], x[1:1 + nR], x[1 + nR:1 + nR + nP], x[1 + nR + nP:]

        def loss(x):
            side, R, th, T = unpack(x)
            z = side + th[B].sum(1) - th[Rd].sum(1)
            if p.use_team:
                z = z + T[tb] - T[tr]
            pr = 1 / (1 + np.exp(-z))
            dev = th - R[hr] / 5
            ll = -(w * (y * np.log(pr + 1e-12) + (1 - y) * np.log(1 - pr + 1e-12))).sum()
            ll += p.lam_player * (dev ** 2).sum() + p.lam_team * (T ** 2).sum() + p.lam_region * (R ** 2).sum()
            r = w * (pr - y)
            gth = np.bincount(B.ravel(), np.repeat(r, 5), nP) - np.bincount(Rd.ravel(), np.repeat(r, 5), nP)
            gth += 2 * p.lam_player * dev
            gR = -2 * p.lam_player * np.bincount(hr, dev, nR) / 5 + 2 * p.lam_region * R
            gT = (np.bincount(tb, r, nT) - np.bincount(tr, r, nT)) if p.use_team else np.zeros(nT)
            gT = gT + 2 * p.lam_team * T
            return ll, np.concatenate([[r.sum()], gR, gth, gT])

        res = minimize(loss, np.zeros(1 + nR + nP + nT), jac=True, method="L-BFGS-B", options={"maxiter": 2000})
        self.side, R, th, T = unpack(res.x)
        self.R = pd.Series(R, self.regions)
        self.theta = pd.Series(th, self.players)
        self.T = pd.Series(T, self.teams)
        self._laplace = (B, Rd, tb, tr, hr, w, res.x)
        return self

    def strength_cov(self, lineups: list[tuple[list[str], str | None, str | None]]) -> np.ndarray:
        """Laplace covariance of team strengths. lineups = [(player_ids, team_id, region), ...].
        Unknown players contribute their region prior R/5 (and its uncertainty)."""
        from scipy import sparse
        B, Rd, tb, tr, hr, w, x = self._laplace
        p = self.p
        n, nP, nT, nR = len(B), len(self.players), len(self.teams), len(self.regions)
        oR, oP, oT = 1, 1 + nR, 1 + nR + nP
        side, R, th, T = x[0], x[oR:oP], x[oP:oT], x[oT:]
        z = side + th[B].sum(1) - th[Rd].sum(1) + ((T[tb] - T[tr]) if p.use_team else 0)
        pr = 1 / (1 + np.exp(-z))
        k = 13 if p.use_team else 11
        rows = np.repeat(np.arange(n), k)
        cols = [np.zeros((n, 1), int), oP + B, oP + Rd]
        vals = [np.ones((n, 1)), np.ones((n, 5)), -np.ones((n, 5))]
        if p.use_team:
            cols += [(oT + tb)[:, None], (oT + tr)[:, None]]
            vals += [np.ones((n, 1)), -np.ones((n, 1))]
        X = sparse.csr_matrix((np.hstack(vals).ravel(), (rows, np.hstack(cols).ravel())), shape=(n, oT + nT))
        H = X.T @ sparse.diags(w * pr * (1 - pr)) @ X
        # penalty Hessian: lam_player * (theta - R[h]/5)^2 + lam_team * T^2 + lam_region * R^2
        pi, ri, ti = np.arange(nP), np.arange(nR), np.arange(nT)
        cnt = np.bincount(hr, minlength=nR)
        pr_rows = np.concatenate([oP + pi, oP + pi, oR + hr, oR + ri, oT + ti])
        pr_cols = np.concatenate([oP + pi, oR + hr, oP + pi, oR + ri, oT + ti])
        pr_vals = np.concatenate([np.full(nP, 2 * p.lam_player), np.full(nP, -2 * p.lam_player / 5),
                                  np.full(nP, -2 * p.lam_player / 5), 2 * p.lam_player / 25 * cnt + 2 * p.lam_region,
                                  np.full(nT, 2 * p.lam_team)])
        H = H + sparse.coo_matrix((pr_vals, (pr_rows, pr_cols)), shape=H.shape)
        A = np.zeros((len(lineups), oT + nT))
        for k_, (players, team_id, region) in enumerate(lineups):
            for pid in players:
                if pid in self.theta.index:
                    A[k_, oP + self.players.get_loc(pid)] += 1
                elif region in self.regions:
                    A[k_, oR + self.regions.get_loc(region)] += 0.2
            if p.use_team and team_id in self.T.index:
                A[k_, oT + self.teams.get_loc(team_id)] = 1
        Hc = H.tocsc()
        from scipy.sparse.linalg import splu
        sol = splu(Hc).solve(A.T)
        return A @ sol

    def player(self, pid: str, region: str | None = None) -> float:
        """Unknown player -> prior mean of the given region (or 0)."""
        if pid in self.theta.index:
            return float(self.theta[pid])
        return float(self.R.get(region, 0.0)) / 5 if region else 0.0

    def strength(self, players: list[str], team_id: str | None = None, region: str | None = None) -> float:
        s = sum(self.player(x, region) for x in players)
        if self.p.use_team and team_id in self.T.index:
            s += float(self.T[team_id])
        return s

    def p_game(self, a_players, b_players, a_team=None, b_team=None, a_region=None, b_region=None, a_blue=None):
        d = self.strength(a_players, a_team, a_region) - self.strength(b_players, b_team, b_region)
        if a_blue is None:
            return 0.5 * (1 / (1 + np.exp(-(d + self.side))) + 1 / (1 + np.exp(-(d - self.side))))
        return 1 / (1 + np.exp(-(d + (self.side if a_blue else -self.side))))


# --- backtest adapter ------------------------------------------------------------------------

_cache: dict = {}


def make_predict(params: PParams | None = None):
    def predict(con, as_of, ev):
        if "data" not in _cache:
            _cache["data"] = load(con)
        games, pg = _cache["data"]
        m = PlayerModel(params).fit(games, pg, as_of)
        ev_roster = pg[pg["game_id"].isin(ev["game_id"])]
        out = []
        for _, row in ev.iterrows():
            r = ev_roster[ev_roster["game_id"] == row["game_id"]]
            bp, rp = r[r["side"] == "Blue"]["player_id"].tolist(), r[r["side"] == "Red"]["player_id"].tolist()
            if len(bp) != 5 or len(rp) != 5:
                out.append(np.nan)
                continue
            # unknown players: prior of the team's region as estimated from known teammates' home regions
            breg = m.home.reindex(bp).dropna().mode()
            rreg = m.home.reindex(rp).dropna().mode()
            out.append(m.p_game(bp, rp, row["blue_team_id"], row["red_team_id"],
                                breg.iloc[0] if len(breg) else None, rreg.iloc[0] if len(rreg) else None, True))
        return np.array(out)
    return predict


if __name__ == "__main__":
    from model.backtest import bt_predict, evaluate
    con = duckdb.connect(DB, read_only=True)
    base, _ = evaluate(bt_predict, con=con)
    print("== team model\n", base.round(4).to_string(index=False))
    for params in (PParams(), PParams(lam_player=3), PParams(lam_player=30), PParams(use_team=False)):
        rep, _ = evaluate(make_predict(params), con=con)
        print(f"\n== player model {params}\n", rep.round(4).to_string(index=False))
