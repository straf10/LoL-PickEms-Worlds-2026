"""Simulation overview for the README: where each team finishes (left) and how a ranked answer is chosen (right).

Reads outputs/crystal_sim.md (written by crystal.estimate) and writes outputs/charts/simulation_overview.png.

    python -m crystal.overview_plot
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from common import viz
from common.paths import OUTPUTS

KO_MIN = 0.40          # left panel: teams with at least this chance to reach Knockouts
CHOICE_Q = "Q18 shortest game winner"
TOP_N = 6              # right panel: candidates shown
POINTS = (50, 20, 10)
PLAYIN_TEAMS = {"FUR", "MVK", "C9", "KC"}
PLACE_COLS = ["Champion", "Final", "SF", "QF", "Swiss 2-3", "Swiss 1-3", "Swiss 0-3", "Play-In", "P(KO)", "games_mean", "games_p90"]


def read_blocks(text: str) -> dict[str, list[str]]:
    """Map each '## heading' to the lines of its first fenced block."""
    out, head, inside, buf = {}, None, False, []
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
        elif line.startswith("```"):
            if inside:
                out[head] = buf
                buf, inside = [], False
            else:
                inside = True
        elif inside:
            buf.append(line)
    return out


def placements(lines: list[str]) -> dict[str, dict[str, float]]:
    """Tournament outcome table: team -> {placement column: share of sims}."""
    rows = {}
    for line in lines:
        tok = line.split()
        if len(tok) == len(PLACE_COLS) + 1 and tok[0] not in ("placement", "team"):
            rows[tok[0]] = dict(zip(PLACE_COLS, map(float, tok[1:])))
    return rows


def ranked(lines: list[str]) -> dict[str, dict[str, float]]:
    """Ranked table with p1, p2, p3, EV columns: candidate -> values."""
    rows = {}
    for line in lines:
        tok = line.split()
        if len(tok) == 5 and tok[0] != "champion":
            rows[tok[0]] = dict(zip(["p1", "p2", "p3", "EV"], map(float, tok[1:])))
    return rows


def finish_panel(ax, place: dict[str, dict[str, float]]) -> str:
    """Stacked bars: where each main-stage team ends up. Returns the favourite's code for the headline."""
    teams = sorted((t for t in place if place[t]["P(KO)"] >= KO_MIN), key=lambda t: -place[t]["Champion"])
    y = np.arange(len(teams))[::-1]
    segs = [
        (["Champion"], viz.BLUE_700),
        (["Final"], viz.BLUE_550),
        (["SF"], viz.BLUE_400),
        (["QF"], viz.BLUE_250),
        (["Swiss 2-3", "Swiss 1-3", "Swiss 0-3"], viz.BASE),
    ]
    left = np.zeros(len(teams))
    for cols, color in segs:
        w = np.array([sum(place[t][c] for c in cols) for t in teams])
        ax.barh(y, w, left=left, height=0.66, color=color, edgecolor=viz.SURFACE, linewidth=1.5)
        left += w
    for yi, t in zip(y, teams):
        p = place[t]["Champion"]
        if p >= 0.05:          # label only where the segment fits
            ax.text(p / 2, yi, f"{p:.0%}", ha="center", va="center", color="white", fontsize=9.5, fontweight="semibold")
        ax.text(1.015, yi, f"{place[t]['P(KO)']:.0%}", ha="left", va="center", color=viz.INK2, fontsize=9.5)
        viz.team_mark(ax, t, (-0.085, yi), coords="mixed", zoom=0.12, grey=t in PLAYIN_TEAMS)
    ax.text(1.015, len(teams) - 0.35, "Reach KO", ha="left", va="bottom", color=viz.MUTED, fontsize=8.5)
    ax.set_yticks([])
    ax.set(xlim=(0, 1), ylim=(-0.6, len(teams) - 0.4))
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    viz.hairline_grid(ax, "x")
    ax.set_title("Where each team finishes", loc="left", pad=30)
    handles = [Patch(color=viz.BLUE_700, label="Champion"), Patch(color=viz.BLUE_550, label="Final"),
               Patch(color=viz.BLUE_400, label="Semi-final"), Patch(color=viz.BLUE_250, label="Quarter-final"),
               Patch(color=viz.BASE, label="Out in Swiss")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.1, -0.055), ncol=3, fontsize=8.5,
              handlelength=1, handleheight=1, columnspacing=1.0)
    return max(teams, key=lambda t: place[t]["Champion"])


def choice_panel(ax, cand: dict[str, dict[str, float]]) -> str:
    """Stacked bars of points for the top candidates: 50 x P(1st) + 20 x P(2nd) + 10 x P(3rd). Returns the pick."""
    top = sorted(cand, key=lambda c: -cand[c]["EV"])[:TOP_N]
    y = np.arange(len(top))[::-1]
    left = np.zeros(len(top))
    for k, (pts, color) in enumerate(zip(POINTS, (viz.BLUE_700, viz.BLUE_400, viz.BLUE_250))):
        seg = np.array([pts * cand[c][f"p{k + 1}"] for c in top])
        ax.barh(y, seg, left=left, height=0.66, color=color, edgecolor=viz.SURFACE, linewidth=1.5)
        left += seg
    for yi, c in zip(y, top):
        ax.text(cand[c]["EV"] + 0.2, yi, f"{cand[c]['EV']:.1f}", va="center", fontsize=10,
                fontweight="semibold" if c == top[0] else "normal", color=viz.INK)
        viz.team_mark(ax, c, (-0.085, yi), coords="mixed", zoom=0.12, grey=c in PLAYIN_TEAMS)
    ax.set_yticks([])
    ax.set(ylim=(-0.6, len(top) - 0.4), xlim=(0, max(cand[c]["EV"] for c in top) * 1.15))
    ax.set_xlabel("Expected points", fontsize=9.5)
    viz.hairline_grid(ax, "x")
    ax.set_title("How a ranked answer is chosen: Q18", loc="left", pad=30)
    handles = [Patch(color=viz.BLUE_700, label="1st × 50"), Patch(color=viz.BLUE_400, label="2nd × 20"),
               Patch(color=viz.BLUE_250, label="3rd × 10")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.1, -0.055), ncol=3, fontsize=8.5,
              handlelength=1, handleheight=1, columnspacing=1.0)
    return top[0]


def main() -> None:
    viz.apply()
    blocks = read_blocks((OUTPUTS / "crystal_sim.md").read_text(encoding="utf-8"))
    place = placements(blocks["Tournament outcome table"])
    cand = ranked(blocks[CHOICE_Q])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7.2), gridspec_kw={"width_ratios": [1, 0.92], "wspace": 0.42})
    fav = finish_panel(ax1, place)
    pick = choice_panel(ax2, cand)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.78, bottom=0.18)

    viz.header(fig,
               f"{fav} is the favourite, and expected points pick {pick} for Q18",
               f"{fav} wins {place[fav]['Champion']:.0%} of 20,000 simulations; {pick} leads Q18 on "
               f"{cand[pick]['EV']:.1f} expected points against {sorted(cand, key=lambda c: -cand[c]['EV'])[1]} "
               f"on {cand[sorted(cand, key=lambda c: -cand[c]['EV'])[1]]['EV']:.1f}")
    viz.footer(fig, "Source: outputs/crystal_sim.md, 20,000 simulations with rating uncertainty. "
                    "Ties are not split. Play-In teams shown in grey.")
    out = OUTPUTS / "charts" / "simulation_overview.png"
    fig.savefig(out, dpi=170, facecolor=viz.SURFACE)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
