"""Shared look for the README charts.

Colours are the light-surface values of the dataviz reference palette (ordinal blue ramp for
ordered stages, one categorical blue for emphasis, neutral grey for everything else). Logos and
champion icons come from data/raw/ (see ingest/assets.py).
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.image as mpimg
import numpy as np
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

from common.paths import ROOT

SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
BLUE_700, BLUE_550, BLUE_400, BLUE_250 = "#0d366b", "#1c5cab", "#3987e5", "#86b6ef"   # ordinal ramp
EMPHASIS = "#2a78d6"                                                                    # categorical slot 1
LOGO_DIR = ROOT / "data" / "raw" / "logos"
ICON_DIR = ROOT / "data" / "raw" / "ddragon" / "icons"


def apply() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans"],
        "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.facecolor": SURFACE, "axes.edgecolor": BASE, "axes.linewidth": 0.8,
        "axes.labelcolor": INK2, "axes.labelsize": 10, "axes.titlesize": 12,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": INK, "xtick.labelsize": 9, "ytick.labelsize": 10,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True, "legend.frameon": False,
    })


def header(fig, title: str, subtitle: str) -> None:
    """Left-aligned headline (the finding) with a one-line method subtitle underneath."""
    fig.text(0.03, 0.955, title, ha="left", va="top", fontsize=15, fontweight="semibold", color=INK)
    fig.text(0.03, 0.905, subtitle, ha="left", va="top", fontsize=10, color=INK2)


def footer(fig, text: str) -> None:
    fig.text(0.03, 0.02, text, ha="left", va="bottom", fontsize=8.5, color=MUTED)


def hairline_grid(ax, axis: str = "x") -> None:
    ax.grid(True, axis=axis, color=GRID, linewidth=0.8)
    ax.grid(False, axis="y" if axis == "x" else "x")
    ax.tick_params(length=0)


def image(path, grey: bool = False) -> np.ndarray:
    """Load a PNG; grey=True flattens it to luminance at reduced opacity (for Play-In / de-emphasised marks)."""
    img = mpimg.imread(path)
    if img.shape[2] == 3:
        img = np.dstack([img, np.ones(img.shape[:2])])
    if grey:
        lum = img[..., :3] @ np.array([0.299, 0.587, 0.114])
        img = np.dstack([np.repeat(lum[..., None], 3, axis=2), img[..., 3] * 0.45])
    return img


TEAMS = ["GEN", "AL", "TL", "G2", "LOS", "TSW", "HLE", "BLG", "LYON", "MKOI", "T1", "TES", "CFO", "IG", "DK",
         "FUR", "MVK", "C9", "KC"]
# Real logos are used only when every team has one; otherwise every team gets a code badge, so the
# charts stay consistent.
HAVE_LOGOS = all((LOGO_DIR / f"{t}.png").exists() for t in TEAMS)


def team_mark(ax, team: str, xy, coords: str = "data", zoom: float = 0.13, grey: bool = False,
              box=(0.5, 0.5), offset=(0, 0)):
    """Team logo or code badge at xy.
    coords: "data" (x and y in data units), "axes" (both axes fractions), "mixed" (x axes fraction, y data).
    grey: Play-In teams, drawn faded."""
    if not HAVE_LOGOS:
        tr = {"data": ax.transData, "axes": ax.transAxes, "mixed": ax.get_yaxis_transform()}[coords]
        ax.annotate(team, xy, xytext=offset, textcoords="offset points", xycoords=tr, ha="center", va="center",
                    fontsize=7.5, fontweight="semibold", color=MUTED if grey else "white",
                    bbox=dict(boxstyle="round,pad=0.28", fc=GRID if grey else INK2, ec="none"), zorder=5)
        return None
    xyc = {"data": "data", "axes": "axes fraction", "mixed": ("axes fraction", "data")}[coords]
    ab = AnnotationBbox(OffsetImage(image(LOGO_DIR / f"{team}.png", grey), zoom=zoom), xy, xycoords=xyc,
                        frameon=False, box_alignment=box, pad=0)
    ax.add_artist(ab)
    return ab


def icon(ax, icon_id: str, xy, zoom: float = 0.22, xycoords=("axes fraction", "data"), box=(1, 0.5)):
    path = ICON_DIR / f"{icon_id}.png"
    if not path.exists():
        return None
    ab = AnnotationBbox(OffsetImage(image(path), zoom=zoom), xy, xycoords=xycoords,
                        frameon=False, box_alignment=box, pad=0)
    ax.add_artist(ab)
    return ab
