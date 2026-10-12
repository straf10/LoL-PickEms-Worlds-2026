"""Stress test for Crystal Ball Q7: Peyz vs Gumayusi total kills (Worlds 2026, all games).

Reuses the tournament simulation (sim.tournament.run) and the 2026 bootstrap pools (crystal.estimate.player_pools).
Each variant changes how a player's kills in a simulated game are drawn:
  env      team kill environment vs Worlds-field opponents (team kills vs field / team kills overall)
  share    bot-laner kill share vs Worlds-field opponents (share vs field / share overall)
  fear     kills in game 3+ of a series scaled by the 2025-26 game-3+ ratio (Fearless series at Worlds)
  recency  2026 kill share shrunk toward the 2024-25 share, with posterior uncertainty drawn per simulation

    python -m crystal.q7_check [n_sims] [seed]
"""
from __future__ import annotations

import os
import sys

import duckdb
import numpy as np
import pandas as pd

from common.paths import DB_PATH, OUTPUTS, ROSTERS_CSV
from crystal.estimate import TOP, player_pools, estimate
from model.predict import matrix_sampler, teams_table
from sim.tournament import run

PLAYERS = {"Peyz": "T1", "Gumayusi": "HLE"}       # player -> team_id in the simulation
SHRINK_N = 30                                      # pseudo-games: group factors shrink toward 1 by n / (n + 30)
MIN_PERIOD_GAMES = 20                              # half-years used to estimate between-period variance
VARIANTS = {
    "a) current method":           dict(env=False, share=False, fear=False, recency=False),
    "b1) team kill env only":      dict(env=True,  share=False, fear=False, recency=False),
    "b2) bot share only":          dict(env=False, share=True,  fear=False, recency=False),
    "b3) game-3+ factor only":     dict(env=False, share=False, fear=True,  recency=False),
    "b4) recency shrink only":     dict(env=False, share=False, fear=False, recency=True),
    "c) opponent (b1+b2)":         dict(env=True,  share=True,  fear=False, recency=False),
    "c2) opponent, LCK top-4 def": dict(env=True,  share=True,  fear=False, recency=False, adj="lck4"),
    "d) all combined (b1-b4)":     dict(env=True,  share=True,  fear=True,  recency=True),
}


def frame(con, pids) -> pd.DataFrame:
    ids = ",".join(f"'{x}'" for x in pids)
    return con.sql(f"""select pg.player_id, pg.player, pg.team_id, pg.league, pg.date_utc, pg.win, pg.kills, pg.team_kills,
        g.game_in_series gis, g.is_international intl,
        case when g.blue_team_id = pg.team_id then g.red_team_id else g.blue_team_id end opp
        from player_games pg join games g using (game_id)
        where pg.player_id in ({ids}) and pg.date_utc >= '2024-06-01' and pg.league in {TOP}""").df()


def fearless_ratio(con) -> float:
    """Kills per game in game 3+ of a series over games 1-2, all players, 2025-26 top leagues."""
    df = con.sql(f"""select pg.kills, g.game_in_series gis from player_games pg join games g using (game_id)
        where pg.date_utc >= '2025-01-01' and pg.league in {TOP}""").df()
    return df.loc[df.gis >= 3, "kills"].mean() / df.loc[df.gis <= 2, "kills"].mean()


def shrunk(ratio: float, n: int) -> float:
    return 1 + n / (n + SHRINK_N) * (ratio - 1)


def share(g: pd.DataFrame) -> float:
    return g["kills"].sum() / g["team_kills"].sum()


def field_factors(cur: pd.DataFrame, field: set) -> tuple[float, float, int]:
    """(team kill env factor, bot share factor, n games vs field) for one player's 2026 games."""
    f = cur[cur["opp"].isin(field)]
    env = shrunk(f["team_kills"].mean() / cur["team_kills"].mean(), len(f))
    sh = shrunk(share(f) / share(cur), len(f))
    return env, sh, len(f)


def recency_factors(fr: pd.DataFrame, pid: str) -> tuple[float, float, dict]:
    """Posterior 2026 share = prior (2024-25 share) + w (2026 share - prior), w = tau^2 / (tau^2 + se^2).
    tau^2 = between-half-year variance of the share, minus average sampling variance. Returns the mean and sd
    of the posterior multiplier applied to 2026 kills."""
    d = fr[fr["player_id"] == pid]
    hist, cur = d[d["date_utc"] < "2026-01-01"], d[d["date_utc"] >= "2026-01-01"]
    se2 = lambda g, s: (np.std(g["kills"] - s * g["team_kills"], ddof=1) / (g["team_kills"].mean() * np.sqrt(len(g)))) ** 2
    per = d.assign(h=d["date_utc"].dt.year.astype(str) + "H" + np.where(d["date_utc"].dt.month <= 6, "1", "2"))
    rows = [(share(g), se2(g, share(g))) for _, g in per.groupby("h") if len(g) >= MIN_PERIOD_GAMES]
    s_arr, v_arr = np.array(rows).T
    tau2 = max(np.var(s_arr, ddof=1) - v_arr.mean(), 1e-4 ** 2)
    s26, v26 = share(cur), se2(cur, share(cur))
    mu = share(hist)
    w = tau2 / (tau2 + v26)
    post = mu + w * (s26 - mu)
    post_sd = np.sqrt(1 / (1 / tau2 + 1 / v26))
    info = dict(share_2026=s26, se_2026=np.sqrt(v26), share_prior=mu, tau=np.sqrt(tau2), weight_2026=w,
                share_posterior=post, n_periods=len(rows))
    return post / s26, post_sd / s26, info


def simulate(games, pools, field_adj, fear_r, rec, flags, rng, n):
    """Per player: kills, games, expected kills (given the drawn factors) for one variant."""
    out = {}
    for name, team in PLAYERS.items():
        pid = field_adj[name]["pid"]
        env, sh = field_adj[name]["env"], field_adj[name]["share"]
        rows = np.where((games["a"] == team) | (games["b"] == team))[0]
        sim = games["sim"].to_numpy()[rows]
        won = games["winner"].to_numpy()[rows] == team
        game_no = games["game_no"].to_numpy()[rows]
        draw = np.empty(len(rows))
        for w in (True, False):
            m = won == w
            draw[m] = pools[pid][w][rng.integers(0, len(pools[pid][w]), m.sum()), 0]
        f = np.full(len(rows), 1.0)
        if flags["env"]:
            f *= env
        if flags["share"]:
            f *= sh
        if flags["fear"]:
            f *= np.where(game_no >= 3, fear_r, 1.0)
        exp = np.where(won, pools[pid][True][:, 0].mean(), pools[pid][False][:, 0].mean()) * f
        if flags["recency"]:
            z = np.clip(rng.normal(rec[name][0], rec[name][1], n), 0.2, None)
            draw = draw * z[sim]
            exp = exp * rec[name][0]
        out[name] = dict(kills=np.rint(np.bincount(sim, draw * f, n)), games=np.bincount(sim, minlength=n),
                         exp_total=exp.sum() / n, wins=np.bincount(sim[won], minlength=n))
    return out


def main(n: int = 40000, seed: int = 11):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    ros = pd.read_csv(ROSTERS_CSV)
    starters = ros[ros["is_starter"] == True][["team_id", "role", "player", "player_id"]]
    st = starters[starters["player"].isin(PLAYERS)]
    pids = dict(zip(st["player"], st["player_id"]))
    pools = player_pools(con, st)
    fr = frame(con, list(pids.values()))
    field = set(teams_table()["oe_team_id"])
    lck4 = {"oe:team:50f58982d91a36557ec8aec52ab014f", "oe:team:3a1d18f46bcb3716ebcfcf4ef068934",
            "oe:team:ce499dea30cfce118f4fe85da0227e8", "oe:team:ef69efa6acebe94107f0cf1ba716806"}
    fear_r = fearless_ratio(con)
    os.makedirs(OUTPUTS / "q7", exist_ok=True)

    # inputs (sanity printout)
    rows, adj, rec = [], {"field": {}, "lck4": {}}, {}
    for name, pid in pids.items():
        cur = fr[(fr["player_id"] == pid) & (fr["date_utc"] >= "2026-01-01")]
        pool = pools[pid]
        assert len(cur) == len(pool[True]) + len(pool[False]), "frame and pool disagree"
        env, sh, nf = field_factors(cur, field)
        rf = cur[cur["opp"].isin(lck4)]
        adj["field"][name] = dict(pid=pid, env=env, share=sh)
        adj["lck4"][name] = dict(pid=pid, **dict(zip(("env", "share"), field_factors(cur, lck4)[:2])))
        rec_mean, rec_sd, info = recency_factors(fr, pid)
        rec[name] = (rec_mean, rec_sd)
        rows.append(dict(player=name, team=cur["team_id"].iloc[0], games_2026=len(cur), kills_pg=cur["kills"].mean(),
                         sd=cur["kills"].std(), win_rate=cur["win"].mean(), kills_win=pool[True][:, 0].mean(),
                         kills_loss=pool[False][:, 0].mean(), n_vs_field=nf, kills_vs_field=cur.loc[cur["opp"].isin(field), "kills"].mean(),
                         n_vs_lck4=len(rf), kills_vs_lck4=rf["kills"].mean(), intl_games=int(cur["intl"].sum()),
                         kills_intl=cur.loc[cur["intl"] == True, "kills"].mean(),
                         team_kills_pg=cur["team_kills"].mean(), share_2026=info["share_2026"],
                         share_prior_2024_25=info["share_prior"], tau=info["tau"], weight_2026=info["weight_2026"],
                         env_factor=env, share_factor=sh, recency_factor=rec_mean))
    inputs = pd.DataFrame(rows).set_index("player")
    pd.set_option("display.width", 250)
    print("== inputs (2026 top-league pool; field = 2026 Worlds teams; factors shrunk, n<30 games shrink most)")
    print(inputs.T.round(3).to_string())
    print(f"fearless / game-3+ kill ratio (all players, 2025-26 top leagues): {fear_r:.3f}")
    inputs.round(4).to_csv(OUTPUTS / "q7" / "q7_inputs.csv")

    # baseline cross-check against the existing estimate (same sims, same seed/n)
    base_est, _, _ = estimate(n, seed=seed)
    print(f"existing estimate() Q7 Peyz share at n={n}, seed={seed}: {base_est['Q7 Peyz vs Gumayusi']['Peyz']:.4f}")

    res = {}
    for seed_i in [seed, seed + 1]:  # common random numbers: every variant shares the same tournament sims
        games, _, _ = run(None, teams_table().set_index("team_id")["region"].to_dict(), n=n, seed=seed_i,
                          sampler=matrix_sampler())
        for vname, flags in VARIANTS.items():
            rng = np.random.default_rng(seed_i + 1000)
            o = simulate(games, pools, adj[flags.get("adj", "field")], fear_r, rec, flags, rng, n)
            kp, kg = o["Peyz"]["kills"], o["Gumayusi"]["kills"]
            res[(seed_i, vname)] = dict(P_Peyz=np.mean(kp > kg), P_Gum=np.mean(kg > kp), P_tie=np.mean(kp == kg),
                                        mean_kills_Peyz=kp.mean(), mean_kills_Gum=kg.mean(),
                                        mean_games_Peyz=o["Peyz"]["games"].mean(), mean_games_Gum=o["Gumayusi"]["games"].mean(),
                                        exp_kills_Peyz=o["Peyz"]["exp_total"], exp_kills_Gum=o["Gumayusi"]["exp_total"],
                                        win_share_Peyz=o["Peyz"]["wins"].sum() / o["Peyz"]["games"].sum(),
                                        win_share_Gum=o["Gumayusi"]["wins"].sum() / o["Gumayusi"]["games"].sum())
        if seed_i == seed:
            gp = pd.concat([games[["sim", "a"]].rename(columns={"a": "t"}), games[["sim", "b"]].rename(columns={"b": "t"})])
            gp = gp.groupby(["sim", "t"]).size().unstack(fill_value=0)
            gt = gp[["T1", "HLE"]]
            print(f"\n== games per team (seed {seed}): T1 mean {gt['T1'].mean():.2f} HLE mean {gt['HLE'].mean():.2f}; "
                  f"corr {np.corrcoef(gt['T1'], gt['HLE'])[0, 1]:.3f}; P(T1 more games) {np.mean(gt['T1'] > gt['HLE']):.3f}; "
                  f"P(HLE more) {np.mean(gt['T1'] < gt['HLE']):.3f}; P(equal) {np.mean(gt['T1'] == gt['HLE']):.3f}")

    table = pd.DataFrame({k[1]: {"seed": k[0], **v} for k, v in res.items() if k[0] == seed}).T
    table = table.drop(columns=[]).round(4)
    print(f"\n== variants (n={n}, seed={seed})")
    print(table.drop(columns=["seed"]).to_string())
    table.to_csv(OUTPUTS / "q7" / "q7_variants.csv")
    cmp = pd.DataFrame({"P_Peyz_seed%d" % s: {v: res[(s, v)]["P_Peyz"] for v in VARIANTS} for s in (seed, seed + 1)})
    print(f"\n== seed stability (seeds {seed} and {seed + 1})")
    print(cmp.round(4).to_string())
    cmp.round(4).to_csv(OUTPUTS / "q7" / "q7_seed_stability.csv")
    print("\n== plausibility (combined variant): mean games x kills/game used = expected total; vs simulated total")
    r = res[(seed, "d) all combined (b1-b4)")]
    for name, key in (("Peyz", "Peyz"), ("Gumayusi", "Gum")):
        g_, ex = r[f"mean_games_{key}"], r[f"exp_kills_{key}"]
        print(f"{name}: games {g_:.2f} x kills/game used {ex / g_:.3f} = expected {ex:.1f}; simulated {r[f'mean_kills_{key}']:.1f}; "
              f"ratio {r[f'mean_kills_{key}'] / ex:.4f}; win share {r[f'win_share_{key}']:.3f}")
    return inputs, table


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 11
    main(n, seed)
