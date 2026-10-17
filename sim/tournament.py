"""Full Worlds 2026 Monte Carlo: Play-In -> Swiss -> Knockout, simulated game by game.

Output per simulation: every game played (stage, teams, winner, duration) and every team's placement.
Player stats for the Crystal Ball are attached afterwards (crystal/estimate.py) by bootstrapping each
starter's 2026 games conditioned on the simulated result.

Format (config/worlds2026.yaml + user brief):
- Play-In: double elimination, all Bo5. Winner takes the Tier 4 Swiss slot.
- Swiss: 5 rounds; R1 Tier1 v Tier4, Tier2 v Tier3, no same-region in R1; later rounds pair equal records,
  no rematches. Bo3 when either team can advance or be eliminated (2 wins or 2 losses), else Bo1.
- Knockout: 8 teams, random draw (avoiding same-region QFs when possible), all Bo5.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from common.paths import OUTPUTS

TIERS = {
    1: ["GEN", "AL", "TL", "G2"],
    2: ["LOS", "TSW", "HLE", "BLG"],
    3: ["LYON", "MKOI", "T1", "TES"],
    4: ["CFO", "IG", "DK"],  # + Play-In winner
}
PLAYIN = [("FUR", "MVK"), ("C9", "KC")]
# Play-In series already played (Oracle's Elixir, 2026-10-15 to 2026-10-16), game winners in order.
# Replayed as fixed results, not simulated. Empty once the Play-In is over.
PLAYIN_PLAYED = {
    "UB1": ["MVK", "MVK", "MVK"],
    "UB2": ["C9", "KC", "C9", "KC", "KC"],
    "UBF": ["KC", "KC", "KC"],
    "LB1": ["C9", "FUR", "FUR", "FUR"],
}

PLACEMENT_ORDER = ["Champion", "Final", "SF", "QF", "Swiss 2-3", "Swiss 1-3", "Swiss 0-3", "Play-In"]


@dataclass
class Sim:
    P: np.ndarray                                # P[i, j] = P(team i beats team j in one game)
    idx: dict                                    # team_id -> row in P
    region: dict
    rng: np.random.Generator
    games: list = field(default_factory=list)   # (stage, a, b, winner, p_a, series, game_no, best_of)
    playin_slots: list = field(default_factory=list)
    n_series: int = 0

    def p(self, a, b):
        return self.P[self.idx[a], self.idx[b]]

    def series(self, a, b, best_of, stage):
        need, wa, wb = best_of // 2 + 1, 0, 0
        p = self.p(a, b)
        sid, g = self.n_series, 0
        self.n_series += 1
        while wa < need and wb < need:
            g += 1
            if self.rng.random() < p:
                wa += 1
                self.games.append((stage, a, b, a, p, sid, g, best_of))
            else:
                wb += 1
                self.games.append((stage, a, b, b, p, sid, g, best_of))
        return (a, b) if wa == need else (b, a)

    # --- Play-In -----------------------------------------------------------------------------
    def _playin_series(self, slot, a, b):
        """A finished Play-In series is replayed from its real game winners; an open one is simulated."""
        if slot not in PLAYIN_PLAYED:
            return self.series(a, b, 5, "PlayIn")
        wins = PLAYIN_PLAYED[slot]
        assert set(wins) <= {a, b}, (slot, a, b, wins)
        sid, p = self.n_series, self.p(a, b)
        self.n_series += 1
        for g, w in enumerate(wins, 1):
            self.games.append(("PlayIn", a, b, w, p, sid, g, 5))
        winner = max((a, b), key=wins.count)
        return winner, b if winner == a else a

    def playin(self):
        (a, b), (c, d) = PLAYIN
        w1, l1 = self._playin_series("UB1", a, b)
        w2, l2 = self._playin_series("UB2", c, d)
        wu, lu = self._playin_series("UBF", w1, w2)
        wl, _ = self._playin_series("LB1", l1, l2)
        wlf, _ = self._playin_series("LBF", lu, wl)
        wg, _ = self._playin_series("GF", wu, wlf)
        self.playin_slots = [w1, w2, wu, wl, wlf, wg]
        return wg

    # --- Swiss -------------------------------------------------------------------------------
    def _pair(self, pool, played, avoid_region=False, tries=200):
        for _ in range(tries):
            order = list(self.rng.permutation(pool))
            pairs, ok = [], True
            while order:
                a = order.pop(0)
                cand = [b for b in order if frozenset((a, b)) not in played
                        and not (avoid_region and self.region[a] == self.region[b])]
                if not cand:
                    ok = False
                    break
                b = cand[0]
                order.remove(b)
                pairs.append((a, b))
            if ok:
                return pairs
        # fall back: allow region clash, keep no-rematch
        return self._pair(pool, played, False, tries) if avoid_region else list(zip(pool[::2], pool[1::2]))

    def swiss(self, playin_winner):
        tiers = {k: list(v) for k, v in TIERS.items()}
        tiers[4] = tiers[4] + [playin_winner]
        rec = {t: [0, 0] for v in tiers.values() for t in v}
        played = set()
        # round 1: tier-to-tier, no same region
        pairs = []
        for hi, lo in ((1, 4), (2, 3)):
            for _ in range(500):
                perm = list(self.rng.permutation(tiers[lo]))
                if all(self.region[a] != self.region[b] for a, b in zip(tiers[hi], perm)):
                    break
            pairs += list(zip(tiers[hi], perm))
        for rnd in range(1, 6):
            if rnd > 1:
                groups = {}
                for t, (w, l) in rec.items():
                    if w < 3 and l < 3:
                        groups.setdefault((w, l), []).append(t)
                pairs = []
                for key in sorted(groups):
                    pairs += self._pair(groups[key], played)
            for a, b in pairs:
                played.add(frozenset((a, b)))
                decisive = max(rec[a][0], rec[b][0]) == 2 or max(rec[a][1], rec[b][1]) == 2
                w, l = self.series(a, b, 3 if decisive else 1, f"Swiss{rnd}")
                rec[w][0] += 1
                rec[l][1] += 1
        return rec

    # --- Knockout ----------------------------------------------------------------------------
    def knockout(self, qualified):
        for _ in range(200):
            perm = list(self.rng.permutation(qualified))
            qf = list(zip(perm[0::2], perm[1::2]))
            if all(self.region[a] != self.region[b] for a, b in qf):
                break
        place = {}
        sf_teams = []
        for a, b in qf:
            w, l = self.series(a, b, 5, "QF")
            place[l] = "QF"
            sf_teams.append(w)
        finalists = []
        for a, b in ((sf_teams[0], sf_teams[1]), (sf_teams[2], sf_teams[3])):
            w, l = self.series(a, b, 5, "SF")
            place[l] = "SF"
            finalists.append(w)
        w, l = self.series(finalists[0], finalists[1], 5, "Final")
        place[l], place[w] = "Final", "Champion"
        return place


def run(P: pd.DataFrame | None, region: dict, n: int = 20000, seed: int = 2026, sampler=None):
    """Simulate n tournaments. Either a fixed probability matrix P (DataFrame) or a `sampler`
    = (ids, sample(rng) -> ndarray) that draws a new plausible matrix per simulation (rating uncertainty).
    Returns (games [sim, stage, a, b, winner, p_a, series (id within sim), game_no (1-based in series), best_of],
    placements [sim, team, placement, swiss_w, swiss_l],
    playin slot winners [sim, UB1, UB2, UBF, LB1, LBF, GF])."""
    rng = np.random.default_rng(seed)
    if sampler is not None:
        ids, draw = sampler
    else:
        ids, fixed = P.index.tolist(), P.to_numpy()
    idx = {t: k for k, t in enumerate(ids)}
    g_rows, p_rows, s_rows = [], [], []
    for s in range(n):
        sim = Sim(draw(rng) if sampler is not None else fixed, idx, region, rng)
        piw = sim.playin()
        rec = sim.swiss(piw)
        qualified = [t for t, (w, _) in rec.items() if w == 3]
        place = sim.knockout(qualified)
        for t in ids:
            if t in place:
                pl = place[t]
            elif t in rec:
                pl = f"Swiss {rec[t][0]}-3"
            else:
                pl = "Play-In"
            w, l = rec.get(t, (np.nan, np.nan))
            p_rows.append((s, t, pl, w, l))
        g_rows += [(s, *g) for g in sim.games]
        s_rows.append((s, *sim.playin_slots))
    games = pd.DataFrame(g_rows, columns=["sim", "stage", "a", "b", "winner", "p_a", "series", "game_no", "best_of"])
    places = pd.DataFrame(p_rows, columns=["sim", "team", "placement", "swiss_w", "swiss_l"])
    slots = pd.DataFrame(s_rows, columns=["sim", "UB1", "UB2", "UBF", "LB1", "LBF", "GF"])
    return games, places, slots


def summarize(places: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    n = places["sim"].nunique()
    tab = pd.crosstab(places["team"], places["placement"]) / n
    tab = tab.reindex(columns=[c for c in PLACEMENT_ORDER if c in tab.columns], fill_value=0)
    tab["P(KO)"] = tab[[c for c in ("Champion", "Final", "SF", "QF") if c in tab]].sum(axis=1)
    long = pd.concat([games[["sim", "a"]].rename(columns={"a": "team"}), games[["sim", "b"]].rename(columns={"b": "team"})])
    gp = long.groupby(["sim", "team"]).size().unstack(fill_value=0)
    tab["games_mean"] = gp.mean()
    tab["games_p90"] = gp.quantile(0.9)
    return tab.sort_values(["Champion", "P(KO)"], ascending=False)


if __name__ == "__main__":
    import sys
    from model.predict import game_matrix, teams_table

    sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    P = game_matrix(verbose=True)
    region = teams_table().set_index("team_id")["region"].to_dict()
    games, places, _ = run(P, region, n=n)
    games.to_csv(OUTPUTS / "sim_games.csv.gz", index=False)
    places.to_csv(OUTPUTS / "sim_places.csv.gz", index=False)
    pd.set_option("display.width", 200)
    print(summarize(places, games).round(3).to_string())
