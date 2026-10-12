"""Round-5 diagnosis: why is the across-sim sd of a champion's ban rate 1.3-1.5x the GLMM sd?

Scratch diagnostic (not a deliverable). Imports crystal.draft and drives its internal functions
exactly as run_draft does, with masks applied to the shift arrays (no change to draft.py).
Writes outputs/draft/spread_diagnosis.md.
"""
import sys
import types
import pickle

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Python\LOL_PICKEMS")
import crystal.draft as d  # noqa: E402

CH = ["Cassiopeia", "Nocturne", "Vi", "Jarvan IV"]
K = 15.0
SEED = 7
G_N = 103
E_BUMP = 0.25
OUT = d.OUT_DIR / "spread_diagnosis.md"

games_all = pd.read_csv(d.GAMES_FILE)


def setup(sims):
    games = games_all[games_all.sim < sims]
    b = d._base()
    ctx = d._context(K)
    fit = d._fit_params()
    M = d._marg(fit, b)
    cal_games = games_all[games_all.sim < d.CAL_SIMS]
    Gcal = d._game_arrays(cal_games, b.tix)
    logm, logmb, _, _, hist = d._calibrate(Gcal, ctx, M.pi_t, M.be_t)
    G = d._game_arrays(games, b.tix)
    rng = np.random.default_rng(SEED)
    shp, shb = d._shift_draws(fit, b, G.n_sims, rng, M)
    return dict(b=b, ctx=ctx, fit=fit, M=M, logm=logm, logmb=logmb, G=G, shp=shp, shb=shb,
                cal_iters=len(hist) - 1)


def run(st, shp, shb, lock=True):
    G = st["G"]
    if not lock:  # fearless off: no series locks
        G = types.SimpleNamespace(**G.__dict__)
        G.bo3 = np.zeros_like(st["G"].bo3)
    res = d._simulate(G, st["ctx"], st["logm"], st["logmb"], shp, shb, seed=SEED + 1000)
    return res.bans / res.games[:, None]


def main():
    lines = []
    st = setup(1000)
    b, M = st["b"], st["M"]
    idx = {c: b.cidx[c] for c in CH}
    glmm = {c: d._glmm_sd_marginal(float(M.lb0[idx[c]] + M.db), float(M.sdb[idx[c]])) for c in CH}
    zero = np.zeros_like(st["shp"])

    # A: baseline, same setup as the round-4 run (1,000 sims)
    rA = run(st, st["shp"], st["shb"])
    sdA = {c: rA[:, idx[c]].std(ddof=1) for c in CH}

    # D: no shift at all (draft noise floor), CRN seed
    rD = run(st, zero, zero)
    sdD = {c: rD[:, idx[c]].std(ddof=1) for c in CH}
    mD = {c: rD[:, idx[c]].mean() for c in CH}
    floorD = {c: np.sqrt(mD[c] * (1 - mD[c]) / G_N) for c in CH}

    # B: random shift only on the target champion (others 0), one run per champion
    sdB = {}
    for c in CH:
        j = idx[c]
        shp_b, shb_b = np.zeros_like(st["shp"]), np.zeros_like(st["shb"])
        shp_b[:, j] = st["shp"][:, j]
        shb_b[:, j] = st["shb"][:, j]
        rB = run(st, shp_b, shb_b)
        sdB[c] = rB[:, j].std(ddof=1)

    # C: fearless off, shift on for all champions
    rC = run(st, st["shp"], st["shb"], lock=False)
    sdC = {c: rC[:, idx[c]].std(ddof=1) for c in CH}

    # F: ban-side shift only (pick shift 0); G: pick-side shift only (ban shift 0)
    rF = run(st, zero, st["shb"])
    sdF = {c: rF[:, idx[c]].std(ddof=1) for c in CH}
    rG = run(st, st["shp"], zero)
    sdG = {c: rG[:, idx[c]].std(ddof=1) for c in CH}

    # H: no shift, fearless off (isolates the within-series ban correlation from fearless locks)
    rH = run(st, zero, zero, lock=False)
    sdH = {c: rH[:, idx[c]].std(ddof=1) for c in CH}
    mH = {c: rH[:, idx[c]].mean() for c in CH}

    # E: slope amplification at baseline: +0.25 log-weight on the target's ban weight only
    amp, slope = {}, {}
    for c in CH:
        j = idx[c]
        shb_e = np.zeros_like(st["shb"])
        shb_e[:, j] = E_BUMP
        rE = run(st, zero, shb_e)
        slope[c] = (rE[:, j].mean() - mD[c]) / E_BUMP
        amp[c] = slope[c] / (mD[c] * (1 - mD[c]))

    # Reproduction check at the full 5,000-sim setting (must equal the round-4 deliverable)
    st5 = setup(5000)
    r5 = run(st5, st5["shp"], st5["shb"])
    b5 = st5["b"]
    M5 = st5["M"]
    rep = {}
    for c in CH:
        j = b5.cidx[c]
        g5 = d._glmm_sd_marginal(float(M5.lb0[j] + M5.db), float(M5.sdb[j]))
        rep[c] = r5[:, j].std(ddof=1) / g5

    with open(d.OUT_DIR / "tmp_run_k15_shift_s5000.pkl", "rb") as fh:
        round4 = pickle.load(fh)
    r4 = round4["spread"].set_index("champion")["ratio_sim_to_glmm"]

    lines.append("# Spread diagnosis: across-tournament sd of the ban rate vs the GLMM sd\n")
    lines.append("Scratch diagnostic `outputs/draft/tmp_spread_diag.py`. Same calibration as the main run "
                 "(500 sims, marginal targets, common shift). Experiments use 1,000 sims unless stated. "
                 "Ratios are sim sd / GLMM sd (marginal formulation, G = 103). sd values are in percentage points.\n")
    lines.append("## Reproduction check (experiment A at the round-4 setting)\n")
    rows = []
    for c in CH:
        rows.append({"champion": c, "round-4 ratio (5,000)": f"{r4[c]:.4f}",
                     "rerun ratio (5,000)": f"{rep[c]:.4f}", "diff": f"{rep[c] - r4[c]:+.4f}",
                     "A ratio (1,000)": f"{sdA[c] / glmm[c]:.3f}",
                     "A vs round-4 within 0.1": "yes" if abs(sdA[c] / glmm[c] - r4[c]) <= 0.1 else "NO"})
    lines.append(d._md_table(pd.DataFrame(rows)) + "\n")
    repro_ok = all(abs(rep[c] - r4[c]) < 1e-9 for c in CH)
    lines.append(f"5,000-sim rerun identical to the round-4 deliverable: {repro_ok}.\n")

    lines.append("## Experiments\n")
    lines.append("A: baseline. B: random shift only on the target (others 0). C: fearless off (shift on). "
                 "D: no shift (draft noise floor). E: slope amplification (+0.25 log-weight on the target's ban "
                 "weight at baseline; slope / p(1-p)). F: ban-side shift only. G: pick-side shift only.\n")
    table = []
    for c in CH:
        table.append({
            "champion": c,
            "GLMM sd (pp)": f"{100 * glmm[c]:.2f}",
            "A ratio": f"{sdA[c] / glmm[c]:.3f}",
            "B ratio (target only)": f"{sdB[c] / glmm[c]:.3f}",
            "C ratio (fearless off)": f"{sdC[c] / glmm[c]:.3f}",
            "D sd (pp, no shift)": f"{100 * sdD[c]:.2f}",
            "binomial floor (pp)": f"{100 * floorD[c]:.2f}",
            "D / floor": f"{sdD[c] / floorD[c]:.3f}",
            "E amplification": f"{amp[c]:.3f}",
            "F ratio (ban shift only)": f"{sdF[c] / glmm[c]:.3f}",
            "G ratio (pick shift only)": f"{sdG[c] / glmm[c]:.3f}",
            "H sd (pp, no shift, fearless off)": f"{100 * sdH[c]:.2f}",
            "H / floor": f"{sdH[c] / floorD[c]:.3f}",
        })
    lines.append(d._md_table(pd.DataFrame(table)) + "\n")
    lines.append("## Variance decomposition (tournament part)\n")
    dec = []
    for c in CH:
        tau_g = np.sqrt(glmm[c] ** 2 - floorD[c] ** 2)
        tau_s = np.sqrt(max(sdA[c] ** 2 - sdD[c] ** 2, 0.0))
        dec.append({
            "champion": c,
            "GLMM tournament sd (pp) = sqrt(GLMM^2 - floor^2)": f"{100 * tau_g:.2f}",
            "sim tournament sd (pp) = sqrt(A^2 - D^2)": f"{100 * tau_s:.2f}",
            "ratio": f"{tau_s / tau_g:.3f}",
            "E slope amplification": f"{amp[c]:.3f}",
        })
    lines.append(d._md_table(pd.DataFrame(dec)) + "\n")
    lines.append("Mean ban rates, no shift, fearless off (pp): " + ", ".join(
        f"{c} {100 * mH[c]:.2f}" for c in CH) + ".\n")
    lines.append("Baseline no-shift mean ban rates (pp): " + ", ".join(
        f"{c} {100 * mD[c]:.2f}" for c in CH) + ". E slope (dp per unit log-weight): " + ", ".join(
        f"{c} {slope[c]:.4f}" for c in CH) + ". Calibrated shift-run means (A, pp): " + ", ".join(
        f"{c} {100 * rA[:, idx[c]].mean():.2f}" for c in CH) + ".\n")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print("A ratio", {c: round(sdA[c] / glmm[c], 3) for c in CH})
    print("rep 5000", {c: round(rep[c], 4) for c in CH}, "round4", {c: round(r4[c], 4) for c in CH})
    print("B", {c: round(sdB[c] / glmm[c], 3) for c in CH})
    print("C", {c: round(sdC[c] / glmm[c], 3) for c in CH})
    print("D sd", {c: round(100 * sdD[c], 2) for c in CH}, "floor", {c: round(100 * floorD[c], 2) for c in CH})
    print("E amp", {c: round(amp[c], 3) for c in CH}, "slope", {c: round(slope[c], 4) for c in CH})
    print("F", {c: round(sdF[c] / glmm[c], 3) for c in CH}, "G", {c: round(sdG[c] / glmm[c], 3) for c in CH})
    print("H sd", {c: round(100 * sdH[c], 2) for c in CH}, "H/floor", {c: round(sdH[c] / floorD[c], 3) for c in CH})
    print("glmm", {c: round(100 * glmm[c], 2) for c in CH}, "cal iters", st["cal_iters"])


if __name__ == "__main__":
    main()
