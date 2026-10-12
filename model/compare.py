"""Compare team BT, player BT and their logit blend on common games. Saves per-game predictions."""
import sys
import duckdb, numpy as np, pandas as pd
from model.backtest import evaluate, bt_predict, log_loss
from model.player_ratings import make_predict, PParams

con = duckdb.connect("data/pickems.duckdb", read_only=True)
_, a = evaluate(bt_predict, con=con)
_, b = evaluate(make_predict(PParams(lam_player=30)), con=con)
a.to_csv("outputs/model_compare/team_preds.csv", index=False)
b.to_csv("outputs/model_compare/player_preds.csv", index=False)
m = a.merge(b[["game_id", "p_blue"]], on="game_id", suffixes=("_team", "_player")).dropna()
logit = lambda p: np.log(p / (1 - p))
y = m.blue_win.values
rows = []
for wgt in (0, 0.25, 0.5, 0.75, 1):
    z = (1 - wgt) * logit(m.p_blue_team) + wgt * logit(m.p_blue_player)
    p = 1 / (1 + np.exp(-z))
    held = m.event.str.contains("2025|2026").values
    rows.append(dict(w_player=wgt, ll_all=log_loss(p, y), ll_pre2025=log_loss(p[~held], y[~held]),
                     ll_2025_26=log_loss(p[held], y[held]), acc=np.mean((p > .5) == y)))
print(f"common games: {len(m)}")
print(pd.DataFrame(rows).round(4).to_string(index=False))
