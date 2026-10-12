"""Charts for the README: team rating map, starter stats, and champion picks / bans / deaths.

Writes outputs/charts/*.png. Team logos and champion icons come from data/raw/ (python -m ingest.assets).
The simulation overview is made by crystal.overview_plot.

    python -m crystal.charts
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from common import viz
from common.paths import OUTPUTS, ROOT
from crystal.estimate import estimate
from model.predict import _strengths, teams_table
from scipy.stats import spearmanr
from sim.tournament import PLAYIN

CHARTS = OUTPUTS / "charts"
DRAFT_CSV = OUTPUTS / "draft" / "champion_sim.csv"
DDRAGON = ROOT / "data" / "raw" / "ddragon" / "champion.json"
N_SIMS = 20000
PLAYIN_TEAMS = {t for pair in PLAYIN for t in pair}
Q3_PICK = "Rell"
CRYSTAL_PICKS = {"Zeka": "KDA", "Peyz": "damage", "CoreJJ": "kill participation"}   # Q4, Q5, Q6
Q6_PICK = "CoreJJ"
POINTS = (50, 20, 10)
# Points, to keep team badges apart where teams sit close together (rating map)
RATING_OFFSET = {"LYON": (-22, 12), "MKOI": (-24, -12), "TL": (14, -10), "LOS": (-18, 12), "CFO": (16, -4),
                 "TSW": (14, 6), "DK": (12, -6), "T1": (12, -10), "HLE": (-10, 12), "FUR": (-22, -10),
                 "MVK": (-24, 10), "C9": (-14, -8), "KC": (12, -4)}


def save(fig, name: str) -> None:
    fig.savefig(CHARTS / name, dpi=170, facecolor=viz.SURFACE)
    plt.close(fig)
    print(f"wrote {CHARTS / name}")


def champion_ids(names) -> dict[str, str]:
    """Display name -> Data Dragon icon id (e.g. "Cho'Gath" -> "Chogath")."""
    by_name = {v["name"]: v["id"] for v in json.loads(DDRAGON.read_text(encoding="utf-8")).values()}
    missing = [n for n in names if n not in by_name]
    if missing:
        print("no icon for:", ", ".join(missing))
    return {n: by_name[n] for n in names if n in by_name}


def rating_map() -> None:
    """Each Worlds team at its (team rating, player rating) point, drawn as its logo, with 1 sd error bars."""
    ids, s_t, s_p, _, _, cov_t, cov_p, _ = _strengths()
    sd_t, sd_p = np.sqrt(np.diag(cov_t)), np.sqrt(np.diag(cov_p))
    r = np.corrcoef(s_t, s_p)[0, 1]
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.axhline(0, color=viz.BASE, lw=0.8)
    ax.axvline(0, color=viz.BASE, lw=0.8)
    ax.errorbar(s_t, s_p, xerr=sd_t, yerr=sd_p, fmt="none", ecolor=viz.GRID, elinewidth=1.2, zorder=1)
    for tid, x, y in zip(ids, s_t, s_p):
        viz.team_mark(ax, tid, (x, y), zoom=0.13, grey=tid in PLAYIN_TEAMS, offset=RATING_OFFSET.get(tid, (0, 0)))
    ax.set(xlabel="Team rating (Bradley-Terry strength)", ylabel="Player rating (Bradley-Terry strength)")
    ax.grid(True, color=viz.GRID, lw=0.8)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.8, bottom=0.12)
    viz.header(fig, f"Team and player ratings move together (r = {r:.2f})",
               "Each marker is one Worlds 2026 team. Bars show one standard deviation of rating uncertainty.")
    viz.footer(fig, "Source: team and player Bradley-Terry models fitted on Oracle's Elixir games, 2022–2026. "
                    "Play-In teams in grey.")
    save(fig, "team_rating_map.png")


def players_chart(players: dict) -> None:
    """Starters' simulated per-game averages: damage and KDA; bubble size = kill participation.
    Averages are pooled over all simulations, so they match the stats the Crystal Ball picks are drawn from."""
    rows = []
    for name, a in players.items():
        games = a["games"].sum()
        if games == 0 or a["games"].mean() < 5:          # expected games per tournament
            continue
        rows.append({"player": name, "team": a["team"], "role": a["role"], "damage": a["damage"].sum() / games,
                     "kda": (a["kills"].sum() + a["assists"].sum()) / max(a["deaths"].sum(), 1),
                     "kp": a["kp"].sum() / games})
    s = pd.DataFrame(rows)
    picks = s[s["player"].isin(CRYSTAL_PICKS)]
    rest = s[~s["player"].isin(CRYSTAL_PICKS)]
    fig, ax = plt.subplots(figsize=(9, 6.8))
    ax.scatter(rest["damage"], rest["kda"], s=rest["kp"] * 230, color=viz.BASE, alpha=0.7, edgecolor="none")
    ax.scatter(picks["damage"], picks["kda"], s=picks["kp"] * 230, color=viz.EMPHASIS, edgecolor=viz.SURFACE,
               linewidth=1.2, zorder=3)
    for _, r in picks.iterrows():
        right = r["damage"] > 0.9 * s["damage"].max()          # keep labels for the rightmost point inside the axes
        ax.annotate(f"{r['player']} ({r['team']}, {CRYSTAL_PICKS[r['player']]})", (r["damage"], r["kda"]),
                    xytext=(-14, -18) if right else (14, -16) if r["player"] == "CoreJJ" else (14, 8),
                    textcoords="offset points", ha="right" if right else "left",
                    fontsize=9.5, color=viz.INK, fontweight="semibold", zorder=4)
    ax.set(xlabel="Damage per game", ylabel="KDA: (kills + assists) / deaths")
    viz.hairline_grid(ax, "both")
    fig.subplots_adjust(left=0.1, right=0.97, top=0.8, bottom=0.12)
    viz.header(fig, "Three Crystal Ball player picks, one per metric",
               "Blue: the Q4 KDA, Q5 damage and Q6 kill participation picks. Bubble size = kill participation. "
               "Players expected to play 5+ games.")
    ax.set_xlim(s["damage"].min() * 0.9, s["damage"].max() * 1.1)
    viz.footer(fig, "Source: crystal.estimate, 20,000 simulations. Simulated averages, not raw season stats.")
    save(fig, "player_stats.png")


def champion_usage_chart(draft: pd.DataFrame) -> None:
    """Expected picks and bans per tournament for the 15 champions with the most combined."""
    d = draft.assign(total=draft["mean_picks"] + draft["mean_bans"]).sort_values("total", ascending=False).head(15)
    ids = champion_ids(d["champion"])
    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(9, 7.4))
    ax.barh(y, d["mean_picks"], height=0.66, color=viz.BLUE_550, edgecolor=viz.SURFACE, linewidth=1.5)
    ax.barh(y, d["mean_bans"], left=d["mean_picks"], height=0.66, color=viz.BLUE_250,
            edgecolor=viz.SURFACE, linewidth=1.5)
    for yi, (name, tot) in zip(y, zip(d["champion"], d["total"])):
        ax.text(tot + 0.3, yi, f"{tot:.1f}", va="center", fontsize=9.5, color=viz.INK)
        ax.text(-0.175, yi, name, transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=10,
                color=viz.INK, fontweight="semibold")
        if name in ids:
            viz.icon(ax, ids[name], (-0.235, yi), zoom=0.14, box=(0, 0.5))
    ax.set_yticks([])
    ax.set(ylim=(-0.6, len(d) - 0.4), xlim=(0, d["total"].max() * 1.12))
    ax.set_xlabel("Expected count per tournament", fontsize=9.5)
    viz.hairline_grid(ax, "x")
    fig.subplots_adjust(left=0.22, right=0.97, top=0.8, bottom=0.2)
    handles = [Patch(color=viz.BLUE_550, label="Picks"), Patch(color=viz.BLUE_250, label="Bans")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.235, -0.1), ncol=2, fontsize=9,
              handlelength=1, handleheight=1)
    top3 = ", ".join(d["champion"].head(3))
    viz.header(fig, f"{top3}: the most expected champions at Worlds 2026",
               "Expected picks and bans per tournament, top 15 by combined count. Draft simulation with the meta shift.")
    viz.footer(fig, "Source: outputs/draft/champion_sim.csv, 5,000 draft simulations (python -m crystal.draft --main). "
                    "Both teams counted.")
    save(fig, "champion_picks_bans.png")


def champion_deaths_chart(draft: pd.DataFrame) -> None:
    """Average deaths per game for champions picked at least 5 times (the Q3 rule), top 15."""
    d = draft[draft["p_ge5_picks"] >= 0.5].sort_values("mean_deaths_given_ge5", ascending=False).head(15)
    ids = champion_ids(d["champion"])
    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(9, 7.4))
    colors = [viz.EMPHASIS if c == Q3_PICK else viz.BASE for c in d["champion"]]
    ax.barh(y, d["mean_deaths_given_ge5"], height=0.66, color=colors, edgecolor=viz.SURFACE, linewidth=1.5)
    for yi, (name, v) in zip(y, zip(d["champion"], d["mean_deaths_given_ge5"])):
        ax.text(v + 0.03, yi, f"{v:.2f}", va="center", fontsize=9.5, color=viz.INK,
                fontweight="semibold" if name == Q3_PICK else "normal")
        ax.text(-0.175, yi, name, transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=10,
                color=viz.INK, fontweight="semibold" if name == Q3_PICK else "normal")
        if name in ids:
            viz.icon(ax, ids[name], (-0.235, yi), zoom=0.14, box=(0, 0.5))
    ax.set_yticks([])
    ax.set(ylim=(-0.6, len(d) - 0.4), xlim=(0, d["mean_deaths_given_ge5"].max() * 1.12))
    ax.set_xlabel("Average deaths per game for that champion", fontsize=9.5)
    viz.hairline_grid(ax, "x")
    fig.subplots_adjust(left=0.22, right=0.97, top=0.8, bottom=0.12)
    top = d["champion"].iloc[0]
    viz.header(fig, f"{top} has the most deaths per game among champions picked 5+ times",
               f"Q3 pick highlighted: {Q3_PICK}. Champions with 5+ picks in at least half of the simulations, top 15.")
    viz.footer(fig, "Source: outputs/draft/champion_sim.csv, 5,000 draft simulations. Deaths are conditional "
                    "on the champion being picked 5+ times in the tournament.")
    save(fig, "champion_deaths.png")


def q6_chart(table: pd.DataFrame, games: pd.Series, teams: dict[str, str]) -> None:
    """Q6 (kill participation leader): expected-points ranking, and why low-game players rank first more often.
    table: rank table from estimate (p1, p2, p3, EV per starter); games: expected games per tournament;
    teams: player -> team id."""
    rho = spearmanr(games.reindex(table.index), table["p1"]).statistic
    top = table.head(6)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6.4), gridspec_kw={"width_ratios": [1, 1.05], "wspace": 0.35})
    # left: expected points, stacked 50 / 20 / 10
    y = np.arange(len(top))[::-1]
    left = np.zeros(len(top))
    for k, (pts, color) in enumerate(zip(POINTS, (viz.BLUE_700, viz.BLUE_400, viz.BLUE_250))):
        seg = np.array([pts * top[f"p{k + 1}"].iloc[i] for i in range(len(top))])
        ax1.barh(y, seg, left=left, height=0.66, color=color, edgecolor=viz.SURFACE, linewidth=1.5)
        left += seg
    for yi, (name, row) in zip(y, top.iterrows()):
        ax1.text(row["EV"] + 0.15, yi, f"{row['EV']:.1f}", va="center", fontsize=10,
                 fontweight="semibold" if name == Q6_PICK else "normal")
        ax1.text(-0.02, yi, f"{name} ({teams.get(name, '')})", ha="right", va="center", fontsize=10,
                 color=viz.INK, fontweight="semibold" if name == Q6_PICK else "normal",
                 transform=ax1.get_yaxis_transform())
    ax1.set_yticks([])
    ax1.set(ylim=(-0.6, len(top) - 0.4), xlim=(0, top["EV"].max() * 1.15))
    ax1.set_xlabel("Expected points", fontsize=9.5)
    viz.hairline_grid(ax1, "x")
    ax1.set_title("Q6 expected points (top six)", loc="left", pad=12, fontsize=11)
    handles = [Patch(color=viz.BLUE_700, label="1st × 50"), Patch(color=viz.BLUE_400, label="2nd × 20"),
               Patch(color=viz.BLUE_250, label="3rd × 10")]
    ax1.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.13), ncol=3, fontsize=8.5,
               handlelength=1, handleheight=1)
    # right: why. Expected games vs chance to finish first
    g = games.reindex(table.index)
    rest = table.index.difference([Q6_PICK])
    ax2.scatter(g[rest], 100 * table.loc[rest, "p1"], s=46, color=viz.BASE, edgecolor="none", alpha=0.9)
    ax2.scatter([g[Q6_PICK]], [100 * table.loc[Q6_PICK, "p1"]], s=110, color=viz.EMPHASIS, edgecolor=viz.SURFACE,
                linewidth=1.2, zorder=3)
    for name in [Q6_PICK] + [n for n in table.index[:6] if n != Q6_PICK][:3]:
        ax2.annotate(name, (g[name], 100 * table.loc[name, "p1"]), xytext=(8, 6), textcoords="offset points",
                     fontsize=9.5, fontweight="semibold" if name == Q6_PICK else "normal",
                     color=viz.INK)
    ax2.set(xlabel="Expected games per tournament", ylabel="Chance to finish 1st in Q6 (%)", ylim=(0, None))
    ax2.set_title(f"Fewer expected games, more often first (Spearman ρ = {rho:.2f})", loc="left", pad=12, fontsize=11)
    viz.hairline_grid(ax2, "both")
    fig.subplots_adjust(left=0.2, right=0.97, top=0.78, bottom=0.2)
    viz.header(fig, f"{Q6_PICK} is the Q6 pick: the highest chance to lead kill participation",
               "Q6 ranks players by their average kill participation per game in each simulated tournament. "
               "Players with fewer expected games tend to finish first more often.")
    viz.footer(fig, f"Source: crystal.estimate, 20,000 simulations, {len(table)} starters, no minimum games (Q6 rule). "
                    f"Expected points = 50 × P(1st) + 20 × P(2nd) + 10 × P(3rd).")
    save(fig, "q6_kill_participation.png")


def main() -> None:
    viz.apply()
    CHARTS.mkdir(parents=True, exist_ok=True)
    samples: dict = {}
    out, _, games = estimate(N_SIMS, samples=samples)
    rating_map()
    players_chart(samples["players"])
    q6_chart(out["Q6 KP leader"], games, {p: a["team"] for p, a in samples["players"].items()})
    draft = pd.read_csv(DRAFT_CSV)
    champion_usage_chart(draft)
    champion_deaths_chart(draft)


if __name__ == "__main__":
    main()
