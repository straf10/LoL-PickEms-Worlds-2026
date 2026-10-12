"""Q10 (unique champions picked at Worlds 2026) with a bias correction from the meta-shift model.

The draft sim (outputs/draft/tmp_run_k15_shift_s5000.pkl) is a per-sim distribution of unique
champions. The meta-shift closed form (crystal/meta_shift.py, same formula as the sanity table in
outputs/meta/meta_shift_report.md) over-predicted past Worlds events. The draft sim is compared
with the closed form for Worlds 2026 here, and the historical residual (actual - expected) is
applied to the draft sim as a count shift plus per-sim noise. The noise is the model-error part
only: the draft sim already carries realized binomial spread, so that part is removed.

    python -m crystal.q10_correct [--seed S]

Writes outputs/q10/q10_backtest.csv and outputs/q10/q10_buckets.csv and prints both.
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from common.paths import DB_PATH as DB_FILE, ROOT
from crystal import draft
from crystal import meta_shift as ms

DRAFT_PKL = ROOT / "outputs" / "draft" / "tmp_run_k15_shift_s5000.pkl"
GAMES_FILE = ROOT / "outputs" / "draft" / "sim_games_5k.csv.gz"
OUT_DIR = ROOT / "outputs" / "q10"
CACHE_PKL = OUT_DIR / "draft_q10_s5000.pkl"
BACKTEST_CSV = OUT_DIR / "q10_backtest.csv"
BUCKETS_CSV = OUT_DIR / "q10_buckets.csv"
DRAFT_SIMS = 5000
EVENT_START_2026 = "2026-10-15"   # Play-In start, config/worlds2026.yaml
EDGES = [100, 105, 110, 115, 120]  # buckets a) to f)
LABELS = ["a) 0-99", "b) 100-104", "c) 105-109", "d) 110-114", "e) 115-119", "f) 120+"]
REPS = 200                        # extra-noise draws per draft sim
SEED = 11


def _newer_than_db(path: Path) -> bool:
    return path.exists() and path.stat().st_mtime >= DB_FILE.stat().st_mtime


def draft_q10(force: bool = False) -> tuple[np.ndarray, str]:
    """Per-sim unique champions from the draft sim. Reuses a saved run if it is newer than the DB,
    otherwise reruns the draft sim (same settings as `python -m crystal.draft --main`) and caches it."""
    src = next((p for p in (DRAFT_PKL, CACHE_PKL) if not force and _newer_than_db(p)), None)
    if src is None:
        games = pd.read_csv(GAMES_FILE)
        games = games[games.sim < DRAFT_SIMS]
        out = draft.run_draft(games, k=15.0, shift=True, seed=7)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PKL, "wb") as fh:
            pickle.dump(out, fh)
        src = CACHE_PKL
    with open(src, "rb") as fh:
        out = pickle.load(fh)
    return out["q10"].unique_champions.to_numpy(float), str(src.relative_to(ROOT))


def closed_form_P(theta, D):
    """Per-champion inclusion probability P_c = 1 - E_u[(1 - p_cu)^G]."""
    _, log1mp, _ = ms.loglik_terms(theta, D)
    Ep = (np.exp(D["G"][:, None] * log1mp) * ms.W_NORM[None, :]).sum(axis=1)
    return 1.0 - Ep


def backtest(events, R_all, theta) -> pd.DataFrame:
    D = ms.make_D(R_all, "pick")
    rows = []
    for e in events:
        P = closed_form_P(theta, ms.subset(D, D["event"] == e["event"]))
        rows.append({"event": e["event"], "G_ev": e["G_ev"], "expected": float(P.sum()),
                     "realized_sd": float(np.sqrt((P * (1 - P)).sum())),
                     "actual": e["unique_picked_actual"]})
    bt = pd.DataFrame(rows)
    bt["resid"] = bt.actual - bt.expected
    return bt


def closed_form_2026(theta, df, G_sims) -> dict:
    intl = df["is_international"].astype(bool)
    dom = df[(~intl) & df["league"].map(ms.is_domestic)]
    nonint = df[~intl]
    start = pd.Timestamp(EVENT_START_2026)
    pre = dom[(dom.date_utc >= start - pd.Timedelta(days=ms.PRE_DAYS)) & (dom.date_utc < start)]
    late = nonint[(nonint.date_utc >= start - pd.Timedelta(days=ms.LATE_DAYS)) & (nonint.date_utc < start)]
    G_pre, cpre = ms.count_games(pre)
    G_late, clate = ms.count_games(late)
    _, cyear = ms.count_games(nonint[nonint.date_utc.dt.year == start.year])
    rows = [{"event": "WLDs 2026", "champion": c, "G_ev": 1, "G_pre": G_pre, "G_late": G_late,
             "pick_pre": cpre["pick"].get(c, 0), "pick_late": clate["pick"].get(c, 0), "pick_ev": 0,
             "ban_pre": cpre["ban"].get(c, 0), "ban_late": clate["ban"].get(c, 0), "ban_ev": 0}
            for c in sorted(cyear["presence"])]
    D = ms.make_D(pd.DataFrame(rows), "pick")
    _, log1mp, _ = ms.loglik_terms(theta, D)

    def expected(G):
        return float((1.0 - (np.exp(G * log1mp) * ms.W_NORM[None, :]).sum(axis=1)).sum())

    Gs, cnt = np.unique(G_sims, return_counts=True)
    return {"G_pre": G_pre, "G_late": G_late, "universe": len(rows),
            "G_mean": float(G_sims.mean()),
            "expected_at_mean_G": expected(G_sims.mean()),
            "expected_over_sim_G": float(sum(expected(g) * c for g, c in zip(Gs, cnt)) / cnt.sum())}


def correction_variants(bt: pd.DataFrame) -> list[dict]:
    rv2 = float((bt.realized_sd ** 2).mean())
    sigma_model = float(np.sqrt(max(bt.resid.var(ddof=1) - rv2, 0.0)))
    worlds = bt[bt.event.str.startswith("WLDs")]

    def spec(name, sub):
        x = sub.resid.to_numpy()
        se = x.std(ddof=1) / np.sqrt(len(x))
        return {"variant": name, "n_events": len(x), "mu": float(x.mean()), "se_mu": float(se),
                "sd": float(np.sqrt(sigma_model ** 2 + se ** 2))}

    w_sub = worlds[worlds.event != "WLDs 2022"]
    primary = spec("Worlds 2022-25 (primary)", worlds)
    w_sd_plain = float(worlds.resid.std(ddof=1) * np.sqrt(1 + 1 / len(worlds)))
    return [
        primary,
        spec("Worlds 2023-25", w_sub),
        spec("All 11 events", bt),
        {"variant": "Worlds 2022-25, sd without realized-noise removal", "n_events": len(worlds),
         "mu": primary["mu"], "se_mu": primary["se_mu"], "sd": w_sd_plain},
        {"variant": "Previous manual -10 +/- 7 (check)", "n_events": None, "mu": -10.0, "se_mu": None, "sd": 7.0},
        {"variant": "No correction (raw draft sim)", "n_events": None, "mu": 0.0, "se_mu": None, "sd": 0.0},
    ], sigma_model


def bucket_mc(q, mu, sd, seed):
    rng = np.random.default_rng(seed)
    delta = mu + sd * rng.standard_normal((len(q), REPS))
    idx = np.digitize(np.round(q[:, None] + delta), EDGES)
    return np.bincount(idx.ravel(), minlength=len(LABELS)) / idx.size


def bucket_exact(q, mu, sd):
    """Analytic check: average over draft sims of the normal-CDF bucket probabilities."""
    hi = np.array(EDGES + [np.inf]) - 0.5
    lo = np.array([-np.inf] + EDGES) - 0.5
    m = q[:, None] + mu
    return (norm.cdf((hi[None, :] - m) / sd) - norm.cdf((lo[None, :] - m) / sd)).mean(axis=0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--rerun-draft", action="store_true", help="rerun the draft sim even if a saved run is current")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    df = ms.load_games()
    events, R_all, _, _ = ms.build_events(df)
    fit = ms.fit_variant(ms.make_D(R_all[R_all.year >= ms.FEARLESS_MIN_YEAR], "pick"), "pick/fearless")
    theta = fit["theta"]

    bt = backtest(events, R_all, theta)
    print("\nBacktest, closed-form pick model (actual - expected):")
    print(bt.round(2).to_string(index=False))

    q, src = draft_q10(force=args.rerun_draft)
    print(f"\nDraft sim input: {src}")
    G_sims = pd.read_csv(GAMES_FILE, usecols=["sim"]).groupby("sim").size().to_numpy()
    cf = closed_form_2026(theta, df, G_sims)
    print(f"\nWorlds 2026 closed form: G_pre {cf['G_pre']}, G_late {cf['G_late']}, universe {cf['universe']}, "
          f"mean G {cf['G_mean']:.2f}")
    print(f"  expected unique at mean G {cf['expected_at_mean_G']:.2f}, "
          f"averaged over sim G {cf['expected_over_sim_G']:.2f}")
    print(f"Draft sim (shifted): mean {q.mean():.2f}, sd {q.std(ddof=1):.2f}, median {np.median(q):.0f}, n {len(q)}")
    print(f"  gap draft - closed form (sim-G average): {q.mean() - cf['expected_over_sim_G']:+.2f}")

    variants, sigma_model = correction_variants(bt)
    print(f"\nModel-error sd (pooled over 11 events, realized binomial spread removed): {sigma_model:.2f}")
    out = []
    for v in variants:
        p = bucket_mc(q, v["mu"], v["sd"], args.seed) if v["sd"] > 0 else bucket_mc(q, v["mu"], 1e-9, args.seed)
        row = {**v, **{lab: round(float(x), 4) for lab, x in zip(LABELS, p)}, "sum": round(float(p.sum()), 6)}
        if v["sd"] > 0:
            ex = bucket_exact(q, v["mu"], v["sd"])
            row["max_abs_mc_minus_exact"] = round(float(np.abs(p - ex).max()), 4)
        out.append(row)
    res = pd.DataFrame(out)
    print(f"\nBucket probabilities (seed {args.seed}, {len(q)} sims x {REPS} noise draws):")
    print(res[["variant", "mu", "se_mu", "sd", *LABELS, "sum"]].round(4).to_string(index=False))
    print("MC vs analytic max abs diff:", res["max_abs_mc_minus_exact"].dropna().tolist())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bt.round(4).to_csv(BACKTEST_CSV, index=False)
    res.to_csv(BUCKETS_CSV, index=False)
    print("\nWrote", BACKTEST_CSV)
    print("Wrote", BUCKETS_CSV)


if __name__ == "__main__":
    main()
