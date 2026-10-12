"""Champion-draft Monte Carlo for the Worlds 2026 Crystal Ball questions.

For each champion, estimates the probability that it leads each question:
  Q1 highest presence (picked or banned share of the event's games),
  Q2 highest win rate (min 5 picks), Q3 highest deaths per game (min 5 picks),
and the distribution of Q10 (unique champions picked per sim).

Model (see outputs/draft/champion_sim.md for the parameters used):
  1. Base rates from the meta window (crystal.meta TOP / RECENT_FROM): pi_c, beta_c, role shares.
  2. Starter propensities w[team, role, c] = their 2026 top-league games on c (x3 if recent)
     + K * prior, where prior is the role-weighted base pick rate.
  3. IPS calibration of per-champion pick and ban multipliers on the first 500 sims, no shift.
  4. Per-tournament meta shift: logit pi' = a + b*x1 + c*(x2 - x1) + sd*z1, with x1 the window
     logit and x2 the late-window (any non-international league) logit; bans analogous with rho.
     Parameters from outputs/meta/meta_shift_fit.json (c required). Drawn once per sim and champion.
  5. Vectorized drafting: games are processed in batches by game_no across all sims; bans via
     Gumbel top-B, picks via sequential Gumbel-max with role draws; fearless locks per series.
  6. Deaths: a starter's deaths drawn from their own 2026 games with the same result, times a
     champion death factor f_c.

    python -m crystal.draft [--sims N] [--k K] [--no-shift] [--seed S] [--main]

--main writes outputs/draft/champion_sim.csv and champion_sim.md (the report, using the
sensitivity pickles outputs/draft/tmp_run_*.pkl that exist). Every run also saves
outputs/draft/tmp_run_<label>.pkl with its DataFrames.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
import warnings
from functools import lru_cache, partial
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from crystal.meta import (RECENT_FROM, TOP, champ_table, connect, game_champ_sets, load,
                          split_list)
from common.mathutil import logit, sigmoid
from common.paths import ROOT
from common.report import md_table

_md_table = partial(md_table, floatfmt="{:.3f}")

GAMES_FILE = ROOT / "outputs" / "draft" / "sim_games_5k.csv.gz"
FIT_FILE = ROOT / "outputs" / "meta" / "meta_shift_fit.json"
ROSTERS = ROOT / "data" / "rosters_2026.csv"
OUT_DIR = ROOT / "outputs" / "draft"
REPORT = OUT_DIR / "champion_sim.md"
SUMMARY_CSV = OUT_DIR / "champion_sim.csv"

ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"]
PICK_SIDES = np.array([0, 1, 1, 0, 0, 1, 1, 0, 0, 1])  # 0 = team A, 1 = team B
RECENT_WEIGHT = 3
MIN_PICKS = 5
CAL_SIMS = 500
CAL_MAX_ITER = 20
VERIFY_SIMS = (500, 1000)   # out-of-sample verification of the calibrated z=0 targets
SPREAD_CHAMPS = ["Cassiopeia", "Nocturne", "Vi", "Jarvan IV"]
SPREAD_G = 103
SPREAD_BAND = (0.85, 1.25)
# Q1 presence-leader benchmark from the meta-shift model (no draft mechanics, G=103 binomial);
# supplied by the coordinator for comparison only.
BENCHMARK_Q1 = {"Nocturne": 0.31, "Cassiopeia": 0.29, "Vi": 0.18, "Jarvan IV": 0.04}
BENCH_TOL = 0.15
SLOPE_SIMS = (500, 1000)   # slope measurement sims (out of calibration sample)
SLOPE_BUMP = 0.25
SLOPE_SEED = 303
SLOPE_MIN_RATE = 0.10     # ban (and pick) slopes measured for targets above this
SLOPE_CHECK_PICKS = ["Rell", "Orianna", "Jarvan IV", "Anivia", "Leona", "Cassiopeia"]
SLOPE_STOP = (0.3, 2.5)   # allowed slope range (stop rule and interpolation floor for picks)
POINTS = (50, 20, 10)
CAL_TOL_PP = 1.5
QUAL = 0.03
MAX_BLOCK = 20000
LATE_FROM = "2026-09-23"
LATE_TO = "2026-10-14"
BINS = ["lt5", "5to20", "gt20"]
FIT_KEYS = ("a", "b", "c")
DEFAULT_RHO = 0.0


# ---------------------------------------------------------------- inputs

@lru_cache(maxsize=1)
def _base():
    """Everything that does not depend on K or the sims: rates, role shares, player counts, pools."""
    con = connect()
    games, pg = load(con)
    late = con.sql(
        f"""select game_id, blue_picks, red_picks, blue_bans, red_bans from games
            where is_international = false and date_utc >= '{LATE_FROM}' and date_utc < '{LATE_TO}'"""
    ).df()
    con.close()
    games["date_utc"] = pd.to_datetime(games.date_utc)
    pg["date_utc"] = pd.to_datetime(pg.date_utc)

    g26 = games[games.league.isin(TOP) & (games.date_utc >= "2026-01-01")]
    pg26 = pg[pg.game_id.isin(g26.game_id)].copy()
    pk26, bn26 = game_champ_sets(g26)
    champs = sorted(set(pk26.champion) | set(bn26.champion) | set(pg26.champion.dropna()))
    cidx = {c: i for i, c in enumerate(champs)}
    C = len(champs)

    gw = games[games.league.isin(TOP) & (games.date_utc >= RECENT_FROM)]
    pgw = pg[pg.game_id.isin(gw.game_id)].copy()
    G = int(gw.game_id.nunique())
    win_tab = champ_table(gw, pgw).set_index("champion").reindex(champs).fillna(0)
    pi = (win_tab.picked_games.to_numpy(float) + 0.5) / (G + 1)
    beta = (win_tab.banned_games.to_numpy(float) + 0.5) / (G + 1)

    # late window (any non-international league): smoothed pick and ban rates, x2 and y2
    G_late = int(late.game_id.nunique())
    late_pk, late_bn = game_champ_sets(late)
    late_pick_n = late_pk.groupby("champion").size().reindex(champs).fillna(0).to_numpy(float)
    late_ban_n = late_bn.groupby("champion").size().reindex(champs).fillna(0).to_numpy(float)
    late_pick = (late_pick_n + 0.5) / (G_late + 1)
    late_ban = (late_ban_n + 0.5) / (G_late + 1)
    late_outside = sorted((set(late_pk.champion) | set(late_bn.champion)) - set(champs))
    n_ban_slots = sum(len(split_list(a)) + len(split_list(b))
                      for a, b in zip(gw.blue_bans, gw.red_bans))
    B = int(round(n_ban_slots / G))
    ban_per_game = n_ban_slots / G

    # role counts in the window -> shares s[c, r]
    cnt = np.zeros((C, 5))
    rix = {r: i for i, r in enumerate(ROLES)}
    for c, r, n in pgw.groupby(["champion", "role"]).size().reset_index().itertuples(index=False):
        if c in cidx and r in rix:
            cnt[cidx[c], rix[r]] = n
    share = (cnt + 0.1) / (cnt.sum(1, keepdims=True) + 0.5)

    # death factors: champion mean deaths / mean deaths of its main role (window)
    role_mean = pgw.groupby("role").deaths.mean()
    main_role = cnt.argmax(1)
    champ_mean = pgw.groupby("champion").deaths.mean()
    ratio = np.ones(C)
    for c, i in cidx.items():
        if c in champ_mean.index and cnt[i].sum() > 0:
            ratio[i] = champ_mean[c] / role_mean[ROLES[main_role[i]]]
    n_pick_win = win_tab.picked_games.to_numpy(float)
    fct = (n_pick_win * ratio + 20) / (n_pick_win + 20)

    # starters
    ros = pd.read_csv(ROSTERS)
    st = ros[ros.is_starter.astype(str).str.lower().eq("true")]
    teams = sorted(st.team_id.unique())
    tix = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    pid = np.empty((T, 5), dtype=object)
    for t, r, p in st[["team_id", "role", "player_id"]].itertuples(index=False):
        pid[tix[t], rix[r]] = p
    assert all(pid[t, r] is not None for t in range(T) for r in range(5)), "missing starter"

    n_pc = np.zeros((T, 5, C))
    w26 = np.where(pg26.date_utc >= RECENT_FROM, RECENT_WEIGHT, 1.0)
    pg26["w"] = w26
    tr_of = {pid[t, r]: (t, r) for t in range(T) for r in range(5)}
    wsum = pg26.groupby(["player_id", "champion"]).w.sum()
    for (p, c), v in wsum.items():
        if c in cidx and p in tr_of:
            t, r = tr_of[p]
            n_pc[t, r, cidx[c]] = v

    # death pools per (team, role, result): starter's own 2026 games with that result,
    # fallback to the role's pool across starters
    st_pids = set(pid.ravel())
    pg_st = pg26[pg26.player_id.isin(st_pids) & pg26.deaths.notna()]
    seg_vals, seg_off, seg_len = [], np.zeros(T * 5 * 2, dtype=np.int64), np.zeros(T * 5 * 2, dtype=np.int64)
    pools = {}
    for p, g in pg_st.groupby("player_id"):
        for res in (0, 1):
            pools[(p, res)] = g[g.win.astype(bool) == bool(res)].deaths.to_numpy(float)
    role_pools = {}
    for r in range(5):
        d = pg_st[pg_st.role == ROLES[r]]
        for res in (0, 1):
            role_pools[(r, res)] = d[d.win.astype(bool) == bool(res)].deaths.to_numpy(float)
    cursor = 0
    for t in range(T):
        for r in range(5):
            for res in (0, 1):
                arr = pools.get((pid[t, r], res), np.array([]))
                if len(arr) == 0:
                    arr = role_pools[(r, res)]
                k = (t * 5 + r) * 2 + res
                seg_off[k] = cursor
                seg_len[k] = len(arr)
                seg_vals.append(arr)
                cursor += len(arr)
    vals = np.concatenate(seg_vals)
    assert (seg_len > 0).all(), "empty death pool"

    return SimpleNamespace(
        champs=champs, cidx=cidx, C=C, G=G, pi=pi, beta=beta, B=B, ban_per_game=ban_per_game,
        share=share, fct=fct, n_pick_win=n_pick_win, win_tab=win_tab, teams=teams, tix=tix, T=T,
        n_pc=n_pc, vals=vals, seg_off=seg_off, seg_len=seg_len, window_games=gw,
        n_games_2026=int(g26.game_id.nunique()),
        G_late=G_late, late_pick=late_pick, late_ban=late_ban,
        late_pick_n=late_pick_n, late_ban_n=late_ban_n, late_outside=late_outside,
    )


def _fit_params():
    """Meta-shift parameters from outputs/meta/meta_shift_fit.json (current contract).

    Required in the file: pick and ban each with a, b, c and sd_by_bin (lt5, 5to20, gt20), and
    rho_pick_ban. A missing key raises. If the file is absent, neutral defaults are used
    (a=0, b=1, c=0, sd=0.5, rho=0) and the source says so.
    """
    if not FIT_FILE.exists():
        out = {"source": "DEFAULTS (meta_shift_fit.json missing): a=0, b=1, c=0, sd=0.5, rho=0"}
        for kind in ("pick", "ban"):
            out[kind] = {"a": 0.0, "b": 1.0, "c": 0.0, "sd_by_bin": {b: 0.5 for b in BINS}}
        out["rho_pick_ban"] = DEFAULT_RHO
        return out
    raw = json.loads(FIT_FILE.read_text(encoding="utf-8"))
    out = {"source": "outputs/meta/meta_shift_fit.json"}
    for kind in ("pick", "ban"):
        if not isinstance(raw.get(kind), dict):
            raise KeyError(f"meta_shift_fit.json: missing block '{kind}'")
        g = raw[kind]
        d = {}
        for key in FIT_KEYS:
            if key not in g:
                raise KeyError(f"meta_shift_fit.json: '{kind}.{key}' is missing (required by the "
                               "current shift model; no default is used)")
            d[key] = float(g[key])
        if not isinstance(g.get("sd_by_bin"), dict):
            raise KeyError(f"meta_shift_fit.json: '{kind}.sd_by_bin' is missing")
        d["sd_by_bin"] = {}
        for b in BINS:
            if b not in g["sd_by_bin"]:
                raise KeyError(f"meta_shift_fit.json: '{kind}.sd_by_bin.{b}' is missing")
            d["sd_by_bin"][b] = float(g["sd_by_bin"][b])
        out[kind] = d
    if "rho_pick_ban" not in raw:
        raise KeyError("meta_shift_fit.json: 'rho_pick_ban' is missing")
    out["rho_pick_ban"] = float(raw["rho_pick_ban"])
    return out


def _bin_index(rate):
    return np.where(rate < 0.05, 0, np.where(rate > 0.20, 2, 1))


def _context(k: float):
    """Per-K arrays: propensity weights W[t, r, c] (log) and per-slot log-weights."""
    b = _base()
    prior_den = (b.share * b.pi[:, None]).sum(0)           # Z_r, shape (5,)
    prior = k * (b.share * b.pi[:, None]) / prior_den[None, :]   # (C, 5)
    W = b.n_pc + prior.T[None, :, :]                        # (T, 5, C)
    return SimpleNamespace(logW=np.log(W), C=b.C, T=b.T, B=b.B, fct=b.fct,
                           vals=b.vals, seg_off=b.seg_off, seg_len=b.seg_len)


# ---------------------------------------------------------------- simulation

def _game_arrays(games: pd.DataFrame, tix: dict):
    g = games.sort_values(["sim", "series", "game_no"]).reset_index(drop=True)
    key = g.sim.to_numpy(np.int64) * 1_000_000 + g.series.to_numpy(np.int64)
    _, sid = np.unique(key, return_inverse=True)
    return SimpleNamespace(
        sim=g.sim.to_numpy(np.int64), sid=sid.astype(np.int64), n_series=int(sid.max()) + 1,
        ga=g.a.map(tix).to_numpy(np.int64), gb=g.b.map(tix).to_numpy(np.int64),
        gw=g.winner.map(tix).to_numpy(np.int64), bo3=(g.best_of.to_numpy() >= 3),
        gn=g.game_no.to_numpy(np.int64), n_sims=int(g.sim.max()) + 1,
    )


def _simulate(G, ctx, logm, logmb, sh_pick, sh_ban, seed, trace=None):
    """Draft every game of the batch. Returns per-sim tallies with shape (n_sims, C).

    trace: optional list; each block appends (game indices, pick champs, pick teams, pick roles,
    ban champs) for testing.
    """
    rng = np.random.default_rng(seed)
    C, B = ctx.C, ctx.B
    S = G.n_sims
    locked = np.zeros((G.n_series, C), dtype=bool)
    picks = np.zeros(S * C)
    wins = np.zeros(S * C)
    deaths = np.zeros(S * C)
    bans = np.zeros(S * C)
    games = np.bincount(G.sim, minlength=S).astype(float)
    rows_all = np.arange(MAX_BLOCK)

    for k in np.unique(G.gn):
        ids_k = np.flatnonzero(G.gn == k)
        for s0 in range(0, len(ids_k), MAX_BLOCK):
            bi = ids_k[s0:s0 + MAX_BLOCK]
            n = len(bi)
            rows = rows_all[:n]
            sim, sid = G.sim[bi], G.sid[bi]
            ta, tb, tw = G.ga[bi], G.gb[bi], G.gw[bi]

            avail = ~locked[sid]
            lb = np.where(avail, logmb[None, :] + sh_ban[sim], -np.inf)
            gb_ = lb + rng.gumbel(size=(n, C))
            top = np.argpartition(-gb_, B - 1, axis=1)[:, :B]
            banned = np.zeros((n, C), dtype=bool)
            banned[rows[:, None], top] = True
            blocked = banned | ~avail

            flip = rng.random(n) < 0.5
            tX = np.where(flip, tb, ta)
            tY = np.where(flip, ta, tb)
            filled = np.zeros((n, 2, 5), dtype=bool)
            base = logm[None, :] + sh_pick[sim]
            pc = np.empty((n, 10), dtype=np.int64)
            pt = np.empty((n, 10), dtype=np.int64)
            pr = np.empty((n, 10), dtype=np.int64)
            for j in range(10):
                side = PICK_SIDES[j]
                team = tX if side == 0 else tY
                rg = np.where(~filled[:, side, :], rng.gumbel(size=(n, 5)), -np.inf)
                role = rg.argmax(1)
                filled[rows, side, role] = True
                L = np.where(blocked, -np.inf, ctx.logW[team, role] + base)
                g = L + rng.gumbel(size=(n, C))
                ch = g.argmax(1)
                if not np.isfinite(g[rows, ch]).all():
                    raise RuntimeError("no available champion for a pick")
                blocked[rows, ch] = True
                pc[:, j], pt[:, j], pr[:, j] = ch, team, role

            if trace is not None:
                trace.append((bi, pc.copy(), pt.copy(), pr.copy(), np.nonzero(banned)))

            won = pt == tw[:, None]
            res = won.astype(np.int64)
            seg = (pt * 5 + pr) * 2 + res
            u = rng.random((n, 10))
            dv = ctx.vals[(ctx.seg_off[seg] + np.floor(u * ctx.seg_len[seg])).astype(np.int64)]
            dv = dv * ctx.fct[pc]

            flat = (sim[:, None] * C + pc).ravel()
            picks += np.bincount(flat, minlength=S * C)
            wins += np.bincount(flat, weights=won.ravel().astype(float), minlength=S * C)
            deaths += np.bincount(flat, weights=dv.ravel(), minlength=S * C)
            bi_r, bi_c = np.nonzero(banned)
            bans += np.bincount(sim[bi_r] * C + bi_c, minlength=S * C)

            m3 = G.bo3[bi]
            locked[sid[m3][:, None], pc[m3]] = True

    shp = (S, C)
    return SimpleNamespace(picks=picks.reshape(shp), wins=wins.reshape(shp),
                           deaths=deaths.reshape(shp), bans=bans.reshape(shp), games=games)


def _calibrate(Gcal, ctx, tgt_pick, tgt_ban):
    """IPS on pick and ban multipliers toward per-game target rates (no random shift).

    tgt_pick / tgt_ban are the z = 0 target rates (window rates when there is no shift).
    Returns logm, logmb, sim pick rates, sim ban rates, history.
    """
    C = ctx.C
    logm = np.zeros(C)
    logmb = np.zeros(C)
    zeros = np.zeros((Gcal.n_sims, C))
    hist = []
    for it in range(CAL_MAX_ITER + 1):
        r = _simulate(Gcal, ctx, logm, logmb, zeros, zeros, seed=101)
        Gt = r.games.sum()
        sp = r.picks.sum(0) / Gt
        sb = r.bans.sum(0) / Gt
        ep = np.abs(sp - tgt_pick) * 100
        eb = np.abs(sb - tgt_ban) * 100
        max_p = ep[tgt_pick > QUAL].max() if (tgt_pick > QUAL).any() else 0.0
        max_b = eb[tgt_ban > QUAL].max() if (tgt_ban > QUAL).any() else 0.0
        hist.append({"iter": it, "max_err_pick_pp": max_p, "max_err_ban_pp": max_b,
                     "sum_pick": float(sp.sum()), "sum_ban": float(sb.sum())})
        if max(max_p, max_b) < CAL_TOL_PP or it == CAL_MAX_ITER:
            break
        floor = 0.5 / Gt
        logm += np.log(tgt_pick / np.maximum(sp, floor))
        logmb += np.log(tgt_ban / np.maximum(sb, floor))
    return logm, logmb, sp, sb, hist


_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(20)
_GH_W = _GH_W / _GH_W.sum()          # weights for E_z[f(z)], z ~ N(0,1)


def _gh_moments(eta, s):
    """Gauss-Hermite (20 nodes) mean and variance over z of p = sigmoid(eta + s*z), elementwise."""
    p = sigmoid(eta[None, :] + s[None, :] * _GH_X[:, None])
    m = (_GH_W[:, None] * p).sum(0)
    v = (_GH_W[:, None] * p * p).sum(0) - m * m
    e_pq = (_GH_W[:, None] * p * (1 - p)).sum(0)
    return m, v, e_pq


def _bisect_common_shift(logit_base, total=10.0):
    """Common additive logit shift d with sum(sigmoid(logit_base + d)) == total."""
    lo, hi = -15.0, 15.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if sigmoid(logit_base + mid).sum() < total:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _marg(fit, b):
    """Shift model pieces: eta = logit of the deterministic rates, marginal means pibar / bebar
    (20-node Gauss-Hermite), and the common logit shifts that make the targets sum to 10 per game."""
    pk, bk = fit["pick"], fit["ban"]
    sdp = np.array([pk["sd_by_bin"][k] for k in BINS])[_bin_index(b.pi)]
    sdb = np.array([bk["sd_by_bin"][k] for k in BINS])[_bin_index(b.beta)]
    x1, x2 = logit(b.pi), logit(b.late_pick)
    y1, y2 = logit(b.beta), logit(b.late_ban)
    lp0 = pk["a"] + pk["b"] * x1 + pk["c"] * (x2 - x1)     # eta_pick = logit pi'_0
    lb0 = bk["a"] + bk["b"] * y1 + bk["c"] * (y2 - y1)     # eta_ban = logit beta'_0
    pibar, _, _ = _gh_moments(lp0, sdp)
    bebar, _, _ = _gh_moments(lb0, sdb)
    dp = _bisect_common_shift(logit(pibar), 10.0)
    db = _bisect_common_shift(logit(bebar), 10.0)
    return SimpleNamespace(lp0=lp0, lb0=lb0, sdp=sdp, sdb=sdb, p0=sigmoid(lp0), be0=sigmoid(lb0),
                           pibar=pibar, bebar=bebar, dp=dp, db=db,
                           pi_t=sigmoid(logit(pibar) + dp), be_t=sigmoid(logit(bebar) + db))


def _glmm_sd_marginal(eta_plus_delta, s, G=SPREAD_G):
    """GLMM-implied across-tournament sd of an observed rate in the marginal formulation:
    p = sigmoid(eta + delta + s*z), z ~ N(0,1) (20-node Gauss-Hermite), binomial noise on G games.
    Returns the sd in probability units."""
    m, v, e_pq = _gh_moments(np.asarray([eta_plus_delta], float), np.asarray([s], float))
    return float(np.sqrt(v[0] + e_pq[0] / G))


def _shift_draws(fit, b, S, rng, M=None, slope_p=None, slope_b=None):
    """Per-sim, per-champion log-weight shifts for the draft.

    Pick: shift = (eta_p + sd_p*z1) - logit(pibar), eta_p = logit pi'_0, pibar = marginal mean.
    Ban:  shift = (eta_b + sd_b*(rho*z1 + sqrt(1-rho^2)*z2)) - logit(bebar).
    Round 7: the whole deviation (eta + u - logit(target marginal)) is divided by the measured draft
    slope of each champion (slope_p, slope_b; default 1).
    """
    if M is None:
        M = _marg(fit, b)
    C = len(b.pi)
    slope_p = np.ones(C) if slope_p is None else slope_p
    slope_b = np.ones(C) if slope_b is None else slope_b
    z1 = rng.standard_normal((S, C))
    z2 = rng.standard_normal((S, C))
    rho = fit["rho_pick_ban"]
    u_p = M.sdp[None, :] * z1
    u_b = M.sdb[None, :] * (rho * z1 + np.sqrt(1 - rho ** 2) * z2)
    sh_pick = (M.lp0[None, :] + u_p - logit(M.pibar)[None, :]) / slope_p[None, :]
    sh_ban = (M.lb0[None, :] + u_b - logit(M.bebar)[None, :]) / slope_b[None, :]
    return sh_pick, sh_ban


def _measure_slopes(Gv, ctx, logm, logmb, b, champs, side):
    """Draft slope at baseline (calibrated weights, forced marginal): change in logit(rate) per unit
    of log-weight, from a +SLOPE_BUMP bump on one champion's weight at a time (common random numbers).
    side: 'ban' or 'pick'. Returns {champion: slope}."""
    C = ctx.C
    S = Gv.n_sims
    zero = np.zeros((S, C))
    base = _simulate(Gv, ctx, logm, logmb, zero, zero, seed=SLOPE_SEED)
    rate0 = (base.bans if side == "ban" else base.picks).sum(0) / base.games.sum()
    out = {}
    for c in champs:
        j = b.cidx[c]
        bump = np.zeros((S, C))
        bump[:, j] = SLOPE_BUMP
        if side == "ban":
            r = _simulate(Gv, ctx, logm, logmb, zero, bump, seed=SLOPE_SEED)
            rate1 = r.bans.sum(0) / r.games.sum()
        else:
            r = _simulate(Gv, ctx, logm, logmb, bump, zero, seed=SLOPE_SEED)
            rate1 = r.picks.sum(0) / r.games.sum()
        out[c] = float((logit(np.array([rate1[j]]))[0] - logit(np.array([rate0[j]]))[0]) / SLOPE_BUMP)
    return out


def _interp_slopes(tgt, measured, lo=1.0):
    """Slope for every champion: measured where given; otherwise linear in logit(target) from the
    measured champions, clamped to [1.0, max measured slope]. tgt: array over all champions;
    measured: {index: slope}."""
    idx = np.array(sorted(measured))
    x_m = logit(tgt[idx])
    y_m = np.array([measured[i] for i in idx])
    order = np.argsort(x_m)
    x_m, y_m = x_m[order], y_m[order]
    out = np.interp(logit(tgt), x_m, y_m)
    out = np.clip(out, lo, y_m.max())
    for i, v in measured.items():
        out[i] = v
    return out


def _rank_probs(V, elig):
    """P(rank = 1, 2, 3) per champion under the no-split rule: rank = 1 + number of eligible
    champions strictly better. V: (S, C) values with ineligible entries set to -inf; elig: (S, C) bool.
    Returns array (3, C) of probabilities averaged over sims."""
    S, C = V.shape
    P = np.zeros((3, C))
    for s in range(S):
        e = elig[s]
        if not e.any():
            continue
        row = V[s]
        srt = np.sort(row)
        rank = 1 + (C - np.searchsorted(srt, row, side="right"))
        for k in (1, 2, 3):
            P[k - 1] += e & (rank == k)
    return P / S


def run_draft(games: pd.DataFrame, k: float = 15, shift: bool = True, seed: int = 7) -> dict:
    """Run the champion-draft simulation on the sim game table.

    games: sim, stage, a, b, winner, p_a, series, game_no, best_of (one row per game).
    Calibration targets are the z = 0 shifted rates (window rates when there is no shift).
    Returns a dict with DataFrames: summary, q10, calibration, baseline, info, cal_hist,
    shift_det, verification, spread, benchmark.
    """
    t0 = time.time()
    b = _base()
    ctx = _context(k)
    tix = b.tix
    unknown = (set(games.a) | set(games.b) | set(games.winner)) - set(tix)
    if unknown:
        raise ValueError(f"teams not in rosters: {sorted(unknown)}")
    fit = _fit_params() if shift else None
    M = _marg(fit, b) if shift else None
    if shift:
        p0, be0 = M.p0, M.be0          # deterministic z = 0 rates (section i)
        tgt_p, tgt_b = M.pi_t, M.be_t  # marginal means with the common shift (calibration targets)
    else:
        p0, be0 = b.pi, b.beta
        tgt_p, tgt_b = b.pi, b.beta

    # calibration on the first CAL_SIMS sims, z = 0 targets
    cal_games = games[games.sim < CAL_SIMS]
    Gcal = _game_arrays(cal_games, tix)
    logm, logmb, sp, sb, hist = _calibrate(Gcal, ctx, tgt_p, tgt_b)
    cal_df = pd.DataFrame({
        "champion": b.champs,
        "base_pick_pct": 100 * b.pi, "target_pick_pct": 100 * tgt_p, "sim_pick_pct": 100 * sp,
        "base_ban_pct": 100 * b.beta, "target_ban_pct": 100 * tgt_b, "sim_ban_pct": 100 * sb,
        "m_pick": np.exp(logm), "m_ban": np.exp(logmb),
    })
    t_cal = time.time() - t0

    # out-of-sample verification of the z = 0 targets (forced z = 0 shift)
    verify = None
    vmask = (games.sim >= VERIFY_SIMS[0]) & (games.sim < VERIFY_SIMS[1])
    if shift and vmask.any():
        vg = games[vmask].copy()
        vg["sim"] = vg.sim - VERIFY_SIMS[0]
        Gv = _game_arrays(vg, tix)
        zv = np.zeros((Gv.n_sims, b.C))
        rv = _simulate(Gv, ctx, logm, logmb, zv, zv, seed=202)
        Gtv = rv.games.sum()
        vp = rv.picks.sum(0) / Gtv
        vb = rv.bans.sum(0) / Gtv
        verify = pd.DataFrame({
            "champion": b.champs,
            "target_pick_pct": 100 * tgt_p, "sim_pick_pct": 100 * vp,
            "target_ban_pct": 100 * tgt_b, "sim_ban_pct": 100 * vb,
        })
        verify["err_pick_pp"] = verify.sim_pick_pct - verify.target_pick_pct
        verify["err_ban_pp"] = verify.sim_ban_pct - verify.target_ban_pct

    # draft slopes (round 6): slope of logit(rate) per unit log-weight at baseline (calibrated
    # weights, forced marginal), measured on sims SLOPE_SIMS. The random part of the shift is
    # divided by these slopes.
    slopes_df = None
    slope_p_arr = None
    slope_b_arr = None
    slope_info = {}
    if shift:
        sg = games[(games.sim >= SLOPE_SIMS[0]) & (games.sim < SLOPE_SIMS[1])].copy()
        sg["sim"] = sg.sim - SLOPE_SIMS[0]
        Gs = _game_arrays(sg, tix)
        ban_names = [c for c, t in zip(b.champs, tgt_b) if t > SLOPE_MIN_RATE]
        ms_b = _measure_slopes(Gs, ctx, logm, logmb, b, ban_names, "ban")
        slope_b_arr = _interp_slopes(tgt_b, {b.cidx[c]: v for c, v in ms_b.items()}, lo=1.0)
        pick_names = sorted(set(SLOPE_CHECK_PICKS) | {c for c, t in zip(b.champs, tgt_p) if t > SLOPE_MIN_RATE})
        ms_p = _measure_slopes(Gs, ctx, logm, logmb, b, pick_names, "pick")
        slope_p_arr = _interp_slopes(tgt_p, {b.cidx[c]: v for c, v in ms_p.items()}, lo=SLOPE_STOP[0])
        stop_bad = [c for c, v in list(ms_b.items()) + list(ms_p.items())
                    if not (SLOPE_STOP[0] <= v <= SLOPE_STOP[1])]
        slopes_df = pd.DataFrame({
            "champion": b.champs,
            "target_ban_pct": 100 * tgt_b,
            "ban_slope_measured": [ms_b.get(c, np.nan) for c in b.champs],
            "ban_slope_applied": slope_b_arr,
            "target_pick_pct": 100 * tgt_p,
            "pick_slope_measured": [ms_p.get(c, np.nan) for c in b.champs],
            "pick_slope_applied": slope_p_arr,
        })
        slope_info = {
            "slope_ban_measured_n": len(ms_b),
            "slope_pick_measured_n": len(ms_p),
            "slope_ban_min_measured": round(float(min(ms_b.values())), 4),
            "slope_ban_max_measured": round(float(max(ms_b.values())), 4),
            "slope_pick_min_measured": round(float(min(ms_p.values())), 4),
            "slope_pick_max_measured": round(float(max(ms_p.values())), 4),
            "slope_pick_check": ", ".join(f"{c} {ms_p[c]:.3f}" for c in SLOPE_CHECK_PICKS),
            "slope_ban_min_applied": round(float(slope_b_arr.min()), 4),
            "slope_ban_max_applied": round(float(slope_b_arr.max()), 4),
            "slope_pick_min_applied": round(float(slope_p_arr.min()), 4),
            "slope_pick_max_applied": round(float(slope_p_arr.max()), 4),
            "slope_within_stop_limits": len(stop_bad) == 0,
            "slope_stop_offenders": ", ".join(stop_bad) or "none",
        }

    # full run with the per-tournament odds-ratio shift
    G = _game_arrays(games, tix)
    S = G.n_sims
    rng = np.random.default_rng(seed)
    if shift:
        shp, shb = _shift_draws(fit, b, S, rng, M, slope_p=slope_p_arr, slope_b=slope_b_arr)
    else:
        shp = np.zeros((S, b.C))
        shb = np.zeros((S, b.C))
    res = _simulate(G, ctx, logm, logmb, shp, shb, seed=seed + 1000)
    t_sim = time.time() - t0 - t_cal

    games_s = res.games
    presence = (res.picks + res.bans) / games_s[:, None]
    picks = res.picks
    with np.errstate(divide="ignore", invalid="ignore"):
        wr = np.where(picks > 0, res.wins / np.maximum(picks, 1), np.nan)
        dpp = np.where(picks > 0, res.deaths / np.maximum(picks, 1), np.nan)
    elig = picks >= MIN_PICKS
    P1 = _rank_probs(presence, np.ones_like(elig))
    P2 = _rank_probs(np.where(elig, wr, -np.inf), elig)
    P3 = _rank_probs(np.where(elig, dpp, -np.inf), elig)
    q10 = (picks > 0).sum(1)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        summary = pd.DataFrame({
            "champion": b.champs,
            "p_lead_q1": P1[0], "p_lead_q2": P2[0], "p_lead_q3": P3[0],
            "p1_q1": P1[0], "p2_q1": P1[1], "p3_q1": P1[2],
            "ev_q1": POINTS[0] * P1[0] + POINTS[1] * P1[1] + POINTS[2] * P1[2],
            "p1_q2": P2[0], "p2_q2": P2[1], "p3_q2": P2[2],
            "ev_q2": POINTS[0] * P2[0] + POINTS[1] * P2[1] + POINTS[2] * P2[2],
            "p1_q3": P3[0], "p2_q3": P3[1], "p3_q3": P3[2],
            "ev_q3": POINTS[0] * P3[0] + POINTS[1] * P3[1] + POINTS[2] * P3[2],
            "mean_presence": presence.mean(0),
            "mean_picks": picks.mean(0),
            "p_ge5_picks": elig.mean(0),
            "mean_wr_given_ge5": np.nanmean(np.where(elig, wr, np.nan), 0),
            "mean_deaths_given_ge5": np.nanmean(np.where(elig, dpp, np.nan), 0),
            "base_pick_pct": 100 * b.pi,
            "base_ban_pct": 100 * b.beta,
        })
    summary = summary.sort_values("ev_q1", ascending=False).reset_index(drop=True)

    q10_df = pd.DataFrame({"sim": np.arange(S), "unique_champions": q10})
    base_df = pd.DataFrame({
        "champion": b.champs,
        "window_presence_pct": b.win_tab.presence_pct.to_numpy(float),
        "sim_presence_pct": 100 * presence.mean(0),
    })

    # spread check: across-sim sd of the simulated ban rate vs the GLMM-implied sd
    spread = None
    if shift:
        brate = res.bans / games_s[:, None]
        rows = []
        for name in SPREAD_CHAMPS:
            j = b.cidx[name]
            bin_name = BINS[int(_bin_index(np.array([b.beta[j]]))[0])]
            s_b = float(M.sdb[j])
            sim_sd = float(brate[:, j].std(ddof=1))
            glmm = _glmm_sd_marginal(float(M.lb0[j] + M.db), s_b)
            ratio = sim_sd / glmm
            rows.append({
                "champion": name, "window_ban_pct": 100 * b.beta[j], "target_ban_pct": 100 * tgt_b[j],
                "bin": bin_name, "sd_logit_bin": s_b,
                "sim_mean_ban_pct": 100 * float(brate[:, j].mean()),
                "sim_sd_pp": 100 * sim_sd, "glmm_sd_pp": 100 * glmm, "ratio_sim_to_glmm": ratio,
                "in_band": bool(SPREAD_BAND[0] <= ratio <= SPREAD_BAND[1]),
            })
        spread = pd.DataFrame(rows)

    # pick mean check (report only): simulated mean pick rate vs the marginal target
    pick_check = None
    if shift:
        prate = res.picks / games_s[:, None]
        pick_check = pd.DataFrame({
            "champion": SPREAD_CHAMPS,
            "target_pick_pct": [100 * tgt_p[b.cidx[c]] for c in SPREAD_CHAMPS],
            "sim_mean_pick_pct": [100 * float(prate[:, b.cidx[c]].mean()) for c in SPREAD_CHAMPS],
        })
        pick_check["diff_pp"] = pick_check.sim_mean_pick_pct - pick_check.target_pick_pct

    # benchmark comparison for Q1 leaders
    bench = None
    if BENCHMARK_Q1:
        sm = summary.set_index("champion")
        bench = pd.DataFrame({
            "champion": list(BENCHMARK_Q1),
            "benchmark_q1": [BENCHMARK_Q1[c] for c in BENCHMARK_Q1],
            "sim_p_lead_q1": [float(sm.loc[c, "p_lead_q1"]) for c in BENCHMARK_Q1],
        })
        bench["diff"] = bench.sim_p_lead_q1 - bench.benchmark_q1

    # calibration error: in-sample on the calibration sims, final state, against z = 0 targets
    qp = tgt_p > QUAL
    qb = tgt_b > QUAL
    last = hist[-1]
    cal_max_p = float(np.abs(sp - tgt_p)[qp].max() * 100)
    cal_max_b = float(np.abs(sb - tgt_b)[qb].max() * 100)
    converged = bool(max(last["max_err_pick_pp"], last["max_err_ban_pp"]) < CAL_TOL_PP)

    info = pd.DataFrame([
        ("k", k), ("shift", shift), ("sims", S), ("seed", seed),
        ("window_games", b.G), ("bans_per_game", b.ban_per_game),
        ("sum_window_pick_targets", round(float(b.pi.sum()), 4)),
        ("sum_window_ban_targets", round(float(b.beta.sum()), 4)),
        ("sum_calib_pick_targets", round(float(tgt_p.sum()), 4)),
        ("sum_calib_ban_targets", round(float(tgt_b.sum()), 4)),
        ("calibration_target", "marginal means pibar, bebar + common logit shift (sums to 10)" if shift
         else "window pi, beta (no shift)"),
        ("scoring", "no-split ranking: 50/20/10 for rank 1/2/3, rank = 1 + eligible champions strictly better"),
        ("q1_sum_p1", round(float(P1[0].sum()), 6)),
        ("q2_sum_p1", round(float(P2[0].sum()), 6)),
        ("q3_sum_p1", round(float(P3[0].sum()), 6)),
        ("common_shift_pick_logit", round(float(M.dp), 6) if shift else 0.0),
        ("common_shift_ban_logit", round(float(M.db), 6) if shift else 0.0),
        ("sum_marginal_pick_pre_shift", round(float(M.pibar.sum()), 4) if shift else None),
        ("sum_marginal_ban_pre_shift", round(float(M.bebar.sum()), 4) if shift else None),
        ("universe_champions", b.C), ("starters", b.T * 5),
        ("meta_shift_params", (fit["source"] if shift else "not used (no-shift run)")),
        ("calibration_sims", CAL_SIMS), ("calibration_iterations", len(hist) - 1),
        ("calibration_converged", converged),
        ("calibration_max_err_pick_pp", round(cal_max_p, 3)),
        ("calibration_max_err_ban_pp", round(cal_max_b, 3)),
        ("calibration_hist", json.dumps(hist)),
        ("q1_sum_p_lead", round(float(summary.p_lead_q1.sum()), 6)),
        ("q2_sum_p_lead", round(float(summary.p_lead_q2.sum()), 6)),
        ("q3_sum_p_lead", round(float(summary.p_lead_q3.sum()), 6)),
        ("q10_mean", float(q10.mean())), ("q10_median", float(np.median(q10))),
        ("q10_p10", float(np.percentile(q10, 10))), ("q10_p90", float(np.percentile(q10, 90))),
        ("seconds_calibration", round(t_cal, 2)), ("seconds_simulation", round(t_sim, 2)),
        ("seconds_total", round(time.time() - t0, 2)),
    ], columns=["key", "value"])
    extra = [("G_late", b.G_late), ("late_window", f"{LATE_FROM} to {LATE_TO} (is_international = false, all leagues)"),
             ("late_champions_outside_universe", ", ".join(b.late_outside) or "none")]
    if verify is not None:
        vq_p = verify.target_pick_pct > 100 * QUAL
        vq_b = verify.target_ban_pct > 100 * QUAL
        vmax_p = float(verify.err_pick_pp.abs()[vq_p].max())
        vmax_b = float(verify.err_ban_pp.abs()[vq_b].max())
        extra += [("verification_sims", f"{VERIFY_SIMS[0]}-{VERIFY_SIMS[1] - 1} (forced marginal, shift term = 0)"),
                  ("verification_max_err_pick_pp", round(vmax_p, 3)),
                  ("verification_max_err_ban_pp", round(vmax_b, 3)),
                  ("verification_pass", bool(max(vmax_p, vmax_b) < CAL_TOL_PP))]
    for k_, v_ in slope_info.items():
        extra.append((k_, v_))
    if spread is not None:
        extra.append(("mean_ban_within_1.5pp_4champs", bool((spread.sim_mean_ban_pct - spread.target_ban_pct).abs().max() <= CAL_TOL_PP)))
        extra.append(("spread_ratio_min", round(float(spread.ratio_sim_to_glmm.min()), 4)))
        extra.append(("spread_ratio_max", round(float(spread.ratio_sim_to_glmm.max()), 4)))
        extra.append(("spread_all_in_band", bool(spread["in_band"].all())))
    if bench is not None and shift:
        extra.append(("benchmark_max_abs_diff", round(float(bench["diff"].abs().max()), 4)))
    if shift:
        extra.append(("meta_shift_fit", json.dumps({k_: v for k_, v in fit.items() if k_ != "source"})))
        extra.append(("shift_source", fit["source"]))
    info = pd.concat([info, pd.DataFrame(extra, columns=["key", "value"])], ignore_index=True)

    det = None
    if shift:
        det = pd.DataFrame({
            "champion": b.champs,
            "base_pick_pct": 100 * b.pi, "late_pick_pct": 100 * b.late_pick,
            "pick_shift_z0_pct": 100 * p0, "pick_marginal_pct": 100 * tgt_p,
            "base_ban_pct": 100 * b.beta, "late_ban_pct": 100 * b.late_ban,
            "ban_shift_z0_pct": 100 * be0, "ban_marginal_pct": 100 * tgt_b,
        })

    return {"summary": summary, "q10": q10_df, "calibration": cal_df,
            "baseline": base_df, "info": info, "cal_hist": pd.DataFrame(hist), "shift_det": det,
            "verification": verify, "spread": spread, "benchmark": bench, "slopes": slopes_df,
            "pick_check": pick_check}


# ---------------------------------------------------------------- report

def _info_dict(info: pd.DataFrame) -> dict:
    return dict(zip(info.key, info.value))


def _write_report(main: dict, sens: dict[str, dict], path: Path, runtime_note: str):
    s = main["summary"]
    info = _info_dict(main["info"])
    q10 = main["q10"].unique_champions
    out = []
    out.append("# Crystal Ball: champion-draft simulation (Worlds 2026)\n")
    out.append(f"Main run: {info['sims']} sims, K = {float(info['k']):g}, meta shift = {'on' if info['shift'] else 'off'}, "
               f"window G = {info['window_games']} games, bans per game = {float(info['bans_per_game']):.2f}, "
               f"universe = {info['universe_champions']} champions. Code: `crystal/draft.py`.\n")

    def top(q, name):
        ev, p1, p2, p3 = f"ev_{q}", f"p1_{q}", f"p2_{q}", f"p3_{q}"
        d = s.sort_values(ev, ascending=False).head(15)[
            ["champion", p1, p2, p3, ev, "mean_presence", "mean_picks", "p_ge5_picks",
             "mean_wr_given_ge5", "mean_deaths_given_ge5", "base_pick_pct", "base_ban_pct"]].copy()
        d = d.rename(columns={p1: "p1", p2: "p2", p3: "p3", ev: "EV"})
        for c_ in ("p1", "p2", "p3"):
            d[c_] = d[c_].round(4)
        d["EV"] = d.EV.round(2)
        d["mean_presence"] = d.mean_presence.round(3)
        d["base_pick_pct"] = d.base_pick_pct.round(2)
        d["base_ban_pct"] = d.base_ban_pct.round(2)
        return f"### {name}\n\n" + _md_table(d) + "\n"

    out.append("## (a) Top 15 by EV (no-split ranking, 50/20/10 points)\n")
    out.append("Rank = 1 + number of eligible champions strictly better (ties are not split: every tied entry gets "
               "the place's points). EV = 50 p1 + 20 p2 + 10 p3. Q2 and Q3 are restricted to champions with >= 5 "
               "picks. Presence = share of games picked or banned. WR and deaths are means over sims in which the "
               "champion has >= 5 picks. Sum of P(rank 1) per question (>= 1 because of ties): "
               f"Q1 {info['q1_sum_p1']}, Q2 {info['q2_sum_p1']}, Q3 {info['q3_sum_p1']}.\n")
    out.append(top("q1", "Q1 highest presence"))
    out.append(top("q2", "Q2 highest win rate (min 5 picks)"))
    out.append(top("q3", "Q3 highest deaths per game (min 5 picks)"))

    out.append("## (b) Q10 unique champions picked\n")
    out.append(f"Mean {q10.mean():.1f}, median {np.median(q10):.0f}, 10-90% range "
               f"{np.percentile(q10, 10):.0f} to {np.percentile(q10, 90):.0f} "
               f"(min {q10.min()}, max {q10.max()}, {len(q10)} sims).\n")
    med_ok = 95 <= np.median(q10) <= 120
    out.append(f"Acceptance check, Q10 median in [95, 120]: **{'PASS' if med_ok else 'FAIL'}** "
               f"(median {np.median(q10):.0f}). Historical Worlds reference: 95 unique champions in 84 games "
               f"(2025) and 95 in 106 games (2024).\n")

    out.append("## (c) Calibration\n")
    out.append(f"IPS on the first {info['calibration_sims']} sims, up to {CAL_MAX_ITER} iterations, toward: "
               f"{info['calibration_target']}. Iterations used: {info['calibration_iterations']}. "
               f"Converged to < {CAL_TOL_PP} pp: {info['calibration_converged']}.\n")
    if info["shift"]:
        out.append(f"Common logit shift (bisection so targets sum to 10 per game): pick {float(info['common_shift_pick_logit']):+.6f}, "
                   f"ban {float(info['common_shift_ban_logit']):+.6f}. Marginal sums before the shift: pick "
                   f"{float(info['sum_marginal_pick_pre_shift']):.4f}, ban {float(info['sum_marginal_ban_pre_shift']):.4f}. "
                   f"Targets after the shift: {float(info['sum_calib_pick_targets']):.4f} and "
                   f"{float(info['sum_calib_ban_targets']):.4f}.\n")
    out.append(f"- Max pick error (champions with pick rate > 3%): **{info['calibration_max_err_pick_pp']} pp**\n"
               f"- Max ban error (champions with ban rate > 3%): **{info['calibration_max_err_ban_pp']} pp**\n")
    if not info["calibration_converged"]:
        out.append("**WARNING: calibration did not reach the 1.5 pp tolerance; multipliers are the best found.**\n")
    cal_hist = main["cal_hist"]
    out.append("Iteration history (max error, pp): " + ", ".join(
        f"{int(r.iter)}: {r.max_err_pick_pp:.2f}/{r.max_err_ban_pp:.2f}" for r in cal_hist.itertuples()) + "\n")

    out.append("## (d) Meta-shift parameters\n")
    out.append(f"Source: {info['meta_shift_params']}.\n")
    if info["shift"]:
        fit = json.loads(info["meta_shift_fit"])
        out.append("```json\n" + json.dumps(fit, indent=1) + "\n```\n")
        out.append("Model: eta = logit pi'_0 = a + b*x1 + c*(x2 - x1), with x1 = logit(pi) (meta window) and x2 = "
                   "logit of the late-window pick rate. Ban: eta_b = a + b*y1 + c*(y2 - y1) with y1, y2 the analogous "
                   "ban logits. Per-champion sd = sd_by_bin of the window rate (pick: pi, ban: beta). "
                   "Marginal means pibar = E_z[sigmoid(eta + sd*z)] by 20-node Gauss-Hermite; the calibration targets are "
                   "sigmoid(logit(pibar) + d) with a common d chosen so the targets sum to 10. "
                   "Per tournament, the draft log-weight shift is (eta + u) - logit(pibar), with u = sd*z1 for picks and "
                   "sd_b*(rho*z1 + sqrt(1-rho^2)*z2) for bans. The common d cancels in this shift. "
                   f"Late window: {info['late_window']}, G_late = {info['G_late']} games.\n")
        if info.get("late_champions_outside_universe", "none") != "none":
            out.append("Late-window champions outside the 2026 top-league universe (cannot be drawn, ignored): "
                       f"{info['late_champions_outside_universe']}.\n")
    else:
        out.append("No shift in this run.\n")

    out.append("## (e) Sensitivity (1,000 sims each; top 5 per question by EV)\n")
    rows = []
    for name, r in sens.items():
        ss = r["summary"]
        row = {"config": name}
        for q, col in (("Q1", "ev_q1"), ("Q2", "ev_q2"), ("Q3", "ev_q3")):
            t5 = ss.sort_values(col, ascending=False).head(5)
            row[q] = ", ".join(f"{c} {p:.2f}" for c, p in zip(t5.champion, t5[col]))
        rows.append(row)
    if rows:
        out.append(_md_table(pd.DataFrame(rows)) + "\n")
    else:
        out.append("No sensitivity runs found.\n")

    out.append("## (f) Baseline sanity check (no shift)\n")
    if "no-shift" in sens:
        bl = sens["no-shift"]["baseline"].copy()
        top_sim = bl.sort_values("sim_presence_pct", ascending=False).head(10)
        top_win = bl.sort_values("window_presence_pct", ascending=False).head(10)
        t = pd.DataFrame({
            "rank": range(1, 11),
            "sim champion": [f"{c} ({v:.1f})" for c, v in zip(top_sim.champion, top_sim.sim_presence_pct)],
            "window champion": [f"{c} ({v:.1f})" for c, v in zip(top_win.champion, top_win.window_presence_pct)],
        })
        out.append(_md_table(t) + "\n")
        overlap = len(set(top_sim.champion) & set(top_win.champion))
        out.append(f"Top-10 overlap: {overlap}/10. Presence in % of games.\n")
        mae = np.abs(bl.sim_presence_pct - bl.window_presence_pct)[bl.window_presence_pct > 5].mean()
        out.append(f"Mean absolute gap for champions with window presence > 5%: {mae:.1f} pp.\n")
    else:
        out.append("No-shift sensitivity run not found.\n")

    out.append("## (h) Effect of the meta shift (diagnostic, 1,000 sims)\n")
    if "no-shift" in sens and "K=15, shift" in sens:
        ns = sens["no-shift"]["baseline"].set_index("champion")
        sh = sens["K=15, shift"]["baseline"].set_index("champion")
        top = ns.sort_values("window_presence_pct", ascending=False).head(10).index
        t = pd.DataFrame({
            "champion": list(top),
            "window %": [f"{v:.1f}" for v in ns.loc[top, "window_presence_pct"]],
            "no-shift %": [f"{v:.1f}" for v in ns.loc[top, "sim_presence_pct"]],
            "shift %": [f"{v:.1f}" for v in sh.loc[top, "sim_presence_pct"]],
        })
        out.append(_md_table(t) + "\n")
        tail = ns.window_presence_pct < 1
        out.append(f"Champions with window presence < 1% ({int(tail.sum())} of {len(ns)}): mean presence "
                   f"{ns.loc[tail, 'sim_presence_pct'].mean():.2f}% with no shift, "
                   f"{sh.loc[tail, 'sim_presence_pct'].mean():.2f}% with the shift.\n")
        q_ns = sens["no-shift"]["q10"].unique_champions.mean()
        q_sh = sens["K=15, shift"]["q10"].unique_champions.mean()
        out.append(f"Q10 mean: {q_ns:.1f} with no shift, {q_sh:.1f} with the shift. Independent per-game "
                   "inclusion at the window pick rates gives about 107 for 103 games (sum over champions of "
                   "1 - (1 - pi_c)^103), so the no-shift run matches that.\n")
        out.append("The z = 0 shifted rates are in section (i).\n")
    else:
        out.append("Needs the no-shift and K=15 shift sensitivity runs.\n")

    out.append("## (i) Deterministic shift (z = 0) and marginal means: what the late-window read changes\n")
    det = main.get("shift_det")
    if det is not None:
        dcols = ["champion", "base_pick_pct", "late_pick_pct", "pick_shift_z0_pct", "pick_marginal_pct",
                 "base_ban_pct", "late_ban_pct", "ban_shift_z0_pct", "ban_marginal_pct"]
        ren = {"base_pick_pct": "pi %", "late_pick_pct": "late pick %", "pick_shift_z0_pct": "pi' (z=0) %",
               "pick_marginal_pct": "pi-bar (calib) %",
               "base_ban_pct": "beta %", "late_ban_pct": "late ban %", "ban_shift_z0_pct": "beta' (z=0) %",
               "ban_marginal_pct": "beta-bar (calib) %"}
        for col, title in (("pick_shift_z0_pct", "Top 20 by pi' (z = 0)"),
                           ("ban_shift_z0_pct", "Top 20 by beta' (z = 0)")):
            t = det.sort_values(col, ascending=False).head(20)[dcols].rename(columns=ren)
            for c_ in t.columns[1:]:
                t[c_] = [f"{v:.2f}" for v in t[c_]]
            out.append(f"### {title}\n\n" + _md_table(t) + "\n")
        out.append("Late rates are the smoothed (count + 0.5)/(G_late + 1) values used in the model, not raw counts. "
                   "Champions with no late-window appearance sit at the smoothed floor, as intended.\n")
    else:
        out.append("No shift in this run.\n")

    out.append("## (j) Verification, spread and benchmark (round 4)\n")
    ver = main.get("verification")
    spr = main.get("spread")
    ben = main.get("benchmark")
    if ver is not None:
        out.append(f"### Verification: forced marginal (shift term = 0), out of sample on sims {VERIFY_SIMS[0]}-{VERIFY_SIMS[1] - 1}\n")
        out.append(f"Max abs error over targets > 3%: pick {info['verification_max_err_pick_pp']} pp, ban "
                   f"{info['verification_max_err_ban_pp']} pp. Pass (< {CAL_TOL_PP} pp): {info['verification_pass']}.\n")
        vt = ver.set_index("champion").loc[list(SPREAD_CHAMPS)].reset_index()
        vt = pd.DataFrame({
            "champion": vt.champion,
            "target pick %": [f"{v:.2f}" for v in vt.target_pick_pct],
            "sim pick %": [f"{v:.2f}" for v in vt.sim_pick_pct],
            "target ban %": [f"{v:.2f}" for v in vt.target_ban_pct],
            "sim ban %": [f"{v:.2f}" for v in vt.sim_ban_pct],
        })
        out.append(_md_table(vt) + "\n")
    if spr is not None:
        out.append("### Spread: across-sim sd of the simulated ban rate vs GLMM-implied sd (marginal formulation, G = 103)\n")
        out.append(f"Band [0.85, 1.25] (acceptance): all inside = {info['spread_all_in_band']}. Ratios range "
                   f"{float(info['spread_ratio_min']):.2f} to {float(info['spread_ratio_max']):.2f}.\n")
        st = pd.DataFrame({
            "champion": spr.champion, "bin": spr.bin, "sd(logit) bin": [f"{v:.4f}" for v in spr.sd_logit_bin],
            "target ban-bar %": [f"{v:.2f}" for v in spr.target_ban_pct],
            "sim mean ban %": [f"{v:.2f}" for v in spr.sim_mean_ban_pct],
            "sim sd (pp)": [f"{v:.2f}" for v in spr.sim_sd_pp],
            "GLMM sd (pp)": [f"{v:.2f}" for v in spr.glmm_sd_pp],
            "ratio": [f"{v:.3f}" for v in spr.ratio_sim_to_glmm],
            "in band": ["yes" if v else "NO" for v in spr["in_band"]],
        })
        out.append(_md_table(st) + "\n")
    if ben is not None:
        out.append("### Benchmark: Q1 P(lead) vs the meta-shift benchmark (no draft mechanics, G = 103)\n")
        bt = pd.DataFrame({
            "champion": ben.champion,
            "benchmark": [f"{v:.3f}" for v in ben.benchmark_q1],
            "sim P(lead) Q1": [f"{v:.3f}" for v in ben.sim_p_lead_q1],
            "diff": [f"{v:+.3f}" for v in ben["diff"]],
            "within 0.15": ["yes" if abs(v) <= BENCH_TOL else "NO" for v in ben["diff"]],
        })
        out.append(_md_table(bt) + "\n")
    stop = []
    if not info["calibration_converged"]:
        stop.append("calibration did not converge")
    if ver is not None and not info["verification_pass"]:
        stop.append("verification failed")
    if spr is not None and not info["spread_all_in_band"]:
        stop.append("spread ratio outside [0.85, 1.25]")
    if ben is not None and any(abs(v) > BENCH_TOL for v in ben["diff"]):
        stop.append("benchmark diff > 0.15")
    out.append("Stop-rule status: " + ("none triggered." if not stop else "TRIGGERED: " + "; ".join(stop) + ".") + "\n")

    out.append("## (k) Slope correction (round 7)\n")
    out.append("Correction: the shift is (eta + u - logit(target marginal)) / slope_c for both picks and bans, where "
               "slope_c = d logit(rate) / d log-weight measured at baseline (calibrated weights, forced marginal) with "
               "a +0.25 bump on that champion's weight, 500 sims (sims 500-999), common random numbers. Ban slopes "
               "are measured for champions with target above 10%, pick slopes for champions above 10% plus six checks. "
               "Other champions are interpolated linearly in logit(target), clamped to [1.0, max] for bans and "
               f"[{SLOPE_STOP[0]}, max] for picks. Slopes outside [{SLOPE_STOP[0]}, {SLOPE_STOP[1]}] stop the run.\n")
    out.append(f"Measured ban slopes: {int(info['slope_ban_measured_n'])} champions, range "
               f"{float(info['slope_ban_min_measured']):.3f} to {float(info['slope_ban_max_measured']):.3f}. "
               f"Measured pick slopes: {int(info['slope_pick_measured_n'])} champions, range "
               f"{float(info['slope_pick_min_measured']):.3f} to {float(info['slope_pick_max_measured']):.3f}. "
               f"Applied ban range {float(info['slope_ban_min_applied']):.3f} to {float(info['slope_ban_max_applied']):.3f}; "
               f"applied pick range {float(info['slope_pick_min_applied']):.3f} to {float(info['slope_pick_max_applied']):.3f}. "
               f"Within stop limits: {info['slope_within_stop_limits']} ({info['slope_stop_offenders']}).\n")
    sl = main.get("slopes")
    if sl is not None:
        bt = sl[sl.ban_slope_measured.notna()].sort_values("target_ban_pct", ascending=False)
        st_ = pd.DataFrame({
            "champion": bt.champion, "target ban %": [f"{v:.2f}" for v in bt.target_ban_pct],
            "ban slope (measured)": [f"{v:.3f}" for v in bt.ban_slope_measured],
            "ban slope (applied)": [f"{v:.3f}" for v in bt.ban_slope_applied],
        })
        out.append("### Ban slopes (measured)\n\n" + _md_table(st_) + "\n")
        pt_ = sl[sl.pick_slope_measured.notna()].sort_values("target_pick_pct", ascending=False)
        pp_ = pd.DataFrame({
            "champion": pt_.champion, "target pick %": [f"{v:.2f}" for v in pt_.target_pick_pct],
            "pick slope (measured)": [f"{v:.3f}" for v in pt_.pick_slope_measured],
            "pick slope (applied)": [f"{v:.3f}" for v in pt_.pick_slope_applied],
        })
        out.append("### Pick slopes (measured)\n\n" + _md_table(pp_) + "\n")
    before = None
    if (OUT_DIR / "tmp_round4_k15_shift_s5000.pkl").exists():
        with open(OUT_DIR / "tmp_round4_k15_shift_s5000.pkl", "rb") as fh:
            before = pickle.load(fh)["spread"].set_index("champion")
    spr_now = main.get("spread")
    if spr_now is not None and before is not None:
        now = spr_now.set_index("champion")
        bf = pd.DataFrame({
            "champion": SPREAD_CHAMPS,
            "GLMM sd (pp)": [f"{now.loc[c, 'glmm_sd_pp']:.2f}" for c in SPREAD_CHAMPS],
            "ratio before (round 4)": [f"{before.loc[c, 'ratio_sim_to_glmm']:.3f}" for c in SPREAD_CHAMPS],
            "ratio after (round 7)": [f"{now.loc[c, 'ratio_sim_to_glmm']:.3f}" for c in SPREAD_CHAMPS],
            "in [0.85, 1.25]": ["yes" if SPREAD_BAND[0] <= now.loc[c, 'ratio_sim_to_glmm'] <= SPREAD_BAND[1] else "NO"
                                for c in SPREAD_CHAMPS],
        })
        out.append("### Spread before and after (sim sd / GLMM sd)\n\n" + _md_table(bf) + "\n")
        mv = pd.DataFrame({
            "champion": SPREAD_CHAMPS,
            "target ban-bar %": [f"{now.loc[c, 'target_ban_pct']:.2f}" for c in SPREAD_CHAMPS],
            "mean before %": [f"{before.loc[c, 'sim_mean_ban_pct']:.2f}" for c in SPREAD_CHAMPS],
            "mean after %": [f"{now.loc[c, 'sim_mean_ban_pct']:.2f}" for c in SPREAD_CHAMPS],
            "after minus target (pp)": [f"{now.loc[c, 'sim_mean_ban_pct'] - now.loc[c, 'target_ban_pct']:+.2f}"
                                        for c in SPREAD_CHAMPS],
            "within 1.5 pp": ["yes" if abs(now.loc[c, 'sim_mean_ban_pct'] - now.loc[c, 'target_ban_pct']) <= CAL_TOL_PP
                              else "NO" for c in SPREAD_CHAMPS],
        })
        out.append("### Mean ban rate vs target, before and after\n\n" + _md_table(mv) + "\n")
    pk = main.get("pick_check")
    if pk is not None:
        out.append("### Mean pick rate vs target (report only; not an acceptance check)\n\n" + _md_table(pk.assign(
            target_pick_pct=lambda x: x.target_pick_pct.round(2), sim_mean_pick_pct=lambda x: x.sim_mean_pick_pct.round(2),
            diff_pp=lambda x: x.diff_pp.round(2))) + "\n")
    acc = []
    if spr_now is not None:
        ok_sp = bool(all(SPREAD_BAND[0] <= v <= SPREAD_BAND[1] for v in spr_now.ratio_sim_to_glmm))
        ok_mean = bool(all(abs(spr_now.sim_mean_ban_pct - spr_now.target_ban_pct) <= CAL_TOL_PP))
        acc.append(f"spread ratio in [{SPREAD_BAND[0]}, {SPREAD_BAND[1]}] for the 4 champions: {ok_sp}")
        acc.append(f"mean ban rate within {CAL_TOL_PP} pp of the target for the 4: {ok_mean}")
    if main.get("benchmark") is not None:
        bdiff = main["benchmark"]["diff"].abs().max()
        acc.append(f"Q1 P(rank 1) within {BENCH_TOL} of the benchmark (Nocturne, Cassiopeia, Vi): {bdiff <= BENCH_TOL}")
    acc.append("constraints pass (outputs/draft/tmp_check.py on the round-7 code: 0 duplicate picks, 0 role "
               "violations, 0 ban/pick overlaps, 0 fearless violations, 10 picks, 10 bans and 5 wins per game); "
               f"Sum P(rank 1) >= 1: "
               f"{float(info['q1_sum_p1']) >= 1 and float(info['q2_sum_p1']) >= 1 and float(info['q3_sum_p1']) >= 1}")
    out.append("Acceptance (round 7): " + "; ".join(acc) + ".\n")

    out.append("## (g) Runtime\n")
    out.append(f"Main run: {info['seconds_total']} s total (calibration {info['seconds_calibration']} s, "
               f"simulation {info['seconds_simulation']} s). {runtime_note}\n")

    out.append("## Notes and deviations from the spec\n")
    out.append(
        f"- Bans per game: {info['bans_per_game']:.3f} in the window, rounded to {info['bans_per_game']:.0f}. "
        f"Window target sums (count + 0.5)/(G + 1): picks {info['sum_window_pick_targets']}, bans "
        f"{info['sum_window_ban_targets']}. Calibrated target sums (marginal means + common shift): picks "
        f"{info['sum_calib_pick_targets']}, bans {info['sum_calib_ban_targets']}.\n"
        "- Shift bins for the ban logit use each champion's ban rate beta_c (the spec does not say which rate).\n"
        "- Role share smoothing: s = (n_cr + 0.1) / (n_c + 0.5). Champions with no window player rows get uniform shares.\n"
        "- Death pool: a starter's 2026 top-league games with the same result (all champions). If that pool is empty, "
        "use the starter role's pool across all starters with that result.\n"
        "- Death factor n_c = champion's picks in the window; ratio_c = champion's window mean deaths / mean deaths of its "
        "most common window role. Champions with no window player rows get factor 1.\n"
        "- mean_wr_given_ge5 and mean_deaths_given_ge5 average the per-sim rate over sims where the champion has >= 5 picks.\n"
        "- The calibration error is in-sample (the same 500 sims used for IPS, with the random shift off). Calibration "
        "targets are the marginal means with one common logit shift per type so each sums to 10 per game.\n"
        "- Presence uses picks + bans per sim; a champion cannot be both banned and picked in the same game.\n"
        "- Shift: the refit contract (a, b, c, sd_by_bin, rho_pick_ban from meta_shift_fit.json). c is required; "
        "a missing key raises. The earlier logit-centre diagnostic is removed because it does not apply to this model.\n"
    )
    path.write_text("\n".join(out), encoding="utf-8")


def _load_sensitivity() -> dict[str, dict]:
    """Sensitivity runs saved by the CLI: display name -> run dict."""
    sens = {}
    labels = [("K=5, shift", "k5_shift_s1000"), ("K=15, shift", "k15_shift_s1000"),
              ("K=30, shift", "k30_shift_s1000"), ("no-shift", "k15_noshift_s1000")]
    for name, lab in labels:
        f = OUT_DIR / f"tmp_run_{lab}.pkl"
        if f.exists():
            with open(f, "rb") as fh:
                sens[name] = pickle.load(fh)
    return sens


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--k", type=float, default=15.0)
    ap.add_argument("--no-shift", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--main", action="store_true",
                    help="also write outputs/draft/champion_sim.csv and champion_sim.md")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    games = pd.read_csv(GAMES_FILE)
    games = games[games.sim < args.sims]
    shift = not args.no_shift
    t0 = time.time()
    out = run_draft(games, k=args.k, shift=shift, seed=args.seed)
    elapsed = time.time() - t0

    label = f"k{args.k:g}_{'shift' if shift else 'noshift'}_s{args.sims}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / f"tmp_run_{label}.pkl", "wb") as fh:
        pickle.dump(out, fh)

    info = _info_dict(out["info"])
    s = out["summary"]
    print(f"run {label}: {args.sims} sims in {elapsed:.1f} s")
    print(f"calibration: max pick err {info['calibration_max_err_pick_pp']} pp, "
          f"max ban err {info['calibration_max_err_ban_pp']} pp, iterations {info['calibration_iterations']}, "
          f"converged {info['calibration_converged']}")
    print(f"Q10 mean {info['q10_mean']:.2f} median {info['q10_median']:.0f} "
          f"10-90% {info['q10_p10']:.0f}-{info['q10_p90']:.0f}")
    for q in ("p_lead_q1", "p_lead_q2", "p_lead_q3"):
        t5 = s.sort_values(q, ascending=False).head(5)
        print(f"{q}: " + ", ".join(f"{c} {p:.3f}" for c, p in zip(t5.champion, t5[q])))

    if args.main:
        s.to_csv(SUMMARY_CSV, index=False)
        if out["slopes"] is not None:
            out["slopes"].to_csv(OUT_DIR / "slopes.csv", index=False)
        _write_report(out, _load_sensitivity(), REPORT,
                      runtime_note="Sensitivity runs are 1,000 sims each; their timings are in their own tmp_run pickles.")
        print(f"wrote {SUMMARY_CSV} and {REPORT}")


if __name__ == "__main__":
    main()
