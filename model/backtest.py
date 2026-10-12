"""Shared backtest harness: every model is scored on the same international events.

A model is a function  predict(con, as_of, event_games) -> np.ndarray of P(blue side wins),
using only data strictly before `as_of` (the event start). No leakage: the harness passes
the event start as as_of; the model must filter its own training data with date_utc < as_of.

    from model.backtest import evaluate, EVENTS
    report, preds = evaluate(my_predict)
"""
from __future__ import annotations

from typing import Callable

import duckdb
import numpy as np
import pandas as pd

DB = "data/pickems.duckdb"

EVENTS = {  # name: (league, start, end)
    "Worlds 2022": ("WLDs", "2022-09-29", "2022-11-07"),
    "MSI 2023": ("MSI", "2023-05-02", "2023-05-22"),
    "Worlds 2023": ("WLDs", "2023-10-09", "2023-11-20"),
    "MSI 2024": ("MSI", "2024-05-01", "2024-05-20"),
    "Worlds 2024": ("WLDs", "2024-09-25", "2024-11-03"),
    "First Stand 2025": ("FST", "2025-03-10", "2025-03-17"),
    "MSI 2025": ("MSI", "2025-06-27", "2025-07-14"),
    "EWC 2025": ("EWC", "2025-07-01", "2025-07-21"),
    "Worlds 2025": ("WLDs", "2025-10-14", "2025-11-10"),
    "First Stand 2026": ("FST", "2026-03-16", "2026-03-23"),
    "MSI 2026": ("MSI", "2026-06-28", "2026-07-13"),
    "EWC 2026": ("EWC", "2026-07-01", "2026-07-20"),
}

Predict = Callable[[duckdb.DuckDBPyConnection, pd.Timestamp, pd.DataFrame], np.ndarray]


def event_games(con, league: str, start: str, end: str) -> pd.DataFrame:
    return con.sql(f"""
        select * from games where league = '{league}'
        and date_utc >= '{start}' and date_utc < '{end}' order by date_utc""").df()


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def evaluate(predict: Predict, events: dict | None = None, con=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (per-event report incl. an ALL row, per-game predictions with outcome).
    Games the model can't rate must be returned as NaN; they are reported as `skipped`."""
    con = con or duckdb.connect(DB, read_only=True)
    rows, preds = [], []
    for name, (league, start, end) in (events or EVENTS).items():
        ev = event_games(con, league, start, end)
        if ev.empty:
            continue
        p = np.asarray(predict(con, pd.Timestamp(start), ev), dtype=float)
        ok = ~np.isnan(p)
        y = ev["blue_win"].astype(float).values
        rows.append({"event": name, "games": int(ok.sum()), "skipped": int((~ok).sum()),
                     "log_loss": log_loss(p[ok], y[ok]), "brier": float(np.mean((p[ok] - y[ok]) ** 2)),
                     "accuracy": float(np.mean((p[ok] > 0.5) == y[ok]))})
        preds.append(pd.DataFrame({"event": name, "game_id": ev["game_id"], "p_blue": p, "blue_win": y}))
    rep = pd.DataFrame(rows)
    w = rep["games"]
    rep.loc[len(rep)] = {"event": "ALL", "games": int(w.sum()), "skipped": int(rep["skipped"].sum()),
                         **{k: float(np.average(rep[k], weights=w)) for k in ("log_loss", "brier", "accuracy")}}
    return rep, pd.concat(preds, ignore_index=True)


# --- reference model: the current team Bradley-Terry ---------------------------------------

_cache: dict = {}


def bt_predict(con, as_of, ev, params=None):
    from model.ratings import BTModel, Params, load_games, team_regions
    if "games" not in _cache:
        _cache["games"] = load_games(con)
        _cache["regions"] = team_regions(_cache["games"])
    m = BTModel(params or Params()).fit(_cache["games"], as_of, _cache["regions"])
    return np.array([m.p_game(b, r, True) if b in m.T.index and r in m.T.index else np.nan
                     for b, r in zip(ev["blue_team_id"], ev["red_team_id"])])


if __name__ == "__main__":
    rep, _ = evaluate(bt_predict)
    print(rep.round(4).to_string(index=False))
