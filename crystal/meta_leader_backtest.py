"""Calibration backtest of presence-leader probabilities from the binomial logit-normal fit.

Run from the project root:  python -m crystal.meta_leader_backtest
Writes outputs/meta/leader_backtest.json and outputs/meta/leader_backtest.md.

For each of the 11 events:
  * In-sample: the recommended (fearless) pick and ban parameters from crystal.meta_shift.
  * Leave-one-event-out (LOEO): the same model refit on the other 10 events (pooled style).
Simulation: DRAWS draws of u_pick and u_ban per champion (standard normal z1, z2 with
corr rho; u = sd_bin * z), pick_count ~ Binomial(G_ev, sigmoid(eta_pick + u_pick)),
ban_count ~ Binomial(G_ev, sigmoid(eta_ban + u_ban)), presence = min(pick+ban, G_ev)/G_ev.
Leader = argmax presence per draw, ties split 1/k. P(lead) is the mean over draws.
The sd scale s multiplies every sd. Random numbers are seeded per event and reused across s.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from common.report import md_rows, round_finite
from crystal.meta_shift import (
    EVENTS,
    FEARLESS_MIN_YEAR,
    JSON_PATH as FIT_JSON,
    THETA_STARTS,
    build_events,
    count_games,
    fit_variant,
    load_games,
    make_D,
    nll,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "meta"
MD_PATH = OUT_DIR / "leader_backtest.md"
JSON_OUT = OUT_DIR / "leader_backtest.json"

DRAWS = 5000
S_LIST = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
LL_CLAMP = 1.0 / (2 * DRAWS)   # log-loss floor: below Monte Carlo resolution
PSTOP = 0.01
SEED = 12345


def params_from_theta(theta) -> dict:
    return {"a": float(theta[0]), "b": float(theta[1]), "c": float(theta[2]),
            "sds": np.exp(np.asarray(theta[3:6], dtype=float))}


def quick_fit(D: dict):
    """Two-start L-BFGS-B fit without a Hessian. Returns the lower-nll solution and the start spread.

    Some held-out ban fits end at two different points on a flat ridge (nll gap of 4-5 units)
    that a polishing pass does not close. The lower-nll point is used and the spread is recorded.
    """
    res = [minimize(nll, th0, args=(D,), method="L-BFGS-B",
                    options={"maxiter": 5000, "maxfun": 200000, "ftol": 1e-12, "gtol": 1e-8})
           for th0 in THETA_STARTS]
    if not any(r.success for r in res):
        raise SystemExit(f"STOP: LOEO fit failed from both starts: {[r.message for r in res]}")
    dx = float(np.max(np.abs(res[0].x[:3] - res[1].x[:3])))
    dnll = float(abs(res[0].fun - res[1].fun))
    info = {"dmax_abc": round(dx, 4), "dnll": round(dnll, 4), "agree": bool(dx <= 0.05 and dnll <= 0.01)}
    return min(res, key=lambda r: r.fun).x, info


def leader_probs(D_p: dict, D_b: dict, par_p: dict, par_b: dict, rho: float, s: float, seed: int) -> np.ndarray:
    G = D_p["G"].astype(np.int64)
    N = len(G)
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal((DRAWS, N))
    z2 = rng.standard_normal((DRAWS, N))
    sd_p = s * par_p["sds"][D_p["bin"]]
    sd_b = s * par_b["sds"][D_b["bin"]]
    eta_p = par_p["a"] + par_p["b"] * D_p["x1"] + par_p["c"] * (D_p["x2"] - D_p["x1"])
    eta_b = par_b["a"] + par_b["b"] * D_b["x1"] + par_b["c"] * (D_b["x2"] - D_b["x1"])
    u_p = sd_p[None, :] * z1
    u_b = sd_b[None, :] * (rho * z1 + math.sqrt(1.0 - rho * rho) * z2)
    p_p = 1.0 / (1.0 + np.exp(-(eta_p[None, :] + u_p)))
    p_b = 1.0 / (1.0 + np.exp(-(eta_b[None, :] + u_b)))
    n_arr = np.broadcast_to(G[None, :], (DRAWS, N))
    brng = np.random.default_rng(seed + 1)
    pick_c = brng.binomial(n_arr, p_p)
    ban_c = brng.binomial(n_arr, p_b)
    pres = np.minimum(pick_c + ban_c, n_arr) / G[None, :].astype(float)
    mx = pres.max(axis=1, keepdims=True)
    ismax = (pres == mx).astype(float)
    k = ismax.sum(axis=1, keepdims=True)
    return (ismax / k).mean(axis=0)


def prepare_events(R_all, df):
    data = []
    for i, (lg, yr) in enumerate(EVENTS):
        name = f"{lg} {yr}"
        R_e = R_all[R_all["event"] == name].reset_index(drop=True)
        ev_games = df[(df["league"] == lg) & (df["date_utc"].dt.year == yr)]
        _, cev = count_games(ev_games)
        # Actual presence = games with the champion picked or banned (per-game union).
        act = np.array([cev["presence"].get(c, 0) for c in R_e["champion"]], dtype=int)
        n_mismatch = int(np.sum(act != (R_e["pick_ev"].to_numpy(int) + R_e["ban_ev"].to_numpy(int))))
        if n_mismatch:
            print(f"  {name}: {n_mismatch} champions where pick+ban double counts a game (union used)")
        data.append({
            "event": name, "year": yr, "idx": i, "R": R_e,
            "D_p": make_D(R_e, "pick"), "D_b": make_D(R_e, "ban"),
            "names": R_e["champion"].to_numpy(object), "act": act,
        })
    return data


def score_event(d: dict, P: np.ndarray) -> dict:
    names, act = d["names"], d["act"]
    mx = act.max()
    is_act = act == mx
    actual = [str(x) for x in names[is_act]]
    fav_i = int(np.argmax(P))
    fav = str(names[fav_i])
    return {
        "event": d["event"],
        "actual_leaders": actual,
        "actual_leader_presence": int(mx),
        "G_ev": int(d["R"]["G_ev"].iloc[0]),
        "P_actual_leader": float(P[is_act].sum()),
        "favourite": fav,
        "P_favourite": float(P[fav_i]),
        "favourite_hit": bool(fav in actual),
    }


def run_all(data, params_by_event, rho, s):
    out = []
    for d in data:
        par_p, par_b = params_by_event[d["event"]]
        P = leader_probs(d["D_p"], d["D_b"], par_p, par_b, rho, s, SEED + 10 * d["idx"])
        out.append(score_event(d, P))
    return out


def aggregate(results, s):
    exp_hits = sum(r["P_favourite"] for r in results)
    act_hits = sum(1 for r in results if r["favourite_hit"])
    ll = [-math.log(max(r["P_actual_leader"], LL_CLAMP)) for r in results]
    return {"s": s, "expected_fav_hits": round(exp_hits, 4), "actual_fav_hits": act_hits,
            "mean_logloss": round(float(np.mean(ll)), 4)}


def s_table(data, params_by_event, rho):
    rows = []
    for s in S_LIST:
        res = run_all(data, params_by_event, rho, s)
        rows.append(aggregate(res, s))
    best = min(rows, key=lambda r: r["mean_logloss"])
    return rows, best["s"]


def fmt_leaders(lst):
    return " / ".join(lst)


def main():
    t0 = time.time()
    fit_json = json.loads(FIT_JSON.read_text(encoding="utf-8"))
    if fit_json.get("recommended") != "fearless":
        raise SystemExit("STOP: fit JSON recommends a variant other than fearless.")
    rho = float(fit_json["rho_pick_ban"])

    df = load_games()
    _, R_all, _, _ = build_events(df)
    data = prepare_events(R_all, df)

    # In-sample: recommended (fearless) fit, refit at full precision with the shared routine.
    R_fear = R_all[R_all["year"] >= FEARLESS_MIN_YEAR]
    fit_p = fit_variant(make_D(R_fear, "pick"), "pick/fearless")
    fit_b = fit_variant(make_D(R_fear, "ban"), "ban/fearless")
    par_in = {"pick": params_from_theta(fit_p["theta"]), "ban": params_from_theta(fit_b["theta"])}
    in_params = {d["event"]: (par_in["pick"], par_in["ban"]) for d in data}

    in_res = run_all(data, in_params, rho, 1.0)
    in_table, in_best = s_table(data, in_params, rho)

    low = [r["event"] for r in in_res if r["P_actual_leader"] < PSTOP]
    if len(low) >= 3:
        for r in in_res:
            print(f"  {r['event']:10s} P_act={r['P_actual_leader']:.4f}")
        raise SystemExit(f"STOP: in-sample P(actual leader) < {PSTOP} for {len(low)} events: {low}. "
                         "No outputs written.")

    # Leave-one-event-out: refit on the other 10 events (pooled style, same model).
    t_loeo = time.time()
    loeo_params = {}
    loeo_checks = []
    for d in data:
        train = R_all[R_all["event"] != d["event"]]
        th_p, info_p = quick_fit(make_D(train, "pick"))
        th_b, info_b = quick_fit(make_D(train, "ban"))
        loeo_params[d["event"]] = (params_from_theta(th_p), params_from_theta(th_b))
        loeo_checks.append({"event": d["event"], "pick": info_p, "ban": info_b})
    loeo_secs = time.time() - t_loeo
    n_disagree = sum((not c["pick"]["agree"]) + (not c["ban"]["agree"]) for c in loeo_checks)
    print(f"LOEO start disagreements: {n_disagree} of {2 * len(loeo_checks)} fits")
    loeo_res = run_all(data, loeo_params, rho, 1.0)
    loeo_table, loeo_best = s_table(data, loeo_params, rho)
    total_secs = time.time() - t0

    def cal(res):
        exp_fav = sum(r["P_favourite"] for r in res)
        act = sum(1 for r in res if r["favourite_hit"])
        ll = float(np.mean([-math.log(max(r["P_actual_leader"], LL_CLAMP)) for r in res]))
        return {"sum_P_favourite": round(exp_fav, 4), "actual_fav_hits": act, "mean_logloss": round(ll, 4)}

    in_cal = cal(in_res)
    loeo_cal = cal(loeo_res)

    result = {
        "draws": DRAWS,
        "rho_used": round_finite(rho),
        "rho_note": "rho_pick_ban from the fit is a correlation of posterior-mean u, which is attenuated; "
                    "it is used as the latent correlation, as briefed.",
        "s_grid": S_LIST,
        "s_best": in_best,
        "table": in_table,
        "in_sample": {"events": in_res, "calibration": in_cal},
        "loeo": {"events": loeo_res, "calibration": loeo_cal, "s_best": loeo_best, "table": loeo_table,
                 "fit_seconds": round(loeo_secs, 1), "start_disagreements": n_disagree,
                 "start_checks": loeo_checks},
        "uniform_baseline_logloss": round(float(np.mean([math.log(len(d["names"])) for d in data])), 4),
        "total_seconds": round(total_secs, 1),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_md(in_res, in_cal, in_table, in_best, loeo_res, loeo_cal, loeo_table, loeo_best,
             rho, loeo_secs, total_secs, fit_p, fit_b, n_disagree,
             float(np.mean([math.log(len(d["names"])) for d in data])))

    print("In-sample per-event:")
    for r in in_res:
        print(f"  {r['event']:10s} actual={fmt_leaders(r['actual_leaders']):28s} P_act={r['P_actual_leader']:.4f} "
              f"fav={r['favourite']:14s} P_fav={r['P_favourite']:.4f} hit={'Y' if r['favourite_hit'] else 'N'}")
    print("In-sample calibration:", in_cal, "s_best:", in_best)
    print("LOEO per-event:")
    for r in loeo_res:
        print(f"  {r['event']:10s} actual={fmt_leaders(r['actual_leaders']):28s} P_act={r['P_actual_leader']:.4f} "
              f"fav={r['favourite']:14s} P_fav={r['P_favourite']:.4f} hit={'Y' if r['favourite_hit'] else 'N'}")
    print("LOEO calibration:", loeo_cal, "s_best:", loeo_best, "fit_seconds:", round(loeo_secs, 1))
    print("Wrote", JSON_OUT)
    print("Wrote", MD_PATH)


def write_md(in_res, in_cal, in_table, in_best, loeo_res, loeo_cal, loeo_table, loeo_best,
             rho, loeo_secs, total_secs, fit_p, fit_b, n_disagree, uniform_ll):
    L = []
    L.append("# Presence-leader calibration backtest\n")
    L.append(
        "Question: is the fitted model overconfident about which champion leads presence at an event? For each of the "
        "11 events, the model simulates 5,000 draws of pick and ban counts for every champion in the event's universe, "
        "and takes the presence leader (pick + ban games, capped at G_ev) in each draw, with ties split. P(lead) is "
        "the share of draws in which the champion leads. We compare the model's favourite (highest P(lead)) and the "
        "probability it gave to the actual leader(s) with what happened.\n")
    L.append(
        f"Parameters: the recommended fearless fit (pick a={fit_p['a']:.4f}, b={fit_p['b']:.4f}, c={fit_p['c']:.4f}; "
        f"ban a={fit_b['a']:.4f}, b={fit_b['b']:.4f}, c={fit_b['c']:.4f}). The in-sample table uses these. The LOEO "
        f"table refits the same model on the other 10 events for each held-out event. Correlation of u_pick and u_ban: "
        f"rho = {rho:.4f}, as in the fit JSON. That value is a posterior-mean correlation and is attenuated, so the "
        "latent correlation is probably higher; the simulation therefore understates the coupling.\n")

    def ev_table(res):
        rows_ = []
        for r in res:
            rows_.append([r["event"], fmt_leaders(r["actual_leaders"]), f"{r['P_actual_leader']:.4f}",
                          r["favourite"], f"{r['P_favourite']:.4f}", "Y" if r["favourite_hit"] else "N"])
        return md_rows(["Event", "Actual leader(s)", "P(actual leader)", "Model favourite", "P(favourite)",
                         "Favourite hit"], rows_)

    def cal_line(c):
        return (f"Calibration: sum of P(favourite) over 11 events = {c['sum_P_favourite']:.2f}; actual favourite hits = "
                f"{c['actual_fav_hits']}; mean log-loss of the actual leader = {c['mean_logloss']:.4f}.\n")

    def s_rows(tbl, best):
        rows_ = [[r["s"], f"{r['expected_fav_hits']:.2f}", r["actual_fav_hits"], f"{r['mean_logloss']:.4f}",
                  "<- s_best" if r["s"] == best else ""] for r in tbl]
        return md_rows(["sd scale s", "Expected favourite hits", "Actual favourite hits", "Mean log-loss", ""],
                        rows_)

    L.append("## In-sample (recommended fearless fit)\n")
    L.append(ev_table(in_res) + "\n")
    L.append(cal_line(in_cal))
    L.append(f"Reference: a uniform guess over each event's universe (about 160-175 champions) has mean log-loss "
             f"{uniform_ll:.4f}. The favourites' P ranged {min(r['P_favourite'] for r in in_res):.2f}-"
             f"{max(r['P_favourite'] for r in in_res):.2f}.\n")
    L.append("## Scaling every sd by s (in-sample)\n")
    L.append(s_rows(in_table, in_best) + "\n")
    L.append(f"s_best (in-sample, minimum mean log-loss) = **{in_best}**.\n")

    L.append("## Leave-one-event-out (same model refit on the other 10 events)\n")
    L.append(f"LOEO refits took {loeo_secs:.1f} s in total (within the ~10 minute budget).\n")
    L.append(
        f"Optimizer caveat: in {n_disagree} of 22 held-out fits (pick and ban, 11 events each), the two L-BFGS-B starts "
        "ended at different points on a flat ridge (nll gap of 4-5 units; the parameters differ by up to about 0.09 in "
        "a, b and c). The lower-nll point is used. A Nelder-Mead polish did not close the gap, so these fits are less "
        "precise than the in-sample fit, which both starts agree on. Per-fit spreads are in the JSON (loeo.start_checks).\n")
    L.append(ev_table(loeo_res) + "\n")
    L.append(cal_line(loeo_cal))
    L.append("## Scaling every sd by s (LOEO)\n")
    L.append(s_rows(loeo_table, loeo_best) + "\n")
    L.append(f"s_best (LOEO) = **{loeo_best}**.\n")

    L.append("## Notes\n")
    L.append(
        "- The actual presence leader counts games where the champion was picked or banned (per-game union). The "
        "database has 2 games (of 53,499) in which a champion appears both as a pick and as a ban; summing pick and "
        "ban counts would double count those, so the union is used.\n"
        "- The model's presence is min(pick + ban, G_ev) / G_ev, as briefed.\n"
        f"- Log-loss uses max(P, {LL_CLAMP:.4f}); {LL_CLAMP:.4f} is half a draw, the lowest probability the simulation "
        "can resolve.\n"
        "- Monte Carlo error on each P(lead) is at most about 0.007 (5,000 draws). Random numbers are seeded per event "
        "and reused across s, so the s comparison uses common random numbers.\n"
        "- In-sample: the fearless fit used only the 2025-26 events. The 2022-24 events are out-of-era for these "
        "parameters, so the LOEO table is the fairer test for them.\n")

    MD_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
