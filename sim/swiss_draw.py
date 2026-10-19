"""Swiss stage from the official Round 1 draw (2026-10-19). KC won the Play-In.

Pick'Em: choose 8 teams to advance. Three of them are bonus picks, one each for a 3-0, 3-1 and 3-2
record; a bonus pick pays extra only if that team advances with exactly that record.
Bonus size is not published, so the best set is shown for a few bonus/base ratios.

    python -m sim.swiss_draw [n_sims]
"""
from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

from common.paths import OUTPUTS
from model.predict import matrix_sampler, teams_table
from sim.tournament import Sim

PLAYIN_WINNER = "KC"
R1 = [("GEN", "IG"), ("TL", "CFO"), ("AL", "KC"), ("G2", "DK"),
      ("HLE", "TES"), ("LOS", "T1"), ("TSW", "LYON"), ("BLG", "MKOI")]
RECORDS = ["3-0", "3-1", "3-2"]


def shift(P: np.ndarray, ids: list[str], offsets: dict | None) -> np.ndarray:
    """Add a per-team logit offset to every game: P'[i,j] = sigmoid(logit P[i,j] + o_i - o_j)."""
    if not offsets:
        return P
    o = np.array([offsets.get(t, 0.0) for t in ids])
    Pc = np.clip(P, 1e-6, 1 - 1e-6)
    out = 1 / (1 + np.exp(-(np.log(Pc / (1 - Pc)) + o[:, None] - o[None, :])))
    np.fill_diagonal(out, 0.5)
    return out


_SAMPLER = None


def simulate(n: int, seed: int = 2026, offsets: dict | None = None, save: bool = True) -> pd.DataFrame:
    global _SAMPLER
    rng = np.random.default_rng(seed)
    if _SAMPLER is None:
        _SAMPLER = matrix_sampler()
    ids, draw = _SAMPLER
    idx = {t: k for k, t in enumerate(ids)}
    region = teams_table().set_index("team_id")["region"].to_dict()
    rows = []
    for s in range(n):
        rec = Sim(shift(draw(rng), ids, offsets), idx, region, rng).swiss(PLAYIN_WINNER, r1=R1)
        rows += [(s, t, f"{w}-{l}") for t, (w, l) in rec.items()]
    df = pd.DataFrame(rows, columns=["sim", "team", "record"])
    if save:
        df.to_csv(OUTPUTS / "swiss_draw_sims.csv.gz", index=False)
    tab = pd.crosstab(df["team"], df["record"]) / n
    for r in RECORDS:
        tab[r] = tab.get(r, 0.0)
    tab["P(advance)"] = tab[RECORDS].sum(axis=1)
    return tab.sort_values("P(advance)", ascending=False)


def best_picks(tab: pd.DataFrame, bonus: float):
    """Maximise expected points: sum P(advance) over the 8 + bonus * sum P(exact record) of the 3 bonus picks
    (in units of one correct qualifier)."""
    teams, adv = tab.index.tolist(), tab["P(advance)"]
    best = (-1, None)
    for trio in itertools.permutations(teams, 3):
        rest = adv.drop(list(trio)).nlargest(5)
        ev = adv[list(trio)].sum() + rest.sum() + bonus * sum(tab.loc[t, r] for t, r in zip(trio, RECORDS))
        if ev > best[0]:
            best = (ev, (trio, rest.index.tolist()))
    return best


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    tab = simulate(n)
    tab.to_csv(OUTPUTS / "swiss_draw_records.csv")
    cols = RECORDS + ["P(advance)", "2-3", "1-3", "0-3"]
    print(tab[[c for c in cols if c in tab]].round(3).to_string())
    for b in (0.5, 1, 2, 4):
        ev, (trio, rest) = best_picks(tab, b)
        print(f"bonus={b}x: 3-0 {trio[0]}, 3-1 {trio[1]}, 3-2 {trio[2]} | others {', '.join(rest)} | EV {ev:.2f}")
