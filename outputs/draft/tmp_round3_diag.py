"""Scratch diagnostic for the round-3 shift calibration (not a deliverable)."""
import sys
import pandas as pd

sys.path.insert(0, r"C:\Python\LOL_PICKEMS")
import crystal.draft as d  # noqa: E402

sims = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
games = pd.read_csv(d.GAMES_FILE)
games = games[games.sim < sims]
out = d.run_draft(games, k=15.0, shift=True, seed=7)

info = out["info"].set_index("key").value
for key in ["sum_window_pick_targets", "sum_window_ban_targets", "sum_calib_pick_targets",
            "sum_calib_ban_targets", "common_shift_pick_logit", "common_shift_ban_logit", "sum_marginal_pick_pre_shift", "sum_marginal_ban_pre_shift", "spread_ratio_min", "spread_ratio_max", "spread_all_in_band", "calibration_converged", "calibration_iterations",
            "calibration_max_err_pick_pp", "calibration_max_err_ban_pp", "verification_pass",
            "verification_max_err_pick_pp", "verification_max_err_ban_pp", "spread_max_abs_dev_from_1",
            "benchmark_max_abs_diff", "q10_median", "q10_p10", "q10_p90", "seconds_total"]:
    print(f"{key}: {info.get(key)}")

hist = pd.DataFrame(eval(info["calibration_hist"]))
print(hist.to_string())
print()
print(out["spread"].round(4).to_string())
print()
print(out["benchmark"].round(4).to_string())
print()
s = out["summary"]
print(s.sort_values("p_lead_q1", ascending=False).head(8)[["champion", "p_lead_q1", "mean_presence", "mean_picks"]].round(3).to_string())
v = out["verification"]
print(v[v.target_pick_pct > 3].round(2).head(10).to_string())
