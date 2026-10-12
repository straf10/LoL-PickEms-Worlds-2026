"""Single entry point for game win probabilities between Worlds 2026 teams.

P(game) = sigmoid( 0.5 * logit(team model) + 0.5 * logit(player model) )   [neutral side]
then optionally:
  - calibration (model/calibration.py, if outputs/calibration/calibrator.json exists and USE_CALIBRATION)
  - market blend: where a bookmaker Bo5 price is known and differs from the model by > MARKET_GAP,
    the game probability becomes the logit-average of model and market (guideline 8).

    from model.predict import game_matrix
    P = game_matrix()        # DataFrame, P.loc[a, b] = P(a beats b in one game)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import brentq

from model.mathutil import logit, sigmoid
from model.player_ratings import PlayerModel, PParams, load
from model.ratings import BTModel, Params, load_games, series_prob, team_regions

ROOT = Path(__file__).resolve().parents[1]
AS_OF = pd.Timestamp("2026-10-15")
W_PLAYER = 0.5
MARKET_GAP = 0.15
USE_CALIBRATION = True

# decimal odds as given by the user on 2026-10-12 (Bo5 match winner)
MARKET_BO5 = {("FUR", "MVK"): (1.22, 3.65), ("C9", "KC"): (2.55, 1.44)}


def market_prob(odds_a: float, odds_b: float) -> float:
    """Bookmaker margin removed proportionally."""
    a, b = 1 / odds_a, 1 / odds_b
    return a / (a + b)


def game_from_series(p_series: float, best_of: int = 5) -> float:
    return brentq(lambda p: series_prob(p, best_of) - p_series, 1e-4, 1 - 1e-4)


@lru_cache(maxsize=1)
def _models():
    con = duckdb.connect(str(ROOT / "data" / "pickems.duckdb"), read_only=True)
    games = load_games(con)
    team = BTModel(Params()).fit(games, AS_OF, team_regions(games))
    pgames, pg = load(con)
    player = PlayerModel(PParams(lam_player=30)).fit(pgames, pg, AS_OF)
    return team, player


def _calibrator():
    path = ROOT / "outputs" / "calibration" / "calibrator.json"
    if not (USE_CALIBRATION and path.exists()):
        return None
    try:
        from model.calibration import Calibrator
        return Calibrator.load(path)
    except Exception as e:  # calibration is optional; never block the pipeline
        print(f"[predict] calibration not applied: {e}")
        return None


def teams_table() -> pd.DataFrame:
    teams = pd.read_csv(ROOT / "data" / "worlds2026_teams.csv")
    ros = pd.read_csv(ROOT / "data" / "rosters_2026.csv")
    starters = ros[ros["is_starter"] == True].groupby("team_id")["player_id"].apply(list)
    teams["starters"] = teams["team_id"].map(starters)
    return teams


@lru_cache(maxsize=1)
def _strengths():
    """Point strengths per model, sides, and Laplace covariances (19 x 19) for the Worlds teams."""
    team, player = _models()
    t = teams_table().set_index("team_id")
    ids = t.index.tolist()
    s_t = np.array([team.strength(t.loc[i, "oe_team_id"]) for i in ids])
    s_p = np.array([player.strength(t.loc[i, "starters"], t.loc[i, "oe_team_id"], t.loc[i, "region"]) for i in ids])
    cov_t = team.strength_cov(t["oe_team_id"].tolist())
    cov_p = player.strength_cov([(t.loc[i, "starters"], t.loc[i, "oe_team_id"], t.loc[i, "region"]) for i in ids])
    reg = t["region"].to_numpy(dtype=object)
    cross = reg[:, None] != reg[None, :]
    return ids, s_t, s_p, team.side, player.side, cov_t, cov_p, cross


def _matrix(s_t, s_p, side_t, side_p, cross, cal=None) -> np.ndarray:
    """Neutral-side blended game probabilities, vectorized. P[i, j] = P(i beats j)."""
    def neutral(d, side):
        return 0.5 * (sigmoid(d + side) + sigmoid(d - side))
    pt = neutral(s_t[:, None] - s_t[None, :], side_t)
    pp = neutral(s_p[:, None] - s_p[None, :], side_p)
    P = sigmoid((1 - W_PLAYER) * logit(pt) + W_PLAYER * logit(pp))
    if cal is not None:
        P = np.asarray(cal.transform(P.ravel(), cross_region=cross.ravel())).reshape(P.shape)
        P = 0.5 * (P + 1 - P.T)                     # keep P[i,j] + P[j,i] = 1
    np.fill_diagonal(P, 0.5)
    return P


def _apply_market(P: np.ndarray, ids: list[str], verbose: bool = False) -> np.ndarray:
    idx = {t: k for k, t in enumerate(ids)}
    for (a, b), (oa, ob) in MARKET_BO5.items():
        i, j = idx[a], idx[b]
        m_series = market_prob(oa, ob)
        model_series = series_prob(P[i, j], 5)
        if abs(m_series - model_series) > MARKET_GAP:
            p = float(sigmoid(0.5 * logit(P[i, j]) + 0.5 * logit(game_from_series(m_series))))
            if verbose:
                print(f"[market] {a}-{b}: model Bo5 {model_series:.2f} vs market {m_series:.2f} -> blended game p {p:.3f}")
            P[i, j], P[j, i] = p, 1 - p
    return P


def game_matrix(use_market: bool = True, verbose: bool = False) -> pd.DataFrame:
    """Point-estimate matrix (best-guess strengths)."""
    ids, s_t, s_p, side_t, side_p, _, _, cross = _strengths()
    P = _matrix(s_t, s_p, side_t, side_p, cross, _calibrator())
    if use_market:
        P = _apply_market(P, ids, verbose)
    return pd.DataFrame(P, index=ids, columns=ids)


def matrix_sampler(use_market: bool = True, scale: float = 1.0):
    """Returns sample(rng) -> one plausible probability matrix (numpy, order = ids).
    Strength draws come from each model's Laplace covariance. The two models are fitted on the same
    games, so their errors are treated as perfectly correlated (one standard-normal draw drives both):
    the conservative choice, it doesn't shrink uncertainty by averaging. `scale` widens/narrows it."""
    ids, s_t, s_p, side_t, side_p, cov_t, cov_p, cross = _strengths()
    jitter = 1e-9 * np.eye(len(ids))
    L_t, L_p = np.linalg.cholesky(cov_t + jitter), np.linalg.cholesky(cov_p + jitter)
    cal = _calibrator()

    def sample(rng: np.random.Generator) -> np.ndarray:
        z = rng.standard_normal(len(ids)) * scale
        P = _matrix(s_t + L_t @ z, s_p + L_p @ z, side_t, side_p, cross, cal)
        return _apply_market(P, ids) if use_market else P

    return ids, sample


if __name__ == "__main__":
    P = game_matrix(verbose=True)
    order = P.mean(axis=1).sort_values(ascending=False).index
    print(P.loc[order, order].round(2).to_string())
    for a, b in MARKET_BO5:
        print(f"{a} vs {b}: game {P.loc[a, b]:.3f}  Bo5 {series_prob(P.loc[a, b], 5):.3f}")
