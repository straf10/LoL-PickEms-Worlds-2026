"""Meta-shift model: how champion pick and ban rates at an international event differ
from (a) the top-league pre-window (60 days before the event) and (b) a late read
from all non-international leagues (21 days before the event).

Run from the project root:  python -m crystal.meta_shift
Writes outputs/meta/meta_shift_fit.json and outputs/meta/meta_shift_report.md.

Model, fitted separately for pick and ban:
  event_count ~ Binomial(G_ev, sigmoid(a + b*x1 + c*(x2 - x1) + u)),
  u ~ Normal(0, sd_bin^2), sd_bin chosen by the pre-rate bin of x1 (lt5, 5to20, gt20).
  x1 = logit((pre_count + 0.5)/(G_pre + 1))    top leagues, 60 days before start
  x2 = logit((late_count + 0.5)/(G_late + 1))  all non-international leagues, 21 days before start
  Universe per event: every champion picked or banned in any non-international game of
  that calendar year, or in the event itself (zeros in both windows are kept).
  The event side has no smoothing: the binomial likelihood handles zeros.
  u is integrated with 20-node Gauss-Hermite quadrature; the log-likelihood is maximized
  with L-BFGS-B from two starting points. Standard errors come from the inverse of a
  central finite-difference Hessian of the negative log-likelihood (step 1e-3).

The previous smoothed-OLS fit is kept under "smoothed_fit_v1" in the JSON.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from numpy.polynomial.hermite import hermgauss
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pickems.duckdb"
OUT_DIR = ROOT / "outputs" / "meta"
JSON_PATH = OUT_DIR / "meta_shift_fit.json"
REPORT_PATH = OUT_DIR / "meta_shift_report.md"

PRE_DAYS = 60
LATE_DAYS = 21
DOMESTIC = {"LCK", "LPL", "LEC", "LCS", "LCP", "PCS", "VCS", "CBLOL", "LJL"}
EVENTS = (
    [("WLDs", y) for y in (2022, 2023, 2024, 2025)]
    + [("MSI", y) for y in (2022, 2023, 2024, 2025, 2026)]
    + [("FST", 2025), ("FST", 2026)]
)
METRICS = ("pick", "ban")
BINS = ("lt5", "5to20", "gt20")
FEARLESS_MIN_YEAR = 2025
C_SE_THRESHOLD = 0.3
SD_MIN, SD_MAX = 0.05, 3.0
GH_NODES, GH_WTS = hermgauss(20)
NODES_Z = math.sqrt(2.0) * GH_NODES          # standard-normal quadrature nodes
W_NORM = GH_WTS / math.sqrt(math.pi)         # weights summing to 1
THETA_STARTS = [
    np.array([-1.0, 0.5, 0.0, math.log(0.5), math.log(0.5), math.log(0.5)]),
    np.array([0.0, 0.2, 0.3, math.log(1.0), math.log(1.0), math.log(1.0)]),
]
CONV_TOL_PARAM = 0.05
CONV_TOL_NLL = 0.01


def is_domestic(league: str) -> bool:
    return league in DOMESTIC or league.startswith("LTA")


def tokens(text) -> set[str]:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return set()
    return {t.strip() for t in str(text).split(",") if t.strip()}


def logit(p):
    p = np.asarray(p, dtype=float)
    return np.log(p / (1.0 - p))


def load_games() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = con.execute(
            """SELECT game_id, league, date_utc, is_international,
                      blue_picks, red_picks, blue_bans, red_bans
               FROM games"""
        ).df()
    finally:
        con.close()
    df["date_utc"] = pd.to_datetime(df["date_utc"])
    assert df["is_international"].notna().all(), "is_international has NULLs"
    assert df["game_id"].is_unique, "game_id is not unique"
    return df


def count_games(g: pd.DataFrame):
    cnt = {m: Counter() for m in ("pick", "ban", "presence")}
    for bp, rp, bb, rb in zip(g["blue_picks"], g["red_picks"], g["blue_bans"], g["red_bans"]):
        picks = tokens(bp) | tokens(rp)
        bans = tokens(bb) | tokens(rb)
        cnt["pick"].update(picks)
        cnt["ban"].update(bans)
        cnt["presence"].update(picks | bans)
    return len(g), cnt


def leader(counts: dict) -> str:
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def rank_of(champ, counts: dict) -> int:
    v = counts[champ]
    return 1 + sum(1 for c in counts.values() if c > v)


def leader_check_event(name, cpre, cev, notes):
    champs = set(cpre["presence"]) | set(cev["presence"])
    pre_pres = {c: cpre["presence"].get(c, 0) for c in champs}
    ev_pres = {c: cev["presence"].get(c, 0) for c in champs}
    pre_pick = {c: cpre["pick"].get(c, 0) for c in champs}
    ev_pick = {c: cev["pick"].get(c, 0) for c in champs}
    pres_leader = leader(ev_pres)
    pre_leader = leader(pre_pres)
    pick_leader = leader(ev_pick)
    ties = sum(1 for v in ev_pres.values() if v == max(ev_pres.values()))
    if ties > 1:
        notes.append(f"{name}: {ties} champions tied for the event presence lead (alphabetical tie-break).")
    return {
        "event": name,
        "presence_leader": pres_leader,
        "its_pre_rank": rank_of(pres_leader, pre_pres),
        "pre_leader": pre_leader,
        "its_event_rank": rank_of(pre_leader, ev_pres),
        "pick_leader": pick_leader,
        "its_pre_rank_pick": rank_of(pick_leader, pre_pick),
    }


def build_events(df: pd.DataFrame):
    intl = df["is_international"].astype(bool)
    dom = df[(~intl) & df["league"].map(is_domestic)]
    nonint = df[~intl]
    events, rows, lc, notes = [], [], [], []
    for lg, yr in EVENTS:
        ev = df[(df["league"] == lg) & (df["date_utc"].dt.year == yr)]
        start = ev["date_utc"].min()
        pre = dom[(dom["date_utc"] >= start - pd.Timedelta(days=PRE_DAYS)) & (dom["date_utc"] < start)]
        late = nonint[(nonint["date_utc"] >= start - pd.Timedelta(days=LATE_DAYS))
                      & (nonint["date_utc"] < start)]
        year_nonint = nonint[nonint["date_utc"].dt.year == yr]
        G_pre, cpre = count_games(pre)
        G_late, clate = count_games(late)
        G_ev, cev = count_games(ev)
        _, cyear = count_games(year_nonint)
        name = f"{lg} {yr}"
        universe = sorted(set(cev["presence"]) | set(cyear["presence"]))
        events.append({
            "event": name, "league": lg, "year": yr, "start": start.date().isoformat(),
            "G_pre": G_pre, "G_ev": G_ev, "G_late": G_late,
            "leagues_pre": sorted(pre["league"].unique().tolist()),
            "universe_size": len(universe),
            "unique_picked_actual": len(cev["pick"]),
        })
        for c in universe:
            rows.append({
                "event": name, "year": yr, "champion": c,
                "G_ev": G_ev, "G_pre": G_pre, "G_late": G_late,
                "pick_pre": cpre["pick"].get(c, 0), "pick_late": clate["pick"].get(c, 0),
                "pick_ev": cev["pick"].get(c, 0),
                "ban_pre": cpre["ban"].get(c, 0), "ban_late": clate["ban"].get(c, 0),
                "ban_ev": cev["ban"].get(c, 0),
            })
        lc.append(leader_check_event(name, cpre, cev, notes))
    return events, pd.DataFrame(rows), lc, notes


def make_D(R: pd.DataFrame, m: str) -> dict:
    G_pre = R["G_pre"].to_numpy(float)
    G_late = R["G_late"].to_numpy(float)
    G = R["G_ev"].to_numpy(float)
    p_pre = (R[f"{m}_pre"].to_numpy(float) + 0.5) / (G_pre + 1.0)
    p_late = (R[f"{m}_late"].to_numpy(float) + 0.5) / (G_late + 1.0)
    y = R[f"{m}_ev"].to_numpy(float)
    return {
        "x1": logit(p_pre),
        "x2": logit(p_late),
        "bin": np.where(p_pre < 0.05, 0, np.where(p_pre <= 0.20, 1, 2)).astype(int),
        "y": y,
        "G": G,
        "const": gammaln(G + 1.0) - gammaln(y + 1.0) - gammaln(G - y + 1.0),
        "event": R["event"].to_numpy(object),
    }


def subset(D: dict, mask) -> dict:
    return {k: v[mask] for k, v in D.items()}


def loglik_terms(theta, D):
    a, b, c = theta[0], theta[1], theta[2]
    sds = np.exp(theta[3:6])
    sd_row = sds[D["bin"]]
    eta0 = a + b * D["x1"] + c * (D["x2"] - D["x1"])
    E = eta0[:, None] + sd_row[:, None] * NODES_Z[None, :]
    logp = -np.logaddexp(0.0, -E)
    log1mp = -np.logaddexp(0.0, E)
    y = D["y"][:, None]
    G = D["G"][:, None]
    logbin = y * logp + (G - y) * log1mp + D["const"][:, None]
    terms = logbin + np.log(W_NORM)[None, :]
    return terms, log1mp, sd_row


def nll(theta, D) -> float:
    terms, _, _ = loglik_terms(theta, D)
    return float(-logsumexp(terms, axis=1).sum())


def hessian_fd(f, x, h=1e-3):
    k = len(x)
    H = np.zeros((k, k))
    for i in range(k):
        for j in range(i, k):
            ei = np.zeros(k)
            ej = np.zeros(k)
            ei[i] = h
            ej[j] = h
            if i == j:
                H[i, i] = (f(x + ei) - 2.0 * f(x) + f(x - ei)) / (h * h)
            else:
                H[i, j] = (f(x + ei + ej) - f(x + ei - ej) - f(x - ei + ej) + f(x - ei - ej)) / (4.0 * h * h)
                H[j, i] = H[i, j]
    return H


def fit_variant(D: dict, label: str) -> dict:
    results = [minimize(nll, th0, args=(D,), method="L-BFGS-B",
                        options={"maxiter": 5000, "maxfun": 200000, "ftol": 1e-12, "gtol": 1e-8})
               for th0 in THETA_STARTS]
    for i, r in enumerate(results):
        print(f"  [{label}] start {i}: success={r.success} nll={r.fun:.4f} "
              f"theta={np.round(r.x, 4).tolist()} msg={r.message}")
    if not all(r.success for r in results):
        raise SystemExit(f"STOP: optimizer did not converge from both starts for {label}.")
    dx = float(np.max(np.abs(results[0].x[:3] - results[1].x[:3])))
    dnll = float(abs(results[0].fun - results[1].fun))
    if dx > CONV_TOL_PARAM or dnll > CONV_TOL_NLL:
        raise SystemExit(f"STOP: starts disagree for {label} (max|da,b,c|={dx:.4f}, dnll={dnll:.4f}).")
    best = min(results, key=lambda r: r.fun)
    theta = best.x
    H = hessian_fd(lambda t: nll(t, D), theta)
    cov = np.linalg.inv(H)
    if np.any(np.diag(cov) <= 0) or not np.all(np.isfinite(cov)):
        raise SystemExit(f"STOP: Hessian not positive definite for {label}.")
    se = np.sqrt(np.diag(cov))[:3]
    sds = np.exp(theta[3:6])
    if np.any(sds < SD_MIN) or np.any(sds > SD_MAX):
        raise SystemExit(f"STOP: sd outside [{SD_MIN}, {SD_MAX}] for {label}: {sds.round(4).tolist()}.")
    return {
        "theta": theta,
        "a": float(theta[0]), "b": float(theta[1]), "c": float(theta[2]),
        "sd_by_bin": {k: float(sds[i]) for i, k in enumerate(BINS)},
        "se": {"a": float(se[0]), "b": float(se[1]), "c": float(se[2])},
        "n": int(len(D["y"])),
        "loglik": float(-best.fun),
        "starts": {"dmax_abc": dx, "dnll": dnll},
    }


def posterior_u(theta, D) -> np.ndarray:
    terms, _, sd_row = loglik_terms(theta, D)
    w = np.exp(terms - logsumexp(terms, axis=1, keepdims=True))
    return (w * (sd_row[:, None] * NODES_Z[None, :])).sum(axis=1)


def expected_unique_by_event(theta, D: dict, name_list) -> dict:
    out = {}
    for name in name_list:
        Ds = subset(D, D["event"] == name)
        _, log1mp, _ = loglik_terms(theta, Ds)
        Ep = (np.exp(Ds["G"][:, None] * log1mp) * W_NORM[None, :]).sum(axis=1)
        out[name] = float((1.0 - Ep).sum())
    return out


def fmt(x, nd=4):
    x = float(x)
    assert math.isfinite(x), f"non-finite value {x}"
    return round(x, nd)


def block(f: dict) -> dict:
    return {
        "a": fmt(f["a"]), "b": fmt(f["b"]), "c": fmt(f["c"]),
        "sd_by_bin": {k: fmt(f["sd_by_bin"][k]) for k in BINS},
        "se": {k: fmt(f["se"][k]) for k in ("a", "b", "c")},
        "n": int(f["n"]),
        "loglik": fmt(f["loglik"], 4),
    }


def load_smoothed_v1():
    if not JSON_PATH.exists():
        return None
    old = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if old.get("model") == "binomial-logitnormal":
        return old.get("smoothed_fit_v1")
    return old


def f4(x):
    return f"{float(x):.4f}"


def md_table(headers, rows_):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows_:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(lines)


def main() -> None:
    df = load_games()
    events, R_all, lc, lc_notes = build_events(df)
    print("Events, windows and universe sizes:")
    for e in events:
        print(f"  {e['event']:10s} G_pre={e['G_pre']:4d} G_ev={e['G_ev']:4d} G_late={e['G_late']:5d} "
              f"universe={e['universe_size']:4d} unique_picked={e['unique_picked_actual']}")

    fear_mask = R_all["year"].to_numpy() >= FEARLESS_MIN_YEAR
    variants = {"fearless": R_all[fear_mask], "pooled": R_all}
    fits = {"fearless": {}, "pooled": {}}
    for vname, R in variants.items():
        for m in METRICS:
            D = make_D(R, m)
            print(f"Fitting {m} ({vname}, rows={len(D['y'])})")
            fits[vname][m] = fit_variant(D, f"{m}/{vname}")

    use_pooled = any(fits["fearless"][m]["se"]["c"] > C_SE_THRESHOLD
                     and fits["pooled"][m]["se"]["c"] < C_SE_THRESHOLD for m in METRICS)
    recommended = "pooled" if use_pooled else "fearless"
    rec_R = variants[recommended]
    rec = fits[recommended]

    D_rec_pick = make_D(rec_R, "pick")
    D_rec_ban = make_D(rec_R, "ban")
    u_pick = posterior_u(rec["pick"]["theta"], D_rec_pick)
    u_ban = posterior_u(rec["ban"]["theta"], D_rec_ban)
    rho = float(np.corrcoef(u_pick, u_ban)[0, 1])

    # Sanity: expected unique picked per event under the recommended pick model (all events).
    D_all_pick = make_D(R_all, "pick")
    names = [e["event"] for e in events]
    exp_unique = expected_unique_by_event(rec["pick"]["theta"], D_all_pick, names)
    for e in events:
        e["unique_picked_expected"] = fmt(exp_unique[e["event"]])

    v1 = load_smoothed_v1()

    result = {
        "model": "binomial-logitnormal",
        "pre_window_days": PRE_DAYS,
        "late_window_days": LATE_DAYS,
        "late_leagues": "all non-international",
        "recommended": recommended,
        "pick": block(rec["pick"]),
        "ban": block(rec["ban"]),
        "rho_pick_ban": fmt(rho),
        "fearless": {m: block(fits["fearless"][m]) for m in METRICS},
        "pooled": {m: block(fits["pooled"][m]) for m in METRICS},
        "events": events,
        "leader_check": lc,
        "smoothed_fit_v1": v1,
        "sd_note": "sd is the event-specific shift; binomial event noise is excluded (the draft sim regenerates it)",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_report(events, fits, recommended, rho, lc, lc_notes, exp_unique)

    print("\nRecommended:", recommended, "| rho_pick_ban =", round(rho, 4))
    for vname in ("fearless", "pooled"):
        for m in METRICS:
            f = fits[vname][m]
            print(f"  {vname:9s} {m:5s} a={f['a']:.4f} b={f['b']:.4f} c={f['c']:.4f} "
                  f"se(a,b,c)=({f['se']['a']:.4f},{f['se']['b']:.4f},{f['se']['c']:.4f}) "
                  f"sd={ {k: round(v, 4) for k, v in f['sd_by_bin'].items()} } n={f['n']} loglik={f['loglik']:.3f}")
    print("Wrote", JSON_PATH)
    print("Wrote", REPORT_PATH)


def write_report(events, fits, recommended, rho, lc, lc_notes, exp_unique):
    rec = fits[recommended]
    L = []
    L.append("# Meta shift: binomial logit-normal fit (top-league pre-window + late any-league read)\n")
    L.append(
        "Model, separately for pick and ban: event_count ~ Binomial(G_ev, sigmoid(a + b*x1 + c*(x2 - x1) + u)), "
        "u ~ Normal(0, sd^2) with sd chosen by the pre-rate bin of x1. x1 is the logit of the smoothed top-league "
        "60-day pre-window rate; x2 is the logit of the smoothed late 21-day rate across all non-international "
        "leagues. Each event's universe is every champion picked or banned in any non-international game of that "
        "calendar year or in the event, so zero-count champions are kept. Event counts are not smoothed. "
        "u is integrated with 20-node Gauss-Hermite quadrature and the likelihood is maximized with L-BFGS-B from two "
        "starts (they agree on a, b, c and the log-likelihood). Standard errors come from the inverse of a central "
        "finite-difference Hessian of the negative log-likelihood (step 1e-3). The sd values are the event-specific "
        "shift; binomial event noise is excluded because the draft sim regenerates it.\n")
    L.append(f"Recommended variant: **{recommended}**. Fearless = 2025-26 events (5 events). Pooled = all 11 events.\n")

    L.append("## Fit table\n")
    rows_ = []
    for vname in ("fearless", "pooled"):
        for m in METRICS:
            f = fits[vname][m]
            tag = " (rec)" if (vname == recommended) else ""
            rows_.append([f"{m} {vname}{tag}",
                          f"{f4(f['a'])} ({f4(f['se']['a'])})",
                          f"{f4(f['b'])} ({f4(f['se']['b'])})",
                          f"{f4(f['c'])} ({f4(f['se']['c'])})",
                          f4(f["sd_by_bin"]["lt5"]), f4(f["sd_by_bin"]["5to20"]), f4(f["sd_by_bin"]["gt20"]),
                          f["n"], f"{f['loglik']:.2f}"])
    L.append(md_table(["Fit", "a (SE)", "b (SE)", "c (SE)", "sd lt5", "sd 5to20", "sd gt20", "n", "loglik"], rows_))
    L.append("")

    L.append("## What c says\n")
    for m in METRICS:
        f = rec[m]
        b, c, se_c = f["b"], f["c"], f["se"]["c"]
        pre_w = b - c
        z = c / se_c if se_c > 0 else float("nan")
        L.append(
            f"- {m}: the late-read coefficient is c = {f4(c)} (SE {f4(se_c)}, z = {z:.2f}). The top-league pre-window "
            f"coefficient is b - c = {f4(pre_w)}. So the late read carries c / b = {c / b:.2f} of the total slope on "
            f"the two reads combined (only meaningful when 0 <= c / b <= 1).")
    L.append(
        "A c near zero means the late any-league read adds little beyond the top-league pre-window. A c near b means "
        "the late read substitutes for the pre-window. Patches right before an event are often played only in minor "
        "leagues, so the late read can be noisy or unrepresentative for some champions.\n")

    L.append("## Sanity check: unique picked champions per event\n")
    srows = []
    for e in events:
        exp = exp_unique[e["event"]]
        srows.append([e["event"], e["G_pre"], e["G_ev"], e["G_late"], e["universe_size"],
                      e["unique_picked_actual"], f"{exp:.1f}", f"{e['unique_picked_actual'] - exp:+.1f}"])
    L.append(md_table(["Event", "G_pre", "G_ev", "G_late", "Universe", "Unique picked (actual)",
                       "Unique picked (expected, rec. pick model)", "actual - expected"], srows))
    L.append(
        "\nExpected = sum over the universe of 1 - E_u[(1 - p)^G_ev], integrated over u with the recommended pick model. "
        "The model is fitted on these same events, so this is an in-sample check. Actual unique picked counts range "
        f"from {min(e['unique_picked_actual'] for e in events)} to {max(e['unique_picked_actual'] for e in events)} "
        f"(median {float(np.median([e['unique_picked_actual'] for e in events])):.0f}) across the 11 events.\n")

    L.append("## Fit notes\n")
    L.append(f"- Pick and ban rho (posterior-mean u, same champion and event, recommended variant): **{f4(rho)}**.")
    L.append("- Recommendation rule: fearless unless its c SE is above 0.3 while the pooled c SE is below 0.3 for "
             "pick or ban; then pooled. Recommended here: **" + recommended + "**.")
    L.append("- Previous smoothed-OLS fit (v1, with bootstrap-adjusted sd): kept under smoothed_fit_v1 in the JSON and "
             "not used. It smoothed the event side as 0.5/(G_ev+1), against 0.5/(G_pre+1) on the pre side, which put a "
             "higher floor on event rates, and it dropped champions at zero in both windows. The draft sim showed "
             "that this pulls rare champions up too far.\n")

    L.append("## Leader check\n")
    lrows = [[x["event"], f"{x['presence_leader']} (pre rank {x['its_pre_rank']})",
              f"{x['pre_leader']} (event rank {x['its_event_rank']})",
              f"{x['pick_leader']} (pre pick rank {x['its_pre_rank_pick']})"] for x in lc]
    L.append(md_table(["Event", "Presence leader (pre rank)", "Pre presence leader (event rank)",
                       "Most picked (pre pick rank)"], lrows))
    L.append("")
    if lc_notes:
        L.append("Notes: " + " ".join(lc_notes) + "\n")
    L.append("Ranks are among all champions seen in either top-league window, with ties sharing the higher rank.\n")

    L.append("## Events\n")
    erows = [[e["event"], e["start"], e["G_pre"], e["G_ev"], e["G_late"], ", ".join(e["leagues_pre"])]
             for e in events]
    L.append(md_table(["Event", "Start (UTC)", "G_pre", "G_ev", "G_late", "Top-league pre-window leagues"], erows))
    L.append("")

    L.append("## Data notes\n")
    L.append(
        "The database has no LCS rows dated 2025, so LCS is absent from every 2025 pre-window and LTA, LTA N and "
        "LTA S appear instead. WLDs 2023 has no LPL in its pre-window because LPL's last 2023 game (2023-08-05) "
        "falls before it. data_complete = False for all LPL 2022-25 games, 126 LPL 2026 games and all MSI 2024 "
        "games; their pick and ban columns are populated, so they are used as-is (data_complete is not a method "
        "filter). Blank champion slots are dropped.\n")

    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
