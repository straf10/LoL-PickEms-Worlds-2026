"""Scratch checks for crystal.estimate.rank_table / greater_counts (not part of the pipeline)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

from crystal.estimate import greater_counts, rank_table

# 1. Toy tie: players 0 and 1 tie for first, player 2 must get rank 3 (ties are not split, next is 3rd).
metric = np.array([[5.0], [5.0], [3.0], [1.0]])
ok = np.ones_like(metric, dtype=bool)
rank = greater_counts(np.where(ok, metric, -np.inf)) + 1
print("toy tie ranks (expect 1,1,3,4):", rank.ravel().tolist())
assert rank.ravel().tolist() == [1, 1, 3, 4]
t = rank_table(metric, ok, ["a", "b", "c", "d"])
assert t.loc["a", "p1"] == 1 and t.loc["b", "p1"] == 1 and t.loc["c", "p3"] == 1
assert t.loc["a", "EV"] == 50 and t.loc["c", "EV"] == 10 and t.loc["d", "EV"] == 0
print(t.to_string())

# 2. Ineligible candidate (ok False) cannot place and does not push others down.
metric = np.array([[9.0], [7.0], [8.0]])
ok = np.array([[True], [False], [True]])
t = rank_table(metric, ok, ["x", "y", "z"])
assert t.loc["x", "p1"] == 1 and t.loc["z", "p2"] == 1 and t.loc["y"].iloc[:3].sum() == 0
print("ineligible check OK")

# 3. Random multi-sim data with many ties vs brute force.
rng = np.random.default_rng(0)
P, S = 7, 50
metric = rng.integers(0, 4, size=(P, S)).astype(float)
ok = rng.random((P, S)) < 0.8
v = np.where(ok, metric, -np.inf)
fast = greater_counts(v)
brute = np.zeros((P, S), int)
for i in range(P):
    for s in range(S):
        brute[i, s] = np.sum(v[:, s] > v[i, s])
assert (fast == brute).all(), "greater_counts disagrees with brute force"
print("random brute-force check OK")

# 4. Sums of p1/p2/p3 on random data with some ineligible candidates (ties present).
t = rank_table(metric, ok, [f"p{i}" for i in range(P)])
has_elig = ok.any(axis=0).mean()
print(f"random: sum p1={t.p1.sum():.4f} p2={t.p2.sum():.4f} p3={t.p3.sum():.4f} (share of sims with any eligible: {has_elig:.4f})")
