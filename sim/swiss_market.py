"""Blend the Swiss "reach top 8" market with the model, then re-simulate records.

1. Each book: remove the margin with the power method (find k so that sum p_i^k = 8 qualifiers).
2. Market = logit-average of the books; target = logit-average of model and market (weight W_MARKET),
   shifted so the targets sum to 8.
3. Fit one logit strength offset per team so the simulated P(advance) hits the target (fixed seed,
   damped fixed-point steps), then run the full sim with those offsets for the record split.

    python -m sim.swiss_market [n_final]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from common.paths import OUTPUTS
from sim.swiss_draw import RECORDS, best_picks, simulate

# User-supplied, 2026-10-19.
BOOK_ODDS = {"GEN": 1.12, "HLE": 1.16, "T1": 1.16, "BLG": 1.22, "AL": 1.5, "DK": 1.72, "G2": 1.8, "IG": 2.2,
             "TL": 2.35, "TES": 2.35, "LYON": 2.4, "KC": 2.6, "MKOI": 2.75, "TSW": 3, "CFO": 5, "LOS": 5}
BOOK_PCT = {"GEN": 92, "T1": 86, "BLG": 85, "HLE": 85, "AL": 71, "DK": 69, "G2": 62, "IG": 55, "LYON": 44,
            "TES": 38, "TL": 37, "TSW": 33, "MKOI": 32, "KC": 27, "CFO": 23, "LOS": 11}
W_MARKET = 0.5
SLOTS = 8


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def demargin(raw: pd.Series) -> pd.Series:
    k = brentq(lambda k: (raw ** k).sum() - SLOTS, 0.2, 10)
    return raw ** k


def to_sum(p: pd.Series) -> pd.Series:
    c = brentq(lambda c: sigmoid(logit(p) + c).sum() - SLOTS, -5, 5)
    return pd.Series(sigmoid(logit(p) + c), index=p.index)


def fit_offsets(target: pd.Series, n: int = 10000, iters: int = 8, step: float = 0.8):
    off = {t: 0.0 for t in target.index}
    for it in range(iters):
        tab = simulate(n, seed=7, offsets=off, save=False)
        sim = tab["P(advance)"].reindex(target.index)
        err = (sim - target).abs().max()
        print(f"  iter {it}: max |sim - target| = {err:.3f}")
        if err < 0.01:
            break
        for t in target.index:
            off[t] += step * (logit(target[t]) - logit(sim[t])) / 2   # game-level effect is ~half the stage-level one
    return off


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    n_final = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    b1 = demargin(1 / pd.Series(BOOK_ODDS))
    b2 = demargin(pd.Series(BOOK_PCT) / 100)
    market = pd.Series(sigmoid((logit(b1) + logit(b2.reindex(b1.index))) / 2), index=b1.index)
    model = pd.read_csv(OUTPUTS / "swiss_draw_records.csv", index_col=0)["P(advance)"].reindex(b1.index)
    target = to_sum(pd.Series(sigmoid((1 - W_MARKET) * logit(model) + W_MARKET * logit(market)), index=b1.index))

    print("fitting offsets ...")
    off = fit_offsets(target)
    tab = simulate(n_final, seed=2026, offsets=off, save=False)
    tab.to_csv(OUTPUTS / "swiss_market_records.csv")

    cmp = pd.DataFrame({"book1": b1, "book2": b2, "market": market, "model": model, "target": target,
                        "blended sim": tab["P(advance)"], "offset": pd.Series(off)})
    pd.set_option("display.width", 200)
    print(cmp.sort_values("target", ascending=False).round(3).to_string())
    print(tab[RECORDS + ["P(advance)"]].round(3).to_string())
    for b in (0.5, 1, 2, 4):
        ev, (trio, rest) = best_picks(tab, b)
        print(f"bonus={b}x: 3-0 {trio[0]}, 3-1 {trio[1]}, 3-2 {trio[2]} | others {', '.join(rest)} | EV {ev:.2f}")
