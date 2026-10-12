"""Play-In double-elimination simulator + expected-points bracket optimizer.

Bracket (config/worlds2026.yaml):
    UB1: A vs B, UB2: C vs D, UBF: W(UB1) vs W(UB2), LB1: L(UB1) vs L(UB2),
    LBF: L(UBF) vs W(LB1), GF: W(UBF) vs W(LBF)  -> GF winner advances to Swiss.

Picks are made up front, one winner per slot, consistent with the picker's own earlier picks.
A slot scores if the picked team actually wins that slot.
"""
from __future__ import annotations

import itertools

import numpy as np

from model.ratings import series_prob

SLOTS = ["UB1", "UB2", "UBF", "LB1", "LBF", "GF"]


def simulate(teams: list[str], p_series: dict[tuple[str, str], float], n: int = 200_000, seed: int = 7):
    """teams = [UB1a, UB1b, UB2a, UB2b]. p_series[(x, y)] = P(x beats y in a Bo5).
    Returns an array of shape (n, 6) of winner indices per slot, plus the team list."""
    rng = np.random.default_rng(seed)
    idx = {t: i for i, t in enumerate(teams)}
    P = np.full((4, 4), 0.5)
    for (x, y), p in p_series.items():
        P[idx[x], idx[y]] = p
        P[idx[y], idx[x]] = 1 - p

    def play(a, b):
        win_a = rng.random(n) < P[a, b]
        return np.where(win_a, a, b), np.where(win_a, b, a)

    a0, a1, a2, a3 = (np.full(n, i) for i in range(4))
    w1, l1 = play(a0, a1)
    w2, l2 = play(a2, a3)
    wu, lu = play(w1, w2)
    wl1, _ = play(l1, l2)
    wlf, _ = play(lu, wl1)
    wg, _ = play(wu, wlf)
    return np.stack([w1, w2, wu, wl1, wlf, wg], axis=1)


def all_brackets():
    """Every self-consistent pick set, as tuples of team indices per slot."""
    for u1, u2 in itertools.product((0, 1), (2, 3)):
        l1, l2 = 1 - u1, 5 - u2
        for ubf in (u1, u2):
            ubf_loser = u2 if ubf == u1 else u1
            for lb1 in (l1, l2):
                for lbf in (ubf_loser, lb1):
                    for gf in (ubf, lbf):
                        yield (u1, u2, ubf, lb1, lbf, gf)


def optimize(outcomes: np.ndarray, points: dict[str, int]):
    pts = np.array([points[s] for s in SLOTS])
    results = []
    for b in all_brackets():
        hit = outcomes == np.array(b)
        results.append((float((hit * pts).sum(axis=1).mean()), b, hit.mean(axis=0)))
    results.sort(key=lambda r: -r[0])
    return results


def summary(teams, outcomes):
    """Per-team probabilities: win each slot, and advance (win GF)."""
    out = {}
    for i, t in enumerate(teams):
        out[t] = {s: float((outcomes[:, k] == i).mean()) for k, s in enumerate(SLOTS)}
    return out


def run(teams, p_game: dict[tuple[str, str], float], points: dict[str, int], best_of: int = 5, top: int = 5):
    p_series = {k: series_prob(v, best_of) for k, v in p_game.items()}
    outcomes = simulate(teams, p_series)
    return summary(teams, outcomes), optimize(outcomes, points)[:top]
