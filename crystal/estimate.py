"""Crystal Ball estimates from the tournament simulation.

For every simulated game, each starter's stat line is bootstrapped from their own 2026 games
(top leagues + internationals), drawn from their wins or losses to match the simulated result.
Game durations are bootstrapped from the winner's 2026 wins, shifted so the share of games
under 32:00 matches the Worlds projection (Worlds games run longer than other events).

    python -m crystal.estimate [n_sims]
"""
from __future__ import annotations

import sys

import duckdb
import numpy as np
import pandas as pd

from model.predict import game_matrix, matrix_sampler, teams_table
from sim import playin
from sim.tournament import run, summarize

TOP = ("LCK", "LPL", "LEC", "LCS", "LCP", "CBLOL", "WLDQ", "MSI", "EWC", "FST")
TARGET_UNDER32 = 0.44     # projection: 2026 internationals 53% minus the recent Worlds gap (~9 pts)
MIN_GAMES = 1             # Q4-Q6 player leaderboards: no minimum games (user-confirmed 2026-10-12)
MVP_ROLE_PRIOR = {"Top": .25, "Jungle": .25, "Mid": .25, "Bot": .20, "Support": .05}  # Worlds 2014-25 finals MVPs, smoothed


def player_pools(con, starters: pd.DataFrame) -> dict:
    ids = ",".join(f"'{x}'" for x in starters["player_id"])
    df = con.sql(f"""select player_id, win, kills, deaths, assists, team_kills, cs, damage
        from player_games where player_id in ({ids}) and date_utc >= '2026-01-01'
        and league in {TOP}""").df()
    pools = {}
    for pid, g in df.groupby("player_id"):
        pools[pid] = {w: g[g["win"] == w][["kills", "deaths", "assists", "team_kills", "cs", "damage"]].to_numpy(float)
                      for w in (True, False)}
    return pools


def duration_pools(con, teams: pd.DataFrame) -> dict:
    ids = ",".join(f"'{x}'" for x in teams["oe_team_id"])
    df = con.sql(f"""select case when blue_win then blue_team_id else red_team_id end winner_id, duration_sec
        from games where date_utc >= '2026-01-01' and league in {TOP}
        and (case when blue_win then blue_team_id else red_team_id end) in ({ids})""").df()
    m = dict(zip(teams["oe_team_id"], teams["team_id"]))
    return {m[k]: g["duration_sec"].to_numpy(float) for k, g in df.groupby("winner_id")}


POINTS = (50, 20, 10)     # "who leads" scoring: 1st, 2nd, 3rd (config/worlds2026.yaml); ties are not split


def greater_counts(v: np.ndarray) -> np.ndarray:
    """v: (candidates x sims), -inf = cannot place. Returns, per cell, how many values in that sim are strictly greater."""
    P = v.shape[0]
    order = np.argsort(v, axis=0, kind="stable")
    sa = np.take_along_axis(v, order, axis=0)                 # ascending within each sim
    end = np.ones(sa.shape, bool)
    end[:-1] = sa[:-1] < sa[1:]                               # last position of each block of equal values
    j = np.arange(P)[:, None]
    group_end = np.minimum.accumulate(np.where(end, j, P)[::-1], axis=0)[::-1]
    greater_sorted = P - 1 - group_end
    inv = np.empty_like(order)                                # inv[i, s] = sorted position of candidate i in sim s
    np.put_along_axis(inv, order, np.broadcast_to(j, order.shape), axis=0)
    return np.take_along_axis(greater_sorted, inv, axis=0)


def rank_table(metric: np.ndarray, ok: np.ndarray, names) -> pd.DataFrame:
    """Expected-points table for a 'who leads' question. metric, ok: (candidates x sims).
    rank = 1 + number of eligible candidates with a strictly greater value (ties all get the same rank)."""
    v = np.where(ok, metric, -np.inf)
    if not np.isfinite(v[ok]).all():
        raise ValueError("non-finite metric for an eligible candidate")
    rank = greater_counts(v) + 1
    df = pd.DataFrame({f"p{k}": ((rank == k) & ok).mean(axis=1) for k in (1, 2, 3)}, index=names)
    df["EV"] = POINTS[0] * df["p1"] + POINTS[1] * df["p2"] + POINTS[2] * df["p3"]
    return df.sort_values("EV", ascending=False)


def estimate(n: int = 20000, seed: int = 11, uncertainty: bool = True):
    rng = np.random.default_rng(seed)
    con = duckdb.connect("data/pickems.duckdb", read_only=True)
    teams = teams_table()
    region = teams.set_index("team_id")["region"].to_dict()
    ros = pd.read_csv("data/rosters_2026.csv")
    starters = ros[ros["is_starter"] == True][["team_id", "role", "player", "player_id"]]

    P = game_matrix(verbose=True)
    if uncertainty:   # each simulation draws its own plausible strengths (Laplace covariance)
        games, places, slots = run(None, region, n=n, seed=seed, sampler=matrix_sampler())
    else:
        games, places, slots = run(P, region, n=n, seed=seed)
    G = len(games)
    sim = games["sim"].to_numpy()

    # durations: mismatch effect fitted on 862 international games (duration = c - 85 * logit p_winner,
    # residual sd 5.2 min) + winner's typical win speed shrunk 50% toward the field + noise
    dpool = duration_pools(con, teams)
    overall = np.concatenate(list(dpool.values())).mean()
    speed = {t: 0.5 * (v.mean() - overall) for t, v in dpool.items()}
    p_w = np.where(games["winner"] == games["a"], games["p_a"], 1 - games["p_a"]).astype(float)
    dur = (-85 * np.log(p_w / (1 - p_w)) + games["winner"].map(speed).fillna(0).to_numpy()
           + rng.normal(0, 290, G))
    dur = np.maximum(dur, 17 * 60 - 1943)          # floor ~17 min after the shift below
    under = lambda d: np.mean(d < 1920)
    lo, hi = 0.0, 4000.0
    for _ in range(40):                      # bisection on the shift
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if under(dur + mid) > TARGET_UNDER32 else (lo, mid)
    dur = dur + (lo + hi) / 2
    games["duration"] = dur

    # player stats
    pools = player_pools(con, starters)
    max_k = np.zeros(G)
    max_cs = np.zeros(G)
    agg = {}
    is_final = (games["stage"] == "Final").to_numpy()
    champion = places[places["placement"] == "Champion"].set_index("sim")["team"]
    mvp_score = {}
    for t in teams["team_id"]:
        rows = np.where((games["a"] == t) | (games["b"] == t))[0]
        won = (games["winner"].to_numpy()[rows] == t)
        for _, pl in starters[starters["team_id"] == t].iterrows():
            pool = pools.get(pl["player_id"])
            if pool is None or len(pool[True]) == 0 or len(pool[False]) == 0:
                continue
            stats = np.empty((len(rows), 6))
            for w in (True, False):
                m = won == w
                stats[m] = pool[w][rng.integers(0, len(pool[w]), m.sum())]
            k, d, a, tk, cs, dmg = stats.T
            np.maximum.at(max_k, rows, k)
            np.maximum.at(max_cs, rows, cs)
            s = sim[rows]
            kp = np.where(tk > 0, (k + a) / np.maximum(tk, 1), 0)
            agg[pl["player"]] = {
                "team": t, "role": pl["role"],
                "games": np.bincount(s, minlength=n), "kills": np.bincount(s, k, n), "deaths": np.bincount(s, d, n),
                "assists": np.bincount(s, a, n), "damage": np.bincount(s, dmg, n), "kp": np.bincount(s, kp, n),
            }
            fm = is_final[rows]
            score = k + 0.6 * a - d + dmg / 2000
            mvp_score[(t, pl["role"])] = np.bincount(s[fm], score[fm], n)

    out = {}
    names = list(agg)
    gm = np.array([agg[p]["games"] for p in names])
    ok = gm >= MIN_GAMES

    def ranked(metric, min_games=MIN_GAMES):
        return rank_table(metric, gm >= min_games, names)

    K = np.array([agg[p]["kills"] for p in names]); D = np.array([agg[p]["deaths"] for p in names])
    A = np.array([agg[p]["assists"] for p in names]); DMG = np.array([agg[p]["damage"] for p in names])
    KP = np.array([agg[p]["kp"] for p in names])
    with np.errstate(divide="ignore", invalid="ignore"):
        out["Q4 KDA leader"] = ranked((K + A) / np.maximum(D, 1))
        out["Q5 damage/game leader"] = ranked(DMG / np.maximum(gm, 1))
        out["Q6 KP leader"] = ranked(KP / np.maximum(gm, 1))
    kills = lambda p: agg[p]["kills"]
    out["Q7 Peyz vs Gumayusi"] = pd.Series({"Peyz": np.mean(kills("Peyz") > kills("Gumayusi")),
                                            "Gumayusi": np.mean(kills("Gumayusi") > kills("Peyz")),
                                            "tie": np.mean(kills("Gumayusi") == kills("Peyz"))})
    fk = kills("Faker")
    out["Q8 Faker >= 84 kills"] = pd.Series({"Yes": np.mean(fk >= 84), "mean kills": fk.mean(),
                                             "p10": np.percentile(fk, 10), "p90": np.percentile(fk, 90)})
    any_ = lambda flag: pd.Series(flag).groupby(sim).any().mean()
    out["Q11 games under 32:00"] = pd.Series({"share under": under(dur),
                                              "P(more games after)": np.mean(games.assign(u=dur < 1920).groupby("sim")["u"].mean() < 0.5)})
    out["Q12 any 15+ kill game"] = pd.Series({"Yes": any_(max_k >= 15)})
    out["Q13 any 450+ CS game"] = pd.Series({"Yes": any_(max_cs >= 450)})

    # Q14 MVP role: best final-series performer on the champion team, blended 50/50 with history
    roles = list(MVP_ROLE_PRIOR)
    best = []
    for s_, c in champion.items():
        sc = [mvp_score.get((c, r), np.zeros(n))[s_] for r in roles]
        best.append(roles[int(np.argmax(sc))])
    sim_roles = pd.Series(best).value_counts(normalize=True).reindex(roles, fill_value=0)
    out["Q14 Finals MVP role"] = (0.5 * sim_roles + 0.5 * pd.Series(MVP_ROLE_PRIOR)).sort_values(ascending=False)

    ko = places[places["placement"].isin(["Champion", "Final", "SF", "QF"])].assign(region=lambda d: d["team"].map(region))
    out["Q15 regions in KO"] = ko.groupby("sim")["region"].nunique().value_counts(normalize=True).sort_index()
    out["Q16 LCS team in KO"] = pd.Series({"Yes": ko.groupby("sim")["region"].apply(lambda r: (r == "LCS").any()).reindex(range(n), fill_value=False).mean()})
    rank = {p: i for i, p in enumerate(["Champion", "Final", "SF", "QF", "Swiss 2-3", "Swiss 1-3", "Swiss 0-3", "Play-In"])}
    pr = places.assign(r=places["placement"].map(rank)).pivot(index="sim", columns="team", values="r")
    out["Q17 HLE vs T1"] = pd.Series({"T1 higher": np.mean(pr["T1"] < pr["HLE"]), "HLE higher": np.mean(pr["HLE"] < pr["T1"]),
                                      "same stage": np.mean(pr["HLE"] == pr["T1"])})
    # Q18: rank teams by their own shortest win in each sim (a team with no win in a sim cannot place)
    W = games.groupby(["winner", "sim"])["duration"].min().unstack("sim").reindex(columns=range(n))
    out["Q18 shortest game winner"] = rank_table(-W.to_numpy(float), W.notna().to_numpy(), list(W.index))

    # Play-In bracket optimisation on the same simulations
    pteams = ["FUR", "MVK", "C9", "KC"]
    outcomes = slots[playin.SLOTS].replace({t: i for i, t in enumerate(pteams)}).to_numpy(int)
    best = playin.optimize(outcomes, {"UB1": 5, "UB2": 5, "UBF": 5, "LB1": 5, "LBF": 5, "GF": 10})[:3]
    out["Play-In best brackets (EV / picks / P(hit) per slot)"] = pd.Series(
        {f"EV {ev:.2f}": " ".join(f"{sl}:{pteams[t]}({h:.2f})" for sl, t, h in zip(playin.SLOTS, b, hit)) for ev, b, hit in best})

    summary = summarize(places, games)
    games_played = pd.Series({p: agg[p]["games"].mean() for p in names})
    return out, summary, games_played


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    fixed = "--fixed" in sys.argv          # point estimates only (no rating uncertainty)
    out, summary, _ = estimate(n, uncertainty=not fixed)
    pd.set_option("display.width", 200)
    print(summary.round(3).to_string())
    lines = []
    for k, v in out.items():
        print(f"\n== {k}\n{v.round(3).head(8).to_string()}")
        lines.append(f"## {k}\n\n```\n{v.round(3).head(8).to_string()}\n```\n")
        if "p1" in v:   # ranked tables: each place's probabilities should sum to ~1
            print(f"sum p1={v['p1'].sum():.4f}  p2={v['p2'].sum():.4f}  p3={v['p3'].sum():.4f}")
    with open("outputs/crystal_sim.md", "w", encoding="utf-8") as f:
        mode = "point estimates" if fixed else "with rating uncertainty"
        f.write(f"# Crystal Ball — simulation estimates ({n} sims, {mode})\n\n" + "\n".join(lines))
        f.write("\n## Tournament outcome table\n\n```\n" + summary.round(3).to_string() + "\n```\n")
