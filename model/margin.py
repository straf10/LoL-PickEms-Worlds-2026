"""Margin signal: gold difference at 15:00 as extra information for the team ratings.

Two variants on top of the Bradley-Terry model in model.ratings (both use the same training
window, recency weights, region + team structure and L2 shrinkage as BTModel):

  A. joint  - one objective. Win/loss log-likelihood plus alpha * Gaussian term on the scaled
              gold difference: g/scale ~ N(beta * (strength_diff + side_gd), 1).
              The win probability is still the logistic part; gold only shapes the strengths.
  B. blend  - fit BTModel as is, fit a weighted ridge regression of g/scale on the same
              region + team design (own intercept), then  z = z_bt + gamma * z_gold.

Only games with date_utc < as_of are used, so the harness's as_of (event start) is leak-free.
Games without a gold value still count for the win/loss part.

Usage:
    python -m model.margin      # tunes on Worlds 2022 - Worlds 2024, reports held-out 2025-26
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from model.backtest import EVENTS, bt_predict, evaluate
from model.ratings import DB, DOMESTIC, EXTRA, BTModel, Params, series_prob, team_regions

TUNE_EVENTS = ["Worlds 2022", "MSI 2023", "Worlds 2023", "MSI 2024", "Worlds 2024"]
HELD_EVENTS = [e for e in EVENTS if e not in TUNE_EVENTS]

_DATA: dict = {}
_FITS: dict = {}


# --- data ----------------------------------------------------------------------------------------

def load_games_gold(con) -> pd.DataFrame:
    """Same rows as model.ratings.load_games, plus the 15-minute gold difference."""
    leagues = ",".join(f"'{x}'" for x in set(DOMESTIC) | EXTRA)
    return con.sql(f"""
        select game_id, league, date_utc, blue_team, red_team, blue_team_id, red_team_id, blue_win,
               is_international, blue_golddiff15
        from games where league in ({leagues}) and blue_team_id is not null and red_team_id is not null
        order by date_utc""").df()


def _data(con):
    if "games" not in _DATA:
        games = load_games_gold(con)
        _DATA["games"] = games
        _DATA["regions"] = team_regions(games)
        _DATA["scale"] = float(games["blue_golddiff15"].std())  # ~2.5k: one "unit" of gold
    return _DATA["games"], _DATA["regions"], _DATA["scale"]


def _train_slice(games, regions, as_of, p: Params) -> dict:
    """Mirror of BTModel.fit's data selection, plus the gold column."""
    g = games[(games["date_utc"] < as_of) & (games["date_utc"] >= as_of - pd.Timedelta(days=p.window_days))]
    g = g[g["blue_team_id"].isin(regions.index) & g["red_team_id"].isin(regions.index)]
    teams = pd.Index(sorted(set(g["blue_team_id"]) | set(g["red_team_id"])))
    team_region = regions.loc[teams]
    regs = pd.Index(sorted(team_region.unique()))
    rr = regs.get_indexer(team_region.values)
    bi, ri = teams.get_indexer(g["blue_team_id"]), teams.get_indexer(g["red_team_id"])
    y = g["blue_win"].astype(float).values
    age = (as_of - g["date_utc"]).dt.total_seconds().values / 86400
    w = 0.5 ** (age / p.half_life_days) * np.where(g["is_international"], p.intl_weight, 1.0)
    gd = g["blue_golddiff15"].to_numpy(dtype=float)
    return dict(teams=teams, regs=regs, team_region=team_region, rr=rr, bi=bi, ri=ri, y=y, w=w, gd=gd)


def _strength(T: pd.Series, R: pd.Series, team_region: pd.Series) -> pd.Series:
    return T + R.loc[team_region.loc[T.index].values].values


def _pair_diff(strength: pd.Series, ev: pd.DataFrame) -> np.ndarray:
    """strength(blue) - strength(red) per game; NaN when a team is not rated."""
    return strength.reindex(ev["blue_team_id"].values).values - strength.reindex(ev["red_team_id"].values).values


def _sigmoid(z):
    return 1 / (1 + np.exp(-z))


def p_neutral(d: np.ndarray, side: float) -> np.ndarray:
    """P(team a beats b) with side unknown: average of both sides (as BTModel.p_game does)."""
    return 0.5 * (_sigmoid(d + side) + _sigmoid(d - side))


# --- variant A: joint objective ------------------------------------------------------------------

def _joint_objective(x, bi, ri, rr, y, w, gd, hm, nT, nR, alpha, lam_team, lam_region):
    """Loss and gradient. x = [side, side_gd, beta, R (nR), T (nT)]; gd is the scaled gold diff
    (0 where missing, hm = 1 where observed)."""
    side, sg, beta = x[0], x[1], x[2]
    R, T = x[3:3 + nR], x[3 + nR:]
    d = R[rr[bi]] - R[rr[ri]] + T[bi] - T[ri]
    pr = _sigmoid(side + d)
    ll = -(w * (y * np.log(pr + 1e-12) + (1 - y) * np.log(1 - pr + 1e-12))).sum()
    e = (gd - beta * (d + sg)) * hm                       # gold residual, observed games only
    ll += 0.5 * alpha * (w * e * e).sum()
    ll += lam_team * (T ** 2).sum() + lam_region * (R ** 2).sum()
    r = w * (pr - y)
    q = r - alpha * w * beta * e                          # dL/d(strength diff), both terms
    g_side = r.sum()
    g_sg = (-alpha * w * beta * e).sum()
    g_beta = -(alpha * w * e * (d + sg)).sum()
    gT = np.bincount(bi, q, nT) - np.bincount(ri, q, nT) + 2 * lam_team * T
    gR = np.bincount(rr[bi], q, nR) - np.bincount(rr[ri], q, nR) + 2 * lam_region * R
    return ll, np.concatenate([[g_side, g_sg, g_beta], gR, gT])


class _Fit:
    def __init__(self, side, strength, **extra):
        self.side = side
        self.strength = strength
        self.extra = extra


def fit_joint(games, regions, as_of, alpha: float, scale: float, p: Params,
              fix_beta: float | None = 1.0) -> _Fit:
    """fix_beta=None frees beta. Free beta is not identified against the strength scale: the gold
    term is then indifferent to a rescaling of the strengths, the L2 penalty shrinks them, and beta
    absorbs the change (observed: team sd 1.18 -> 0.45 at alpha=0.25). Fixing beta removes that."""
    sl = _train_slice(games, regions, as_of, p)
    nT, nR = len(sl["teams"]), len(sl["regs"])
    hm = (~np.isnan(sl["gd"])).astype(float)
    gd = np.nan_to_num(sl["gd"] / scale)
    x0 = np.zeros(3 + nR + nT)
    bounds = [(None, None)] * (3 + nR + nT)
    if fix_beta is None:
        x0[2] = 0.5                                       # free: starts at half a unit of gold per logit
    else:
        x0[2] = fix_beta
        bounds[2] = (fix_beta, fix_beta)                  # L-BFGS-B keeps a degenerate bound fixed
    res = minimize(_joint_objective, x0,
                   args=(sl["bi"], sl["ri"], sl["rr"], sl["y"], sl["w"], gd, hm, nT, nR,
                         alpha, p.lam_team, p.lam_region),
                   jac=True, method="L-BFGS-B", bounds=bounds)
    x = res.x
    R = pd.Series(x[3:3 + nR] - x[3:3 + nR].mean(), sl["regs"])
    T = pd.Series(x[3 + nR:], sl["teams"])
    return _Fit(side=x[0], strength=_strength(T, R, sl["team_region"]),
                side_gd=x[1], beta=x[2], converged=bool(res.success))


# --- variant B: BT + gold ridge blend ------------------------------------------------------------

def fit_gold_ridge(sl: dict, scale: float, lam_team: float, lam_region: float = 1.0) -> pd.Series:
    """Weighted ridge of g/scale on the region + team design, with an unpenalised intercept.
    Returns the gold-implied strength per team (in units of scale)."""
    nT, nR = len(sl["teams"]), len(sl["regs"])
    m = ~np.isnan(sl["gd"])
    bi, ri, wm = sl["bi"][m], sl["ri"][m], sl["w"][m]
    ym = sl["gd"][m] / scale
    n = len(ym)
    X = np.zeros((n, nR + nT))
    idx = np.arange(n)
    X[idx, sl["rr"][bi]] += 1
    X[idx, sl["rr"][ri]] -= 1
    X[idx, nR + bi] += 1
    X[idx, nR + ri] -= 1
    xbar = wm @ X / wm.sum()
    ybar = wm @ ym / wm.sum()
    Xc, yc = X - xbar, ym - ybar
    A = Xc.T @ (Xc * wm[:, None]) + np.diag(np.r_[np.full(nR, lam_region), np.full(nT, lam_team)])
    coef = np.linalg.solve(A, Xc.T @ (wm * yc))
    return pd.Series(coef[nR:] + coef[sl["rr"]], sl["teams"])


# --- predict factory -----------------------------------------------------------------------------

def make_predict(variant: str = "joint", alpha: float = 0.5, scale: float | None = None,
                 fix_beta: float | None = 1.0, lam_gd: float = 30.0, gamma: float = 0.5,
                 params: Params | None = None):
    """Predict function for model.backtest.evaluate.

    variant="joint":    alpha = weight of the gold term (0 reproduces BTModel exactly).
    variant="blend":    lam_gd = ridge penalty on gold team effects, gamma = weight of gold strength.
    variant="baseline": the current team model (model.backtest.bt_predict).
    """
    p = params or Params()

    def predict(con, as_of, ev):
        if variant == "baseline":
            return bt_predict(con, as_of, ev, p)
        games, regions, gscale = _data(con)
        s = scale or gscale
        if variant == "joint":
            key = ("joint", as_of, alpha, s, fix_beta, p.half_life_days, p.lam_team, p.lam_region, p.intl_weight)
            if key not in _FITS:
                _FITS[key] = fit_joint(games, regions, as_of, alpha, s, p, fix_beta)
            f = _FITS[key]
            d = _pair_diff(f.strength, ev)
            return _sigmoid(f.side + d)
        if variant == "blend":
            bkey = ("bt", as_of, p.half_life_days, p.lam_team, p.lam_region, p.intl_weight)
            if bkey not in _FITS:
                _FITS[bkey] = BTModel(p).fit(games, as_of, regions)
            bt = _FITS[bkey]
            d_bt = _pair_diff(_strength(bt.T, bt.R, bt.team_region), ev)
            gkey = ("gold", as_of, s, lam_gd, p.half_life_days, p.intl_weight)
            if gkey not in _FITS:
                sl = _train_slice(games, regions, as_of, p)
                _FITS[gkey] = fit_gold_ridge(sl, s, lam_gd)
            d_gd = _pair_diff(_FITS[gkey], ev)
            return _sigmoid(bt.side + d_bt + gamma * d_gd)
        raise ValueError(variant)

    return predict


# --- evaluation ----------------------------------------------------------------------------------

def paired_stats(base: pd.DataFrame, var: pd.DataFrame, events: list[str] | None = None,
                 n_boot: int = 2000, seed: int = 0) -> dict:
    """Metrics on games both models can rate (inner join on event + game_id)."""
    m = base.merge(var, on=["event", "game_id"], suffixes=("_b", "_v"))
    m = m.dropna(subset=["p_blue_b", "p_blue_v"])
    if events is not None:
        m = m[m["event"].isin(events)]
    y = m["blue_win_b"].astype(float).values
    pb = np.clip(m["p_blue_b"].values, 1e-6, 1 - 1e-6)
    pv = np.clip(m["p_blue_v"].values, 1e-6, 1 - 1e-6)
    lb = -(y * np.log(pb) + (1 - y) * np.log(1 - pb))
    lv = -(y * np.log(pv) + (1 - y) * np.log(1 - pv))
    diff = lv - lb
    rng = np.random.default_rng(seed)
    boots = np.array([diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)])
    return {
        "games": len(m),
        "ll_base": lb.mean(), "ll_var": lv.mean(), "d_ll": diff.mean(),
        "d_ll_se": diff.std(ddof=1) / np.sqrt(len(diff)),
        "p_var_better": float((boots < 0).mean()),
        "brier_base": np.mean((pb - y) ** 2), "brier_var": np.mean((pv - y) ** 2),
        "acc_base": np.mean((pb > .5) == y), "acc_var": np.mean((pv > .5) == y),
    }


def per_event(base: pd.DataFrame, var: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for e in EVENTS:
        if e not in set(base["event"]):
            continue
        s = paired_stats(base, var, [e], n_boot=10)
        rows.append({"event": e, "games": s["games"], "ll_base": s["ll_base"], "ll_var": s["ll_var"],
                     "d_ll": s["d_ll"]})
    return pd.DataFrame(rows)


def gold_signal_by_year(games: pd.DataFrame) -> pd.DataFrame:
    """How informative the 15-min gold is for international games, by year (Fearless from 2025)."""
    g = games[games["is_international"] & games["blue_golddiff15"].notna()].copy()
    g["year"] = g["date_utc"].dt.year
    rows = []
    for yr, s in g.groupby("year"):
        y = s["blue_win"].astype(float)
        slope = np.polyfit(s["blue_golddiff15"] / 1000, y, 1)[0]  # rough linear slope of win prob per 1k gold
        rows.append({"year": yr, "fearless": yr >= 2025, "n": len(s),
                     "corr": np.corrcoef(s["blue_golddiff15"], y)[0, 1], "slope_per_1k": slope})
    return pd.DataFrame(rows)


REFERENCE = ("joint alpha=0.0 scale=None fix_beta=1.0", "blend lam_gd=30.0 gamma=0.0")


def grid_configs():
    """(variant, kwargs). Zero gold weight (alpha=0 / gamma=0) is the BT reference, not a candidate."""
    cfgs = [("joint", dict(alpha=0.0, scale=None, fix_beta=1.0))]
    cfgs += [("joint", dict(alpha=a, scale=sc, fix_beta=1.0))
             for sc in (1500.0, 3000.0, 6000.0) for a in (0.1, 0.25, 0.5, 1.0)]
    cfgs += [("joint", dict(alpha=a, scale=None, fix_beta=None)) for a in (0.25, 1.0)]  # free beta, for the record
    cfgs += [("blend", dict(lam_gd=30.0, gamma=0.0))]
    cfgs += [("blend", dict(lam_gd=l, gamma=g)) for l in (10.0, 30.0, 100.0) for g in (0.25, 0.5, 1.0, 2.0)]
    return cfgs


def _label(variant, kw):
    return variant + " " + " ".join(f"{k}={v}" for k, v in kw.items())


def main():
    con = duckdb.connect(DB, read_only=True)
    base_rep, base_preds = evaluate(make_predict("baseline"), con=con)
    print("== baseline (current BT, ALL):", base_rep.round(4).iloc[-1].to_dict())

    results = []
    preds_by_label = {}
    for variant, kw in grid_configs():
        label = _label(variant, kw)
        rep, preds = evaluate(make_predict(variant, **kw), con=con)
        preds_by_label[label] = (variant, kw, preds)
        tune = paired_stats(base_preds, preds, TUNE_EVENTS, n_boot=200)
        held = paired_stats(base_preds, preds, HELD_EVENTS, n_boot=2000)
        allg = paired_stats(base_preds, preds, None, n_boot=200)
        results.append({"variant": label, "tune_d_ll": tune["d_ll"], "tune_ll": tune["ll_var"],
                        "held_d_ll": held["d_ll"], "held_se": held["d_ll_se"], "held_p_better": held["p_var_better"],
                        "held_ll": held["ll_var"], "all_d_ll": allg["d_ll"], "all_ll": allg["ll_var"]})
        print(f"  done {label}")
    res = pd.DataFrame(results)
    print("\n== grid (same games as baseline; d_ll < 0 means variant better)\n",
          res.round(4).to_string(index=False))

    best = {}
    for fam in ("joint", "blend"):
        sub = res[res["variant"].str.startswith(fam) & ~res["variant"].isin(REFERENCE)]
        best[fam] = sub.loc[sub["tune_ll"].idxmin(), "variant"]
    print("\n== best per family (gold weight > 0) chosen on tuning events:", best)
    for fam, label in best.items():
        variant, kw, preds = preds_by_label[label]
        print(f"\n== {label}: per-event (common games)")
        print(per_event(base_preds, preds).round(4).to_string(index=False))

    print("\n== gold signal by year (international games)\n",
          gold_signal_by_year(_data(con)[0]).round(3).to_string(index=False))

    # Play-In probabilities with the chosen family's best variant, fitted as of 2026-10-15.
    games, regions, _ = _data(con)
    as_of = pd.Timestamp("2026-10-15")
    teams = {"FURIA": "oe:team:87e3e1e75839f75a10bbc66e894d806", "MVK": "oe:team:bc3824b0bbb8139d16109178faa4822",
             "Cloud9": "oe:team:fc8e90107dabb9a35c490b0d86adea0", "KC": "oe:team:f3aa9bbd924ce3af42ac53f8326bc7c"}
    matchups = [("FURIA", "MVK"), ("Cloud9", "KC")]
    print("\n== Play-In probabilities (fit as of 2026-10-15)")
    for fam, label in best.items():
        variant, kw, _ = preds_by_label[label]
        if variant == "joint":
            f = fit_joint(games, regions, as_of, kw["alpha"], kw["scale"] or _data(con)[2], Params(), kw["fix_beta"])
            side, s = f.side, f.strength
        else:
            bt = BTModel(Params()).fit(games, as_of, regions)
            side, s = bt.side, _strength(bt.T, bt.R, bt.team_region)
            if kw["gamma"] != 0:
                sl = _train_slice(games, regions, as_of, Params())
                g = fit_gold_ridge(sl, _data(con)[2], kw["lam_gd"])
                s = s + kw["gamma"] * g.reindex(s.index).fillna(0.0)
        for a, b in matchups:
            d = s[teams[a]] - s[teams[b]]
            p = float(p_neutral(np.array([d]), side)[0])
            print(f"  [{label}] {a} vs {b}: P(game)={p:.3f}  P(Bo5)={series_prob(p, 5):.3f}")
    bt = BTModel(Params()).fit(games, as_of, regions)
    sb = _strength(bt.T, bt.R, bt.team_region)
    for a, b in matchups:
        p = float(p_neutral(np.array([sb[teams[a]] - sb[teams[b]]]), bt.side)[0])
        print(f"  [baseline BT] {a} vs {b}: P(game)={p:.3f}  P(Bo5)={series_prob(p, 5):.3f}")
    return res


if __name__ == "__main__":
    main()
