"""Scratch constraint checks for crystal/draft.py (not a deliverable)."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Python\LOL_PICKEMS")
import crystal.draft as d  # noqa: E402

games = pd.read_csv(d.GAMES_FILE)
games = games[games.sim < 200]
b = d._base()
ctx = d._context(15.0)
G = d._game_arrays(games, b.tix)
S, C = G.n_sims, b.C
zeros = np.zeros((S, C))
logm = np.zeros(C)
logmb = np.zeros(C)
trace = []
res = d._simulate(G, ctx, logm, logmb, zeros, zeros, seed=5, trace=trace)

n_games = len(games)
print("games", n_games, "picks total", res.picks.sum(), "expected", 10 * n_games)
print("bans total", res.bans.sum(), "expected", b.B * n_games)
print("wins total", res.wins.sum(), "expected", 5 * n_games)

# per-game checks: map each block row back to global game row via the sorted order used in _simulate
bad_dup_game = 0
bad_role = 0
bad_ban_pick = 0
bad_series = 0
bad_bo1_lock = 0
seen_series = {}
ban_total = 0
for bi, pc, pt, pr, (br, bc) in trace:
    n = len(bi)
    for i in range(n):
        champs = pc[i]
        if len(set(champs)) != 10:
            bad_dup_game += 1
        # roles per team
        for team in np.unique(pt[i]):
            roles = pr[i][pt[i] == team]
            if len(set(roles)) != len(roles) or len(roles) != 5:
                bad_role += 1
    # bans vs picks in same game
    ban_by_row = {}
    for r_, c_ in zip(br, bc):
        ban_by_row.setdefault(r_, set()).add(c_)
    ban_total += len(br)
    for i in range(n):
        if ban_by_row.get(i, set()) & set(pc[i]):
            bad_ban_pick += 1
    # fearless: picks of game k must not appear in earlier games of same series
    for i in range(n):
        sid_key = int(G.sid[bi[i]])
        prev = seen_series.get(sid_key, set())
        if G.bo3[bi[i]]:
            if prev & set(pc[i]):
                bad_series += 1
            if (prev & set(ban_by_row.get(i, set()))):
                bad_series += 1
        else:
            bad_bo1_lock += 0
        seen_series[sid_key] = prev | set(pc[i])
print("games with duplicate picks:", bad_dup_game)
print("teams with bad role sets:", bad_role)
print("games with champion both banned and picked:", bad_ban_pick)
print("fearless violations (bo3/bo5 repeat picks or bans in a series):", bad_series)
print("ban rows:", ban_total, "expected", b.B * n_games)

# champion-level sanity: how often a chosen champion is among the team's own starters' weights
print("series with bo3+ count:", int(G.bo3.sum()), "games")
print("sample summary (no shift):")
print(res.picks.sum(0)[:0])
