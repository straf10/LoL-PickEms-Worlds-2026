"""Calibration layer for game-level win probabilities. Works with ANY model that has the
backtest predict interface (model.backtest.evaluate), because it only sees P(blue wins).

Calibrator maps a model's P(blue wins) to a calibrated one:
  slope     p' = sigmoid(a * logit p)                  one parameter, a > 1 = model under-confident
  platt     p' = sigmoid(a * logit p + b)              b absorbs side/bias
  isotonic  p' = monotone step function of p           non-parametric, for comparison
  + cross-region variant: a separate slope a_cross for games whose two teams come from different
    regions (pass cross_region=... to transform; a calibrator with a_cross refuses to guess).

Usage:
    python -m model.calibration       # reproduce the analysis (recomputes the backtest cache if missing)

    from model.calibration import Calibrator
    cal = Calibrator.load()           # outputs/calibration/calibrator.json
    cal.transform(p_blue, cross_region=is_cross)
"""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression

from common.mathutil import logit as _logit, sigmoid
from common.paths import DB_PATH, OUTPUTS
from common.report import md_table

fmt_table = partial(md_table, floatfmt="{:.3f}")

DB = str(DB_PATH)
OUT_DIR = OUTPUTS / "calibration"
PREDS_CSV = OUT_DIR / "bt_preds.csv"
CAL_JSON = OUT_DIR / "calibrator.json"
REPORT_MD = OUT_DIR / "report.md"
EPS = 1e-6
METHODS = ("slope", "platt", "isotonic")

# Recommended calibrator for the team BT model, set after the analysis (see report.md).
# None = identity: no calibration needed, no LOEO variant beat the raw probabilities.
RECOMMENDED = None

PLAYIN_TEAMS = {  # team_id from games table (LCP/CBLOL/LCS/LEC domestic team ids)
    "FURIA": "oe:team:87e3e1e75839f75a10bbc66e894d806",
    "MVK Esports": "oe:team:bc3824b0bbb8139d16109178faa4822",
    "Cloud9": "oe:team:fc8e90107dabb9a35c490b0d86adea0",
    "Karmine Corp": "oe:team:f3aa9bbd924ce3af42ac53f8326bc7c",
}
PLAYIN_PAIRS = [("FURIA", "MVK Esports"), ("Cloud9", "Karmine Corp")]

BINS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 1.0001]
BIN_LABELS = ["50-55", "55-60", "60-65", "65-70", "70-75", "75-80", "80-85", "85+"]


def logit(p):
    return _logit(np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS))


class Calibrator:
    def __init__(self, method: str, a: float = 1.0, b: float = 0.0, a_cross: float | None = None,
                 iso_x=None, iso_y=None, n_fit: int = 0):
        if method not in METHODS:
            raise ValueError(f"method must be one of {METHODS}")
        self.method = method
        self.a = float(a)
        self.b = float(b)
        self.a_cross = None if a_cross is None else float(a_cross)
        self.iso_x = None if iso_x is None else np.asarray(iso_x, dtype=float)
        self.iso_y = None if iso_y is None else np.asarray(iso_y, dtype=float)
        self.n_fit = int(n_fit)

    @property
    def cross_region(self) -> bool:
        return self.a_cross is not None

    def transform(self, p, cross_region=None):
        """p = P(blue wins) from any model. cross_region: bool array (True = teams from different regions)."""
        p = np.asarray(p, dtype=float)
        if self.method == "isotonic":
            return np.clip(np.interp(p, self.iso_x, self.iso_y), EPS, 1 - EPS)
        a = np.full(p.shape, self.a)
        if self.cross_region:
            if cross_region is None:
                raise ValueError("this calibrator has a cross-region slope: pass cross_region")
            a = np.where(np.asarray(cross_region, dtype=bool), self.a_cross, self.a)
        return sigmoid(a * logit(p) + self.b)

    def to_dict(self) -> dict:
        d = {"method": self.method, "a": self.a, "b": self.b, "a_cross": self.a_cross, "n_fit": self.n_fit}
        if self.method == "isotonic":
            d["iso_x"] = self.iso_x.tolist()
            d["iso_y"] = self.iso_y.tolist()
        return d

    def save(self, path=CAL_JSON) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path=CAL_JSON) -> "Calibrator":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def __repr__(self) -> str:
        if self.method == "isotonic":
            return f"Calibrator(isotonic, n_fit={self.n_fit})"
        s = f"Calibrator({self.method}, a={self.a:.3f}, b={self.b:.3f}"
        if self.cross_region:
            s += f", a_cross={self.a_cross:.3f}"
        return s + f", n_fit={self.n_fit})"


def _nll(theta, z, y, cross, fit_b, has_cross):
    a = theta[0]
    i = 1
    slope = a
    if has_cross:
        slope = np.where(cross, theta[1], a)
        i = 2
    b = theta[i] if fit_b else 0.0
    q = np.clip(sigmoid(slope * z + b), EPS, 1 - EPS)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def fit_calibrator(preds: pd.DataFrame, method: str = "slope", cross_region_col: str | None = None) -> Calibrator:
    """Fit on a predictions table with columns p_blue, blue_win (+ cross_region_col if given).
    Rows with NaN p_blue (games the model could not rate) are ignored.
      method='slope'    : p' = sigmoid(a*logit p)            (b = 0, symmetric in side)
      method='platt'    : p' = sigmoid(a*logit p + b)
      method='isotonic' : sklearn isotonic regression on p
    cross_region_col: name of a bool column; adds a separate slope for those games."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    d = preds[preds["p_blue"].notna()]
    y = d["blue_win"].astype(float).to_numpy()
    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1 - EPS)
        iso.fit(d["p_blue"].to_numpy(dtype=float), y)
        return Calibrator("isotonic", iso_x=iso.X_thresholds_, iso_y=iso.y_thresholds_, n_fit=len(y))

    z = logit(d["p_blue"].to_numpy(dtype=float))
    has_cross = cross_region_col is not None
    cross = d[cross_region_col].astype(bool).to_numpy() if has_cross else np.zeros(len(y), dtype=bool)
    fit_b = method == "platt"
    x0 = [1.0] + ([1.0] if has_cross else []) + ([0.0] if fit_b else [])
    res = minimize(_nll, x0, args=(z, y, cross, fit_b, has_cross), method="Nelder-Mead",
                   options={"xatol": 1e-8, "fatol": 1e-10, "maxiter": 5000})
    x = res.x
    a = x[0]
    a_cross = x[1] if has_cross else None
    b = x[-1] if fit_b else 0.0
    return Calibrator(method, a=a, b=b, a_cross=a_cross, n_fit=len(y))


# --- data preparation -----------------------------------------------------------------------

def load_preds(con=None) -> pd.DataFrame:
    """Cached backtest predictions (outputs/calibration/bt_preds.csv); recomputed if missing."""
    if PREDS_CSV.exists():
        return pd.read_csv(PREDS_CSV)
    from model.backtest import bt_predict, evaluate
    rep, preds = evaluate(bt_predict, con=con)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preds.to_csv(PREDS_CSV, index=False)
    rep.to_csv(OUT_DIR / "bt_report_base.csv", index=False)
    return preds


def annotate(preds: pd.DataFrame, con) -> pd.DataFrame:
    """Adds: bo1 (approx.), cross_region, fav_blue, fav_p, fav_won."""
    from model.ratings import load_games, team_regions
    regions = team_regions(load_games(con))
    meta = con.sql("select game_id, league, game_in_series, blue_team_id, red_team_id, date_utc from games").df()
    meta["day"] = meta["date_utc"].dt.date
    meta["pair"] = [f"{min(str(b), str(r))}|{max(str(b), str(r))}"
                    for b, r in zip(meta["blue_team_id"], meta["red_team_id"])]
    # Bo1 approximation: game 1 of its series and no other game between the same two teams in the
    # same league on the same UTC day. Bo3/Bo5 games almost always share a day; Bo1 never does.
    meta["group_size"] = meta.groupby(["league", "day", "pair"])["game_id"].transform("size")
    meta["bo1"] = (meta["game_in_series"] == 1) & (meta["group_size"] == 1)
    df = preds.merge(meta[["game_id", "bo1", "blue_team_id", "red_team_id"]], on="game_id", how="left", validate="1:1")
    df["blue_region"] = df["blue_team_id"].map(regions)
    df["red_region"] = df["red_team_id"].map(regions)
    df["cross_region"] = (df["blue_region"] != df["red_region"]).where(df["blue_region"].notna() & df["red_region"].notna())
    df["fav_blue"] = df["p_blue"] >= 0.5
    df["fav_p"] = np.maximum(df["p_blue"], 1 - df["p_blue"])
    df["fav_won"] = np.where(df["fav_blue"], df["blue_win"], 1 - df["blue_win"])
    return df


# --- reliability ----------------------------------------------------------------------------

def _logloss(p, y):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(p, y):
    return float(np.mean((np.asarray(p, dtype=float) - y) ** 2))


def reliability(d: pd.DataFrame) -> pd.DataFrame:
    """Bins by the favourite's predicted win probability. Columns: bin, n, pred_fav, actual_fav, gap, se."""
    d = d[d["p_blue"].notna()]
    b = pd.cut(d["fav_p"], BINS, labels=BIN_LABELS, right=False, include_lowest=True)
    g = d.groupby(b, observed=False)
    out = pd.DataFrame({
        "n": g["fav_won"].size(),
        "pred_fav": g["fav_p"].mean(),
        "actual_fav": g["fav_won"].mean(),
    })
    out["gap"] = out["actual_fav"] - out["pred_fav"]
    out["se"] = np.sqrt(out["pred_fav"] * (1 - out["pred_fav"]) / out["n"].replace(0, np.nan))
    out.index.name = "fav_prob_bin"
    return out.reset_index()


def summary_row(name: str, d: pd.DataFrame) -> dict:
    d = d[d["p_blue"].notna()]
    rel = reliability(d)
    n = len(d)
    ece = float((rel["n"] * rel["gap"].abs()).sum() / n) if n else np.nan
    y = d["blue_win"].astype(float).to_numpy()
    return {"subgroup": name, "n": n, "pred_fav": d["fav_p"].mean(), "actual_fav": d["fav_won"].mean(),
            "gap_pp": 100 * (d["fav_won"].mean() - d["fav_p"].mean()), "ECE": ece,
            "log_loss_raw": _logloss(d["p_blue"], y), "brier_raw": _brier(d["p_blue"], y)}



def split_groups(d: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    cr = d["cross_region"].fillna(False).astype(bool)
    return {
        "Bo1-ish vs in-series": {"Bo1-ish": d[d["bo1"].astype(bool)], "in-series": d[~d["bo1"].astype(bool)]},
        "same-region vs cross-region": {"same-region": d[~cr], "cross-region": d[cr]},
        "blue-side vs red-side favourite": {"blue-side fav": d[d["fav_blue"]], "red-side fav": d[~d["fav_blue"]]},
    }


# --- leave-one-event-out --------------------------------------------------------------------

def loeo_predict(d: pd.DataFrame, method: str, cross: bool) -> np.ndarray:
    """Out-of-fold calibrated P(blue) for every row with a prediction (fit on the other 11 events)."""
    d = d.reset_index(drop=True)
    q = np.full(len(d), np.nan)
    col = "cross_region" if cross else None
    for ev in d["event"].unique():
        te = (d["event"] == ev).to_numpy()
        cal = fit_calibrator(d[~te], method, cross_region_col=col)
        ok = te & d["p_blue"].notna().to_numpy()
        q[ok] = cal.transform(d.loc[ok, "p_blue"].to_numpy(dtype=float),
                              cross_region=d.loc[ok, "cross_region"].astype(bool).to_numpy() if cross else None)
    return q


def loeo_table(d: pd.DataFrame, variants: dict[str, tuple[str | None, bool]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = d[d["p_blue"].notna()].reset_index(drop=True)
    y = d["blue_win"].astype(float).to_numpy()
    cr = d["cross_region"].fillna(False).astype(bool).to_numpy()
    rows, per_event = [], []
    for name, (method, cross) in variants.items():
        q = d["p_blue"].to_numpy(dtype=float) if method is None else loeo_predict(d, method, cross)
        rows.append({"calibrator": name, "log_loss": _logloss(q, y), "brier": _brier(q, y),
                     "log_loss_cross": _logloss(q[cr], y[cr]), "log_loss_same": _logloss(q[~cr], y[~cr]),
                     "brier_cross": _brier(q[cr], y[cr]), "brier_same": _brier(q[~cr], y[~cr])})
        for ev in d["event"].unique():
            m = (d["event"] == ev).to_numpy()
            per_event.append({"calibrator": name, "event": ev, "games": int(m.sum()),
                              "log_loss": _logloss(q[m], y[m]), "brier": _brier(q[m], y[m])})
    tab = pd.DataFrame(rows)
    base = tab.loc[tab["calibrator"] == "raw (uncalibrated)", "log_loss"].iloc[0]
    tab["d_logloss_vs_raw"] = tab["log_loss"] - base
    pe = pd.DataFrame(per_event)
    return tab, pe


# --- Play-In application ------------------------------------------------------------------

def fit_current_model(con):
    from model.ratings import BTModel, Params, load_games, team_regions
    games = load_games(con)
    regions = team_regions(games)
    return BTModel(Params()).fit(games, pd.Timestamp("2026-10-15"), regions), regions


def playin_probs(m, regions, cal: Calibrator | None, a: str, b: str) -> dict:
    """P(a wins one game vs b), averaged over sides like BTModel.p_game(a, b), and the Bo5 probability.
    Calibration is applied to each side-specific P(blue wins) before averaging."""
    from model.ratings import series_prob
    ia, ib = PLAYIN_TEAMS[a], PLAYIN_TEAMS[b]
    cross = bool(regions[ia] != regions[ib])
    p_ab_blueA = m.p_game(ia, ib, True)     # P(a wins | a is blue) = P(blue wins)
    p_ba_blueB = m.p_game(ib, ia, True)     # P(b wins | b is blue) = P(blue wins) in the swapped game
    if cal is not None:
        cr = np.array([cross])
        q1 = float(cal.transform(np.array([p_ab_blueA]), cross_region=cr if cal.cross_region else None)[0])
        q2 = float(cal.transform(np.array([p_ba_blueB]), cross_region=cr if cal.cross_region else None)[0])
    else:
        q1, q2 = p_ab_blueA, p_ba_blueB
    p_game = 0.5 * (q1 + (1 - q2))
    raw = m.p_game(ia, ib)
    return {"pair": f"{a} vs {b}", "cross_region": cross, "raw_game": raw,
            "game": p_game, "raw_bo5": series_prob(raw, 5), "bo5": series_prob(p_game, 5)}


def main():
    import duckdb
    con = duckdb.connect(DB, read_only=True)
    preds = load_preds(con)
    d = annotate(preds, con)
    n_all, n_rated = len(d), int(d["p_blue"].notna().sum())
    events = list(d["event"].unique())

    out = []
    out.append("# Calibration of the team Bradley-Terry model (backtest on 12 international events)\n")
    out.append(f"Predictions: `model.backtest.bt_predict` via `model.backtest.evaluate` ({n_all} games, "
               f"{n_all - n_rated} unrateable games skipped, {n_rated} analysed). Each prediction uses only "
               "data before its event start, so the predictions are already out-of-sample.\n")
    out.append("Caveats: (1) `cross_region` uses each team's current region (`model.ratings.team_regions`, "
               "same as the model uses), not its region at the event. (2) Bo1-ish is an approximation: game 1 of "
               "its series with no other game between the same teams in that league on the same UTC day.\n")

    # 1. reliability overall
    rel = reliability(d)
    out.append("## 1. Reliability (favourite's predicted probability vs actual win rate)\n")
    out.append(fmt_table(rel.rename(columns={"fav_prob_bin": "bin"})))
    s_all = summary_row("all", d)
    out.append(f"\nOverall: n={s_all['n']}, predicted favourite {s_all['pred_fav']:.3f}, actual {s_all['actual_fav']:.3f}, "
               f"gap {s_all['gap_pp']:+.1f} pp, ECE {s_all['ECE']:.3f}.\n")

    # 2. splits
    out.append("## 2. Splits\n")
    summ = [summary_row("all", d)]
    for split, groups in split_groups(d).items():
        for name, g in groups.items():
            summ.append(summary_row(f"{split}: {name}", g))
    summ_df = pd.DataFrame(summ)
    out.append(fmt_table(summ_df))
    out.append("")
    for split, groups in split_groups(d).items():
        out.append(f"### {split}\n")
        frames = []
        for name, g in groups.items():
            r = reliability(g)
            r.insert(0, "group", name)
            frames.append(r)
        out.append(fmt_table(pd.concat(frames, ignore_index=True)))
        out.append("")

    # 3. LOEO
    variants = {
        "raw (uncalibrated)": (None, False),
        "slope (b=0)": ("slope", False),
        "slope + cross-region slope": ("slope", True),
        "platt (a,b)": ("platt", False),
        "platt + cross-region slope": ("platt", True),
        "isotonic": ("isotonic", False),
    }
    tab, pe = loeo_table(d, variants)
    out.append("## 3. Leave-one-event-out CV (fit on 11 events, score the held-out 12th; pooled out-of-fold scores)\n")
    out.append(fmt_table(tab))
    piv = pe.pivot(index="event", columns="calibrator", values="log_loss")
    piv = piv.reindex(events)
    piv.insert(0, "games", pe.groupby("event")["games"].first().reindex(events).values)
    out.append("\nPer-event held-out log-loss:\n")
    out.append(fmt_table(piv.reset_index().rename(columns={"index": "event"})))
    out.append("")

    # 4. full-data fits
    fits = {}
    for method in ("slope", "platt", "isotonic"):
        for cross in (False, True):
            if method == "isotonic" and cross:
                continue
            c = fit_calibrator(d, method, cross_region_col="cross_region" if cross else None)
            fits[f"{method}{' + cross' if cross else ''}"] = c
    out.append("## 4. Parameters fitted on all 12 events\n")
    out.append("| calibrator | a (same-region slope) | a_cross | b |\n|---|---|---|---|")
    for k, c in fits.items():
        if c.method == "isotonic":
            out.append(f"| {k} | (isotonic, {len(c.iso_x)} thresholds) | | |")
        else:
            out.append(f"| {k} | {c.a:.3f} | {'' if c.a_cross is None else f'{c.a_cross:.3f}'} | {c.b:.3f} |")
    out.append("")

    # 5. recommendation
    if RECOMMENDED is None:
        rec = Calibrator("slope", a=1.0, b=0.0, n_fit=int(d["p_blue"].notna().sum()))  # identity
        rec_label = "recommended (identity)"
    else:
        rec_method, rec_cross = RECOMMENDED
        rec = fit_calibrator(d, rec_method, cross_region_col="cross_region" if rec_cross else None)
        rec_label = f"recommended ({rec_method}{' + cross' if rec_cross else ''})"
    rec.save(CAL_JSON)
    out.append("## 5. Recommendation\n")
    out.append(RECOMMENDATION_TEXT)
    out.append(f"\nSaved: `{CAL_JSON}` = {rec}. Refit for another model with `fit_calibrator(preds, method, cross_region_col)`.\n")

    # 6. Play-In
    m, regions = fit_current_model(con)
    variants = [("uncalibrated", None), (rec_label, rec),
                ("fitted slope (not recommended)", fits["slope"]),
                ("fitted slope + cross (not recommended)", fits["slope + cross"])]
    rows = []
    for a, b in PLAYIN_PAIRS:
        for name, cal in variants:
            r = playin_probs(m, regions, cal, a, b)
            r["calibrator"] = name
            rows.append(r)
    pi = pd.DataFrame(rows)[["pair", "cross_region", "calibrator", "raw_game", "game", "raw_bo5", "bo5"]]
    out.append("## 6. Play-In probabilities (team model as of 2026-10-15, default Params)\n")
    out.append(fmt_table(pi))
    out.append("\nBookmaker-implied Bo5 (from the brief): FURIA ~0.75, Karmine Corp ~0.64 (C9 vs KC: KC Bo5 = 1 - C9 Bo5).\n")
    REPORT_MD.write_text("\n".join(out), encoding="utf-8")

    print("\n".join(out))
    print(f"\nReport written to {REPORT_MD}")
    return d, tab, pe, rec, pi


RECOMMENDATION_TEXT = """**Recommendation: no calibration needed for the team Bradley-Terry model.** Keep the identity calibrator
(`outputs/calibration/calibrator.json`) so downstream code can always call `Calibrator.load().transform(...)`.

- **Overall reliability is good.** Favourite predicted 0.667, actual 0.647 (gap -2.0 pp, ECE 0.047, 862 games).
  The 60-70% bins look over-confident (actual 0.50-0.57 vs predicted 0.62-0.68, about 2 SE each), but there is no
  consistent direction across bins. The 75-85% bins are slightly under-confident.
- **Slope fit on all 12 events:** a = 0.931 (b = 0). The model is very slightly over-confident, within noise.
- **LOEO-CV:** no calibrator beats raw. Pooled log-loss: raw 0.613, slope 0.613, Platt 0.613, isotonic 0.641
  (isotonic is worse: the MSI 2024 fold goes to 0.936). Brier is 0.213 for all but isotonic.
- **Cross-region slope:** the fit gives a_cross = 0.92 for cross-region games and 1.81 for same-region games. Out of fold
  it changes nothing for cross-region games (log-loss 0.602 vs 0.602), and it makes same-region games (n = 127) worse
  (0.675 to 0.681). The model's region gaps are not systematically mis-stated, so no separate cross-region slope is used.
- **Residual patterns, not corrected by any calibrator:** Bo1-ish games are under-predicted (+5.5 pp, n = 153; the
  Bo1 vs series difference is about 2 SE) and red-side favourites under-perform (-4.7 pp, n = 351, about 1.2 SE).
  Mean P(blue) is 0.540 vs an actual blue win rate of 0.558, a small side-bias gap.
- **Play-In implication:** calibration moves the Play-In numbers by at most about 0.005 per game. The gap to the
  bookmakers is about ratings, not calibration. CBLOL sits at the bottom of the region table (-0.74) and LCP at -0.57,
  so FURIA and MVK are rated almost equal. Bookmakers have FURIA at about 0.75 Bo5, the model at 0.49. Flag this
  before freeze."""

if __name__ == "__main__":
    main()
