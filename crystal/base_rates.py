"""T1.4b - Crystal Ball base rates from Worlds 2024 and 2025 game data.

Usage (from project root):  python crystal/base_rates.py

Reads data/pickems.duckdb READ-ONLY (never writes, no network calls).
Writes:
  outputs/base_rates.md          one section per Crystal Ball question, 2024 and 2025 side by side
  outputs/base_rates/*.csv       computed tables (reusable)

Stage logic (league 'WLDs' only; 'WLDQ' regional qualifiers are excluded):
  - Series = consecutive game_in_series for the same team pair on the same UTC day.
  - Knockouts = the last 7 series in time order: 4 QF, 2 SF, 1 Final (Bo5).
  - Play-In vs Swiss split = first day after the first gap of >= 2 days in the
    non-knockout schedule (both years have a 3-4 day break before Swiss).
  - Placement from the furthest stage reached.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "pickems.duckdb"
OUT_MD = ROOT / "outputs" / "base_rates.md"
OUT_DIR = ROOT / "outputs" / "base_rates"

YEARS = [2024, 2025]
EVENT_LEAGUE = "WLDs"
THRESH_SEC = 32 * 60
KILLS_FLAG = 15
CS_FLAG = 450
N_TOP = 10
MIN_GAMES = [5, 10]  # for champion questions (Q2, Q3)
MIN_GAMES_PRO = [1, 5]  # for pro questions (Q4-Q6)
STAGE_ORDER = ["Play-In", "Swiss", "QF", "SF", "F"]
STAGE_LABEL = {"Play-In": "Play-In", "Swiss": "Swiss", "QF": "Quarterfinal",
               "SF": "Semifinal", "F": "Final"}
PLACEMENT_ORDER = ["Champion", "Finalist", "SF", "QF", "Swiss exit", "Play-In exit"]
PRO_PLAYERS = {"Peyz": "Peyz", "Gumayusi": "Gumayusi", "Faker": "Faker"}
PATCH_RE = r"^16\.(17|18|19|20)(\.|$)"
PATCH_TARGETS = ["16.17", "16.18", "16.19", "16.20"]
# Domestic leagues (for Q15/Q16 regions). Pacific leagues merge into one "LCP" bucket.
REGION_OF_LEAGUE = {
    "LCK": "LCK", "LPL": "LPL", "LEC": "LEC",
    "LCS": "NA", "LTA N": "NA",
    "CBLOL": "BR", "LTA S": "BR",
    "LCP": "LCP (Pacific)", "PCS": "LCP (Pacific)", "VCS": "LCP (Pacific)",
    "LJL": "LCP (Pacific)", "LCO": "LCP (Pacific)",
    "LLA": "LLA",
}
INTL_LEAGUES = {"WLDs", "WLDQ", "MSI", "EWC", "EWCQ", "FST", "KeSPA Cup", "DCup",
                "DCGI", "ASI", "CCWS", "WSCI", "WLRQ", "IC", "IGNIS", "LDL",
                "NLC Aurora Open", "AmCh", "AM"}
# Finals MVP history, kept from the earlier verified section (do not regenerate).
FINALS_MVP_VERIFIED = [
    ("2022", "Kingen", "DRX", "Top"),
    ("2023", "Zeus", "T1", "Top"),
    ("2024", "Faker", "T1", "Mid"),
    ("2025", "Gumayusi", "T1", "Bot"),
]


# ---------------------------------------------------------------- helpers

def md_table(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0:
        return "_(no rows)_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row.values) + " |")
    return "\n".join(lines)


def fmt(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{x:.{nd}f}"


def mode_or_none(s: pd.Series):
    m = s.dropna().mode()
    return m.iloc[0] if len(m) else None


def add_disp(df: pd.DataFrame, fn) -> pd.DataFrame:
    """Add a 'disp' column built row by row from fn(row)."""
    df = df.copy()
    df["disp"] = [fn(r) for r in df.itertuples(index=False)]
    return df


def side_by_side(per_year: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Rank-aligned side-by-side view of per-year top-N frames (each has a 'rank' column)."""
    parts = []
    for y in YEARS:
        f = per_year[y].set_index("rank").add_prefix(f"{y} ")
        parts.append(f)
    out = pd.concat(parts, axis=1).reset_index()
    return out


def leader_answer(top: dict[int, pd.DataFrame], col: str, fmt_val=None) -> str:
    a, b = top[2024], top[2025]
    if len(a) == 0 or len(b) == 0:
        return "N/A (no qualifying rows)"
    n24, n25 = a[col].iloc[0], b[col].iloc[0]
    if n24 == n25:
        return f"{n24} (top in both years)"
    overlap = sorted(set(a[col].head(3)) & set(b[col].head(3)))
    txt = f"no single leader: 2024 {n24}, 2025 {n25}"
    if overlap:
        txt += f"; in both years' top 3: {', '.join(overlap)}"
    return txt


# ---------------------------------------------------------------- loading

def load(con: duckdb.DuckDBPyConnection):
    games = con.sql(
        f"select * from games where league = '{EVENT_LEAGUE}' and year in (2024, 2025)"
    ).df()
    pg = con.sql(
        f"select p.*, g.year from player_games p join games g using (game_id) "
        f"where g.league = '{EVENT_LEAGUE}' and g.year in (2024, 2025)"
    ).df()
    # domestic league per team per year (by team_id), excluding international codes
    dom = con.sql(
        "select year, league, tid, count(*) n from ("
        " select year, league, blue_team_id tid from games"
        " union all select year, league, red_team_id from games) x "
        "group by all"
    ).df()
    dom = dom[~dom.league.isin(INTL_LEAGUES)]
    dom = dom.sort_values(["year", "tid", "n"], ascending=[True, True, False])
    dom_best = dom.groupby(["year", "tid"]).head(1)[["year", "tid", "league"]]
    # team_id -> team name in WLDs
    names = pd.concat([
        games[["year", "blue_team_id", "blue_team"]].rename(columns={"blue_team_id": "tid", "blue_team": "team"}),
        games[["year", "red_team_id", "red_team"]].rename(columns={"red_team_id": "tid", "red_team": "team"}),
    ]).drop_duplicates(["year", "tid"])
    teams = names.merge(dom_best, on=["year", "tid"], how="left")
    teams["region"] = teams.league.map(REGION_OF_LEAGUE).fillna(teams.league)
    return games, pg, teams


def load_bonus(con: duckdb.DuckDBPyConnection):
    intl = con.sql(
        "select * from games where league in ('MSI','FST','EWC') and year = 2026"
    ).df()
    intl_pg = con.sql(
        "select p.*, g.year, g.league from player_games p join games g using (game_id) "
        "where g.league in ('MSI','FST','EWC') and g.year = 2026"
    ).df()
    # 16.17-16.20 presence: playoffs of the 6 domestic leagues + WLDQ
    meta = con.sql(
        "select * from games where ((league in ('LCK','LPL','LEC','LCS','LCP','CBLOL') "
        " and year = 2026 and playoffs) or (league = 'WLDQ' and year = 2026)) "
        f"and regexp_matches(patch, '{PATCH_RE}')"
    ).df()
    return intl, intl_pg, meta


# ---------------------------------------------------------------- stage structure

def build_series(g: pd.DataFrame) -> pd.DataFrame:
    """Assign series_id to each game (consecutive game_in_series, same pair, same day)."""
    g = g.sort_values(["date_utc", "game_id"]).copy()
    g["day"] = g["date_utc"].dt.normalize()
    g["pair"] = ["|".join(sorted([b, r])) for b, r in zip(g.blue_team, g.red_team)]
    current: dict = {}
    sid_counter = 0
    sids = []
    for day, pair, gis in zip(g.day, g.pair, g.game_in_series):
        key = (day, pair)
        cur = current.get(key)
        if cur is None or gis != cur[1] + 1:
            sid_counter += 1
            cur = (sid_counter, gis)
        else:
            cur = (cur[0], gis)
        current[key] = cur
        sids.append(cur[0])
    g["series_id"] = sids
    return g


def tag_stages(g: pd.DataFrame, year: int):
    """Return (games with stage columns, series table, swiss_start date)."""
    s = (g.groupby("series_id")
         .agg(start=("date_utc", "min"), day=("day", "first"), n_games=("game_id", "size"),
              first_game=("game_id", "first"), max_gis=("game_in_series", "max"))
         .reset_index())
    # winner = team with most game wins in the series
    wins = g.groupby(["series_id", "winner_team"]).size().rename("w").reset_index()
    wins = wins.sort_values(["series_id", "w"], ascending=[True, False]).groupby("series_id").head(1)
    s = s.merge(wins.rename(columns={"winner_team": "winner"})[["series_id", "winner"]], on="series_id")
    pairs = g.groupby("series_id").agg(team_a=("blue_team", "first"), team_b=("red_team", "first")).reset_index()
    s = s.merge(pairs, on="series_id")
    s["loser"] = np.where(s.winner == s.team_a, s.team_b, s.team_a)
    s = s.sort_values(["start", "first_game"]).reset_index(drop=True)

    if len(s) < 8:
        raise RuntimeError(f"{year}: too few series ({len(s)})")
    stage = ["?"] * len(s)
    ko_start = len(s) - 7
    for i in range(ko_start, len(s)):
        k = i - ko_start
        stage[i] = "QF" if k < 4 else ("SF" if k < 6 else "F")
    # Play-In vs Swiss: first gap >= 2 days in the non-knockout schedule
    pre = s.iloc[:ko_start]
    days = sorted(pre.day.unique())
    swiss_start = None
    for a, b in zip(days[:-1], days[1:]):
        if (b - a).days >= 2:
            swiss_start = b
            break
    if swiss_start is None:
        raise RuntimeError(f"{year}: no Play-In/Swiss break found")
    for i in range(ko_start):
        stage[i] = "Play-In" if s.day.iloc[i] < swiss_start else "Swiss"
    s["stage"] = stage
    s["format"] = np.where(s.n_games == 1, "Bo1 (single game)", "multi-game series")

    gg = g.merge(s[["series_id", "stage", "n_games", "format", "winner", "loser"]], on="series_id", how="left")
    if gg.stage.isna().any():
        raise RuntimeError(f"{year}: games without a stage")
    return gg, s, pd.Timestamp(swiss_start)


def placements(gg: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """One row per team with the furthest stage reached."""
    team_stages: dict[str, set] = {}
    for _, r in s.iterrows():
        for t in (r.team_a, r.team_b):
            team_stages.setdefault(t, set()).add(r.stage)
    final_winner = s.loc[s.stage == "F", "winner"].iloc[0]
    rows = []
    for t, st in team_stages.items():
        if "F" in st:
            p = "Champion" if t == final_winner else "Finalist"
        elif "SF" in st:
            p = "SF"
        elif "QF" in st:
            p = "QF"
        elif "Swiss" in st:
            p = "Swiss exit"
        else:
            p = "Play-In exit"
        g_t = gg[(gg.blue_team == t) | (gg.red_team == t)]
        rows.append({
            "team": t, "placement": p, "reached_knockouts": bool(st & {"QF", "SF", "F"}),
            "games": len(g_t),
            "games_playin": int((g_t.stage == "Play-In").sum()),
            "games_swiss": int((g_t.stage == "Swiss").sum()),
            "games_ko": int(g_t.stage.isin(["QF", "SF", "F"]).sum()),
        })
    out = pd.DataFrame(rows)
    out["placement"] = pd.Categorical(out.placement, PLACEMENT_ORDER, ordered=True)
    return out.sort_values(["placement", "team"]).reset_index(drop=True)


# ---------------------------------------------------------------- champion questions

def champ_long(g: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for side in ("blue", "red"):
        for kind in ("picks", "bans"):
            col = f"{side}_{kind}"
            s = g[["game_id", col]].copy()
            s["champ"] = s[col].fillna("").str.split(",")
            s = s.explode("champ")
            s["champ"] = s["champ"].str.strip()
            s = s[s["champ"] != ""]
            s["kind"] = "pick" if kind == "picks" else "ban"
            parts.append(s[["game_id", "champ", "kind"]])
    return pd.concat(parts, ignore_index=True)


def presence_table(cl: pd.DataFrame, n_games: int) -> pd.DataFrame:
    present = cl.drop_duplicates(["game_id", "champ"]).groupby("champ").size().rename("games_present")
    picks = cl[cl.kind == "pick"].groupby("champ").size().rename("picks")
    bans = cl[cl.kind == "ban"].groupby("champ").size().rename("bans")
    df = pd.concat([present, picks, bans], axis=1).fillna(0).astype(int)
    df["presence_pct"] = 100.0 * df.games_present / n_games
    df["appearances_per_game"] = (df.picks + df.bans) / n_games
    df = df.sort_values(["presence_pct", "picks", "champ"], ascending=[False, False, True])
    df = df.reset_index().rename(columns={"index": "champ"})
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def champ_stats(pg: pd.DataFrame) -> pd.DataFrame:
    d = pg.groupby("champion").agg(
        games=("win", "size"), wins=("win", "sum"),
        deaths_mean=("deaths", "mean"), deaths_total=("deaths", "sum"),
    ).reset_index()
    d["win_rate_pct"] = 100.0 * d.wins / d.games
    return d


def top_champs(stats: pd.DataFrame, col: str, min_games: int, asc=False) -> pd.DataFrame:
    x = stats[stats.games >= min_games].sort_values([col, "games", "champion"],
                                                    ascending=[asc, False, True]).head(N_TOP).copy()
    x.insert(0, "rank", range(1, len(x) + 1))
    return x


# ---------------------------------------------------------------- player questions

def player_table(pg: pd.DataFrame, placement_by_team: dict) -> pd.DataFrame:
    pg = pg.copy()
    pg["kp"] = np.where(pg.team_kills > 0, (pg.kills + pg.assists) / pg.team_kills.where(pg.team_kills > 0), np.nan)
    t = pg.groupby("player_id").agg(
        player=("player", mode_or_none), team=("team", mode_or_none), role=("role", mode_or_none),
        games=("win", "size"), kills=("kills", "sum"), deaths=("deaths", "sum"),
        assists=("assists", "sum"), team_kills=("team_kills", "sum"),
        damage=("damage", "sum"), kp_per_game=("kp", "mean"),
    ).reset_index()
    t["kda"] = (t.kills + t.assists) / t.deaths.clip(lower=1)
    t["avg_damage"] = t.damage / t.games
    t["kp_aggregate"] = (t.kills + t.assists) / t.team_kills.where(t.team_kills > 0)
    t["placement"] = t.team.map(placement_by_team).astype(str)
    return t


def top_pros(t: pd.DataFrame, col: str, min_games: int) -> pd.DataFrame:
    x = t[t.games >= min_games].sort_values([col, "games", "player"], ascending=[False, False, True]).head(N_TOP).copy()
    x.insert(0, "rank", range(1, len(x) + 1))
    return x


# ---------------------------------------------------------------- other questions

def duration_split(g: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    def one(x: pd.DataFrame, label: str) -> dict:
        d = x.duration_sec.astype(float)
        return {"group": label, "games": len(x),
                "under_32_games": int((d < THRESH_SEC).sum()),
                "over_or_equal_32_games": int((d >= THRESH_SEC).sum()),
                "under_32_pct": 100.0 * (d < THRESH_SEC).mean() if len(x) else np.nan,
                "mean_min": d.mean() / 60 if len(x) else np.nan,
                "median_min": d.median() / 60 if len(x) else np.nan}
    rows = [one(g, "All")]
    if by:
        for k, x in g.groupby(by):
            rows.append(one(x, str(k)))
    return pd.DataFrame(rows)


def event_flags(pg: pd.DataFrame, g: pd.DataFrame):
    """Game-level 15+ kill and 450+ CS flags, plus single-game maxima."""
    kmax = pg.groupby("game_id").kills.max()
    cmax = pg.groupby("game_id").cs.max()
    n = len(g)
    k_games = int((kmax >= KILLS_FLAG).sum())
    c_games = int((cmax >= CS_FLAG).sum())
    top_k = pg.sort_values(["kills", "player"], ascending=[False, True]).head(3)[
        ["game_id", "player", "champion", "team", "kills", "deaths", "assists"]]
    top_c = pg.sort_values(["cs", "player"], ascending=[False, True]).head(3)[
        ["game_id", "player", "champion", "team", "cs", "kills"]]
    return {"n_games": n, "games_15k": k_games, "rate_15k": k_games / n if n else np.nan,
            "max_kills": int(pg.kills.max()), "games_450cs": c_games,
            "rate_450cs": c_games / n if n else np.nan, "max_cs": float(pg.cs.max()),
            "top_kills": top_k, "top_cs": top_c}


def finals_context(gg: pd.DataFrame, pg: pd.DataFrame, s: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    fin = s[s.stage == "F"].iloc[0]
    winner = fin.winner
    fgames = gg[gg.series_id == fin.series_id]
    gids = set(fgames.game_id)
    p = pg[pg.game_id.isin(gids) & (pg.team == winner)]
    t = p.groupby("player").agg(
        role=("role", mode_or_none), games=("win", "size"), kills=("kills", "sum"),
        deaths=("deaths", "sum"), assists=("assists", "sum"), damage=("damage", "sum"),
        cs=("cs", "mean"),
    ).reset_index()
    t["kda"] = (t.kills + t.assists) / t.deaths.clip(lower=1)
    t["kills_per_game"] = t.kills / t.games
    t["dmg_per_game"] = t.damage / t.games
    t = t.sort_values(["kills", "player"], ascending=[False, True])
    t["series"] = f"{fin.team_a} vs {fin.team_b} ({fin.n_games} games, {winner} won {int((fgames.winner_team == winner).sum())}-{int((fgames.winner_team != winner).sum())} by game)"
    return winner, t[["player", "role", "games", "kills", "deaths", "assists", "kda",
                      "kills_per_game", "dmg_per_game", "cs"]].rename(columns={"cs": "cs_mean"})


# ---------------------------------------------------------------- main compute

def compute_year(games: pd.DataFrame, pg: pd.DataFrame, teams: pd.DataFrame, year: int) -> dict:
    g0 = games[games.year == year].copy()
    p0 = pg[pg.year == year].copy()
    g = build_series(g0)
    gg, s, swiss_start = tag_stages(g, year)
    pl = placements(gg, s)
    pl = pl.merge(teams[teams.year == year][["team", "region", "league"]], on="team", how="left")
    placement_by_team = dict(zip(pl.team, pl.placement))
    p0["stage"] = p0.game_id.map(dict(zip(gg.game_id, gg.stage)))
    p0["format"] = p0.game_id.map(dict(zip(gg.game_id, gg.format)))
    if p0.stage.isna().any():
        raise RuntimeError(f"{year}: player rows without stage")

    out: dict = {"year": year, "games": gg, "series": s, "placements": pl,
                 "swiss_start": swiss_start, "pg": p0}
    n = len(gg)
    out["n_games"] = n
    out["n_series"] = len(s)
    out["stage_counts"] = gg.groupby("stage").size().reindex(STAGE_ORDER).fillna(0).astype(int)

    cl = champ_long(gg)
    out["champ_long"] = cl
    pres = presence_table(cl, n)
    out["q1"] = pres.head(N_TOP)

    stats = champ_stats(p0)
    out["q2_5"] = top_champs(stats, "win_rate_pct", MIN_GAMES[0])
    out["q2_10"] = top_champs(stats, "win_rate_pct", MIN_GAMES[1])
    out["q3_5"] = top_champs(stats, "deaths_mean", MIN_GAMES[0])
    out["q3_10"] = top_champs(stats, "deaths_mean", MIN_GAMES[1])
    out["champ_stats"] = stats

    t = player_table(p0, placement_by_team)
    out["players"] = t
    for m in MIN_GAMES_PRO:
        out[f"q4_{m}"] = top_pros(t, "kda", m)
        out[f"q5_{m}"] = top_pros(t, "avg_damage", m)
        out[f"q6avg_{m}"] = top_pros(t, "kp_per_game", m)
        out[f"q6agg_{m}"] = top_pros(t, "kp_aggregate", m)

    def player_totals(name: str) -> dict:
        x = p0[p0.player == name]
        return {"year": year, "player": name, "team": mode_or_none(x.team) if len(x) else "-",
                "games": len(x), "kills": int(x.kills.sum()),
                "kills_per_game": x.kills.mean() if len(x) else np.nan}
    out["q7"] = pd.DataFrame([player_totals("Peyz"), player_totals("Gumayusi")])
    out["q8"] = pd.DataFrame([player_totals("Faker")])
    t1 = gg[(gg.blue_team == "T1") | (gg.red_team == "T1")]
    out["t1_games"] = len(t1)

    picks = cl[cl.kind == "pick"].groupby("champ").size()
    bans = cl[cl.kind == "ban"].groupby("champ").size()
    out["q9"] = {"teemo_picks": int(picks.get("Teemo", 0)), "teemo_bans": int(bans.get("Teemo", 0)),
                 "champs_picked_once": int((picks == 1).sum())}
    out["q10"] = {"unique_picked": int(len(picks)),
                  "unique_picked_or_banned": int(len(set(cl.champ)))}

    out["q11"] = duration_split(gg)
    gg["format_short"] = np.where(gg.n_games == 1, "Bo1 (single game)", "Bo3/Bo5 series games")
    out["q11_format"] = duration_split(gg, "format_short")
    out["q11_stage"] = duration_split(gg, "stage")

    out["q12_13"] = event_flags(p0, gg)
    out["q14_winner"], out["q14_table"] = finals_context(gg, p0, s)

    ko = pl[pl.reached_knockouts]
    out["ko_teams"] = ko
    out["ko_regions"] = ko.region.nunique()
    out["ko_region_list"] = ko.groupby("region").team.apply(lambda x: ", ".join(sorted(x))).to_dict()
    out["ko_na"] = ko[ko.region == "NA"].team.tolist()

    t_names = {"T1": None, "Hanwha Life Esports": None}
    out["q17"] = {k: pl.loc[pl.team == k, "placement"].astype(str).tolist() for k in t_names}

    short = gg.sort_values(["duration_sec", "game_id"]).head(5)
    out["q18"] = short.assign(
        winner_team_out=short.winner_team,
        opponent=np.where(short.winner_team == short.blue_team, short.red_team, short.blue_team),
    )[["winner_team_out", "opponent", "duration_sec", "stage", "patch", "game_id"]].rename(
        columns={"winner_team_out": "winner"})
    return out


# ---------------------------------------------------------------- bonus (2026)

def bonus_2026(intl, intl_pg, meta):
    res = {}
    n = len(intl)
    res["n_games"] = n
    res["by_event"] = intl.groupby("league").size().rename("games").reset_index()
    cl = champ_long(intl)
    res["presence"] = presence_table(cl, n).head(N_TOP)
    picks = cl[cl.kind == "pick"].groupby("champ").size()
    res["unique_picked"] = int(len(picks))
    res["teemo_picks"] = int(picks.get("Teemo", 0))
    res["teemo_bans"] = int(cl[(cl.kind == "ban") & (cl.champ == "Teemo")].shape[0])
    res["unique_picked_or_banned"] = int(cl.champ.nunique())
    res["dur"] = duration_split(intl)
    res["flags"] = event_flags(intl_pg, intl)
    res["flags_cs_games"] = res["flags"]["games_450cs"]
    # by-event flags for the table
    rows = []
    for ev, gsub in intl.groupby("league"):
        pgs = intl_pg[intl_pg.game_id.isin(set(gsub.game_id))]
        f = event_flags(pgs, gsub)
        cle = champ_long(gsub)
        rows.append({"event": ev, "games": len(gsub), "unique_picked": int(cle[cle.kind == "pick"].champ.nunique()),
                     "under_32_pct": 100 * (gsub.duration_sec < THRESH_SEC).mean(),
                     "games_15k": f["games_15k"], "games_450cs": f["games_450cs"],
                     "max_kills": f["max_kills"], "max_cs": f["max_cs"]})
    res["by_event_table"] = pd.DataFrame(rows)
    # patch 16.17-16.20 presence across domestic playoffs + WLDQ
    res["patch_meta_n"] = len(meta)
    res["patch_meta_counts"] = meta.groupby(["league", "patch"]).size().rename("games").reset_index()
    cm = champ_long(meta)
    res["patch_presence"] = presence_table(cm, len(meta)).head(25) if len(meta) else pd.DataFrame()
    return res


# ---------------------------------------------------------------- report

def write_outputs(R: dict, B: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}

    def add(name: str, per_year: dict | pd.DataFrame, key_year=True):
        if isinstance(per_year, dict):
            tables[name] = pd.concat([v.assign(year=y) for y, v in per_year.items()], ignore_index=True)
        else:
            tables[name] = per_year

    add("q01_presence", {y: R[y]["q1"] for y in YEARS})
    add("q02_winrate_min5", {y: R[y]["q2_5"] for y in YEARS})
    add("q02_winrate_min10", {y: R[y]["q2_10"] for y in YEARS})
    add("q03_deaths_min5", {y: R[y]["q3_5"] for y in YEARS})
    add("q03_deaths_min10", {y: R[y]["q3_10"] for y in YEARS})
    for m in MIN_GAMES_PRO:
        add(f"q04_kda_min{m}", {y: R[y][f"q4_{m}"] for y in YEARS})
        add(f"q05_damage_min{m}", {y: R[y][f"q5_{m}"] for y in YEARS})
        add(f"q06_kp_avg_min{m}", {y: R[y][f"q6avg_{m}"] for y in YEARS})
        add(f"q06_kp_agg_min{m}", {y: R[y][f"q6agg_{m}"] for y in YEARS})
    add("q07_peyz_gumayusi", {y: R[y]["q7"] for y in YEARS})
    add("q08_faker", {y: R[y]["q8"] for y in YEARS})
    add("q11_duration", {y: R[y]["q11"] for y in YEARS})
    add("q11_duration_by_format", {y: R[y]["q11_format"] for y in YEARS})
    add("q11_duration_by_stage", {y: R[y]["q11_stage"] for y in YEARS})
    add("q14_final_winner_players", {y: R[y]["q14_table"] for y in YEARS})
    add("placements", {y: R[y]["placements"] for y in YEARS})
    add("series_structure", {y: R[y]["series"] for y in YEARS})
    add("all_players", {y: R[y]["players"] for y in YEARS})
    add("all_champion_stats", {y: R[y]["champ_stats"] for y in YEARS})
    add("q18_shortest_games", {y: R[y]["q18"] for y in YEARS})
    add("bonus_2026_by_event", B["by_event_table"])
    add("bonus_2026_presence", B["presence"])
    add("bonus_2026_patch_1617_1620_presence", B["patch_presence"])
    add("bonus_2026_duration", B["dur"])
    for name, df in tables.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8")

    L: list[str] = []
    w = L.append
    w("# Worlds 2024 / 2025 base rates for the Crystal Ball (T1.4b)")
    w("")
    w("Source: `data/pickems.duckdb` (read-only), league `WLDs` only; `WLDQ` regional qualifiers excluded. "
      "Generated by `python crystal/base_rates.py`. Tables: `outputs/base_rates/*.csv`.")
    w("")
    for y in YEARS:
        r = R[y]
        w(f"- **{y}**: {r['n_games']} games, {r['n_series']} series, patch "
          f"{', '.join(sorted(r['games'].patch.unique()))}, Play-In/Swiss break at {r['swiss_start'].date()}; "
          f"stage games: " + ", ".join(f"{k} {int(v)}" for k, v in r["stage_counts"].items()) + ".")
    w("")
    w("## Stage and placement method")
    w("")
    w("- Series = consecutive `game_in_series` for one team pair on one UTC day. Bo1 = single-game series.")
    w("- Knockouts = last 7 series in time order (QF x4, SF x2, Final). The `playoffs` flag is False for every "
      "Worlds game, so it is not used.")
    w("- Play-In vs Swiss = first day after the first gap of 2+ days in the pre-knockout schedule.")
    w("- Placement = furthest stage reached: Champion, Finalist, SF (3rd-4th), QF (5th-8th), Swiss exit, Play-In exit.")
    w("- Presence (Q1) = share of games where the champion was picked or banned (each game counts once). "
      "The raw (picks+bans)/games ratio is in the CSV as `appearances_per_game`.")
    w("- 2025 caveat: the Oct 14-19 block (35 games, 17 teams) holds 3-win qualifiers who go straight to the knockouts "
      "(KT Rolster, Anyone's Legend), so its label 'Play-In' means block 1, not the 2024-style Play-In. "
      "The Oct 22-25 block (21 games, 12 teams) is labelled 'Swiss'. The 'Play-In exit' and 'Swiss exit' labels are "
      "therefore only block labels for 2025. Knockout teams and the final placements are not affected.")
    w("")
    w("### Placements (both years)")
    w("")
    for y in YEARS:
        pl = R[y]["placements"]
        show = pl[["placement", "team", "region", "games", "games_playin", "games_swiss", "games_ko"]].copy()
        show["placement"] = show.placement.astype(str)
        w(f"**{y}**")
        w("")
        w(md_table(show))
        w("")

    # --- Q1
    w("## 1. Highest presence champion (picks + bans / games)")
    w("")
    sbs = side_by_side({y: add_disp(R[y]["q1"], lambda r: f"{r.champ} {r.presence_pct:.1f}% "
                                    f"(P {r.picks}, B {r.bans})")[["rank", "disp"]] for y in YEARS})
    w(md_table(sbs.rename(columns={f"{YEARS[0]} disp": "2024 (champ presence, picks/bans)",
                                   f"{YEARS[1]} disp": "2025 (champ presence, picks/bans)"})))
    w("")
    a24, a25 = R[2024]["q1"], R[2025]["q1"]
    top_common = sorted(set(a24.champ.head(5)) & set(a25.champ.head(5)))
    w(f"**Base-rate answer for 2026:** {leader_answer({2024: a24, 2025: a25}, 'champ')}. "
      f"Champions in both years' top 5: {', '.join(top_common) if top_common else 'none'}.")
    w("")
    ov5 = sorted(set(a24.champ.head(5)) & set(a25.champ.head(5)))
    w(f"**Confidence:** low. {len(ov5)} champion(s) appear in both years' top 5, so the presence leader is not stable across "
      "events. Bans count toward presence, and the 2025 Fearless draft changed the ban pattern.")
    w("")

    # --- Q2
    w("## 2. Highest win-rate champion (min games 5 and 10)")
    w("")
    for mg, key in [(5, "q2_5"), (10, "q2_10")]:
        per = {y: add_disp(R[y][key], lambda r: f"{r.champion} {r.win_rate_pct:.1f}% ({r.wins}/{r.games})")[["rank", "disp"]]
            for y in YEARS}
        w(f"**min games {mg}**")
        w("")
        w(md_table(side_by_side(per).rename(columns={"2024 disp": "2024 (win rate, wins/games)",
                                                     "2025 disp": "2025 (win rate, wins/games)"})))
        w("")
    w(f"**Base-rate answer for 2026:** min 5: {leader_answer({y: R[y]['q2_5'] for y in YEARS}, 'champion')}. "
      f"min 10: {leader_answer({y: R[y]['q2_10'] for y in YEARS}, 'champion')}.")
    w("")
    w("**Confidence:** low. Win rate for champions with 5 to 10 games is noisy, and the answer depends on the min-games rule.")
    w("")

    # --- Q3
    w("## 3. Highest average deaths per game champion (min games 5 and 10)")
    w("")
    for mg, key in [(5, "q3_5"), (10, "q3_10")]:
        per = {y: add_disp(R[y][key], lambda r: f"{r.champion} {r.deaths_mean:.2f} ({r.games}g)")[["rank", "disp"]]
            for y in YEARS}
        w(f"**min games {mg}**")
        w("")
        w(md_table(side_by_side(per).rename(columns={"2024 disp": "2024 (deaths/game, games)",
                                                     "2025 disp": "2025 (deaths/game, games)"})))
        w("")
    w(f"**Base-rate answer for 2026:** min 5: {leader_answer({y: R[y]['q3_5'] for y in YEARS}, 'champion')}. "
      f"min 10: {leader_answer({y: R[y]['q3_10'] for y in YEARS}, 'champion')}.")
    w("")
    w("**Confidence:** low to medium. The leaders are mostly engage champions (Nautilus, Rell, Leona, Alistar, Vi), so the "
      "ranking reflects the game plan as much as the player.")
    w("")

    # --- Q4-Q6
    def pro_block(qname, col_key, val_label, fmt_fn, src_prefix, agg=False):
        w(f"## {qname}")
        w("")
        for mg in MIN_GAMES_PRO:
            per = {}
            for y in YEARS:
                d = R[y][f"{src_prefix}_{mg}"]
                disp = [f"{r.player} ({r.team}, {r.role}, {r.placement}) {fmt_fn(r)} [{int(r.games)}g]"
                        for r in d.itertuples(index=False)]
                per[y] = pd.DataFrame({"rank": d["rank"].values, "disp": disp})
            w(f"**min games {mg}**")
            w("")
            w(md_table(side_by_side(per).rename(columns={"2024 disp": f"2024 ({val_label})",
                                                         "2025 disp": f"2025 ({val_label})"})))
            w("")
        w(f"**Base-rate answer for 2026:** min 1: "
          f"{leader_answer({y: R[y][f'{src_prefix}_1'] for y in YEARS}, 'player')}. "
          f"min 5: {leader_answer({y: R[y][f'{src_prefix}_5'] for y in YEARS}, 'player')}.")
        w("")

    pro_block("4. Highest average KDA pro (total (K+A)/max(D,1))", "kda", "KDA",
              lambda r: f"{r.kda:.2f}", "q4")
    w("**Confidence:** low. KDA is dominated by small death counts, and most leaders have 8 to 17 games. Use the min-5 list as a shortlist.")
    w("")
    pro_block("5. Highest average damage per game pro", "avg_damage", "dmg/game",
              lambda r: f"{r.avg_damage:.0f}", "q5")
    w("**Confidence:** medium. Damage per game depends on role and team style.")
    w("")
    pro_block("6a. Highest average kill participation pro (per-game average of (K+A)/team kills)", "kp", "KP avg",
              lambda r: f"{100 * r.kp_per_game:.1f}%", "q6avg")
    pro_block("6b. Highest aggregate kill participation pro (sum(K+A)/sum(team kills))", "kp", "KP agg",
              lambda r: f"{100 * r.kp_aggregate:.1f}%", "q6agg")
    w("**Confidence:** low to medium. Supports and junglers lead these lists in both years, and each year has only 84 to 106 games.")
    w("")

    # --- Q7
    w("## 7. Peyz and Gumayusi: total kills, games, kills per game")
    w("")
    rows = []
    for y in YEARS:
        for _, r in R[y]["q7"].iterrows():
            rows.append({"year": y, "player": r.player, "team": r.team, "games": int(r.games),
                         "kills": int(r.kills), "kills_per_game": fmt(r.kills_per_game, 2)})
    w(md_table(pd.DataFrame(rows)))
    w("")
    kp = {y: {r.player: r.kills_per_game for _, r in R[y]["q7"].iterrows()} for y in YEARS}
    def kpg_txt(y, name):
        rr = R[y]["q7"][R[y]["q7"].player == name].iloc[0]
        if rr.games == 0:
            return f"did not play Worlds {y}"
        return f"{rr.kills_per_game:.2f} kills/game in {int(rr.games)} games ({y})"
    w(f"**Base-rate answer for 2026:** Peyz: {kpg_txt(2024, 'Peyz')}; {kpg_txt(2025, 'Peyz')}. "
      f"Gumayusi: {kpg_txt(2024, 'Gumayusi')}; {kpg_txt(2025, 'Gumayusi')}. "
      "Total kills = kills per game x games played, so the totals depend on how far each team goes (see the games-per-team table).")
    w("")
    w("**Confidence:** medium for Gumayusi (two events of data). Low for Peyz (one event; no 2025 Worlds games).")
    w("")

    # --- Q8
    w("## 8. Faker: kills, games, kills per game; T1 total games")
    w("")
    rows = []
    for y in YEARS:
        f = R[y]["q8"].iloc[0]
        rows.append({"year": y, "player": "Faker", "team": f.team, "games": int(f.games),
                     "kills": int(f.kills), "kills_per_game": fmt(f.kills_per_game, 2),
                     "T1 games (year)": R[y]["t1_games"]})
    w(md_table(pd.DataFrame(rows)))
    w("")
    k24 = R[2024]["q8"].iloc[0]
    k25 = R[2025]["q8"].iloc[0]
    avg_rate = (k24.kills + k25.kills) / max(k24.games + k25.games, 1)
    games_needed = 84 / avg_rate if avg_rate > 0 else np.nan
    w(f"**Reference:** 616 career kills entering 2026 + 84 needed = 700. Faker's Worlds 2024 + 2025 kills in this data: "
      f"{int(k24.kills + k25.kills)} (not the full career). A single-year Worlds total of 84 would be "
      f"{fmt(84 / max(k24.kills, 1), 1)}x 2024's total and {fmt(84 / max(k25.kills, 1), 1)}x 2025's.")
    w("")
    w(f"**Base-rate answer for 2026:** pooled rate {fmt(avg_rate, 2)} kills per game, so 84 kills need about "
      f"{fmt(games_needed, 0)} games. T1 played {R[2024]['t1_games']} games in 2024 (title) and {R[2025]['t1_games']} in 2025 "
      f"(title). Faker's 2025 run ({int(k25.kills)} kills in {int(k25.games)} games) clears 84; his 2024 run "
      f"({int(k24.kills)} in {int(k24.games)}) does not. 84 needs a title-length run, and the answer depends on T1's "
      f"game count from the T2.4 simulation.")
    w("")
    w("**Confidence:** medium on the rate (two events, 41 games). The main uncertainty is T1's game count in 2026.")
    w("")

    # --- Q9
    w("## 9. Teemo picked at least once; champions picked exactly once")
    w("")
    rows = [{"year": y, "Teemo picks": R[y]["q9"]["teemo_picks"], "Teemo bans": R[y]["q9"]["teemo_bans"],
             "champions picked exactly once": R[y]["q9"]["champs_picked_once"]} for y in YEARS]
    w(md_table(pd.DataFrame(rows)))
    w("")
    tp = [R[y]["q9"]["teemo_picks"] > 0 for y in YEARS]
    w(f"**Base-rate answer for 2026:** Teemo was picked in {sum(tp)} of 2 Worlds events (picks or bans: "
      f"{R[2024]['q9']['teemo_picks'] + R[2024]['q9']['teemo_bans']} in 2024, "
      f"{R[2025]['q9']['teemo_picks'] + R[2025]['q9']['teemo_bans']} in 2025). Base answer: no. "
      f"Champions picked exactly once: {R[2024]['q9']['champs_picked_once']} (2024) and "
      f"{R[2025]['q9']['champs_picked_once']} (2025). The 2026 international sample has "
      f"{B['teemo_picks']} Teemo picks in {B['n_games']} games.")
    w("")
    w("**Confidence:** low. Zero hits in two events is a weak base rate for a rare pick. Re-check the 2026 sample "
      "before submitting.")
    w("")

    # --- Q10
    w("## 10. Unique champions picked; unique picked or banned")
    w("")
    rows = [{"year": y, "unique picked": R[y]["q10"]["unique_picked"],
             "unique picked or banned": R[y]["q10"]["unique_picked_or_banned"]} for y in YEARS]
    w(md_table(pd.DataFrame(rows)))
    w("")
    up = {y: R[y]["q10"]["unique_picked"] for y in YEARS}
    upb = {y: R[y]["q10"]["unique_picked_or_banned"] for y in YEARS}
    w(f"**Base-rate answer for 2026:** picked {up[2024]} (2024) and {up[2025]} (2025, Fearless); picked or banned "
      f"{upb[2024]} and {upb[2025]}. The picked count was the same in both years; picked-or-banned rose under Fearless. "
      f"The 2026 international sample has {B['unique_picked']} unique picks in {B['n_games']} games. Base case for Worlds 2026: "
      f"about {up[2025]} picked, scaled up if the event has more games than 2025's 84.")
    w("")
    w("**Confidence:** medium. The unique-champion count grows with the number of games, so the final figure depends on the "
      "Worlds 2026 game count.")
    w("")

    # --- Q11
    w("## 11. Games under 32:00 vs 32:00 and over")
    w("")
    rows = []
    for y in YEARS:
        d = R[y]["q11"].iloc[0]
        rows.append({"year": y, "games": int(d.games), "< 32:00": int(d.under_32_games),
                     ">= 32:00": int(d.over_or_equal_32_games), "< 32:00 %": fmt(d.under_32_pct, 1),
                     "mean (min)": fmt(d.mean_min, 2), "median (min)": fmt(d.median_min, 2)})
    w(md_table(pd.DataFrame(rows)))
    w("")
    w("Split by format (Bo1 = single-game series; Bo3/Bo5 = games in multi-game series) and by stage:")
    w("")
    for key, label in [("q11_format", "format"), ("q11_stage", "stage")]:
        rows = []
        for y in YEARS:
            d = R[y][key]
            for _, r in d.iterrows():
                if r.group == "All":
                    continue
                rows.append({"year": y, label: r.group, "games": int(r.games), "< 32:00 %": fmt(r.under_32_pct, 1),
                             "mean (min)": fmt(r.mean_min, 2), "median (min)": fmt(r.median_min, 2)})
        w(md_table(pd.DataFrame(rows)))
        w("")
    wl_under = 100.0 * sum(R[y]["q11"].iloc[0].under_32_games for y in YEARS) / sum(R[y]["n_games"] for y in YEARS)
    int_under = B["dur"].iloc[0].under_32_pct
    gap = max(abs(wl_under - 50), abs(int_under - 50))
    tail = ("both within 3 points of 50/50, so there is no reliable lean; call it a coin flip"
            if gap < 3 else "the lean is clear enough to use")
    w(f"**Base-rate answer for 2026:** Worlds 2024+2025 pooled: {fmt(wl_under, 1)}% under 32:00 "
      f"({'under' if wl_under > 50 else 'over'} lean). 2026 international (MSI/FST/EWC) pooled: {fmt(int_under, 1)}% under "
      f"({'under' if int_under > 50 else 'over'} lean). The two disagree on the lean and are {tail}.")
    w("")
    w("**Confidence:** low. The two samples disagree on the lean, and some stage splits have only 5 games (the final).")
    w("")

    # --- Q12
    w("## 12. Any pro with 15+ kills in a game")
    w("")
    rows = []
    for y in YEARS:
        f = R[y]["q12_13"]
        rows.append({"year": y, "games": f["n_games"], "games with a 15+ kill player": f["games_15k"],
                     "rate per game": fmt(100 * f["rate_15k"], 1) + "%", "max single-game kills": f["max_kills"]})
    w(md_table(pd.DataFrame(rows)))
    w("")
    for y in YEARS:
        t = R[y]["q12_13"]["top_kills"]
        w(f"{y} top single-game kill rows: " + "; ".join(
            f"{r.player} ({r.champion}, {r.team}) {int(r.kills)}-{int(r.deaths)}-{int(r.assists)}" for _, r in t.iterrows()))
        w("")
    n_event = round(np.mean([R[y]["n_games"] for y in YEARS]))
    wl_k = sum(R[y]["q12_13"]["games_15k"] for y in YEARS)
    wl_n = sum(R[y]["q12_13"]["n_games"] for y in YEARS)
    in_k, in_n = B["flags"]["games_15k"], B["flags"]["n_games"]
    p_pool = (wl_k + in_k) / (wl_n + in_n)
    pr = lambda p: 100 * (1 - (1 - p) ** n_event)
    w(f"**Base-rate answer for 2026:** Worlds 2024+2025: {wl_k}/{wl_n} games, so the Worlds prior is no. "
      f"2026 international: {in_k}/{in_n} ({fmt(100 * in_k / in_n, 1)}%). Pooled: {fmt(100 * p_pool, 1)}%. "
      f"For a {n_event}-game event (average of 2024 and 2025), P(at least one 15+ kill game) = {fmt(pr(p_pool), 0)}% pooled, "
      f"{fmt(pr(in_k / in_n), 0)}% at the 2026 rate, {fmt(pr(wl_k / wl_n), 0)}% at the Worlds rate.")
    w("")
    w("**Confidence:** low. Two Worlds events have zero hits, and the 2026 rate comes from only "
      f"{in_k} hits in {in_n} games. The pooled figure is the most reasonable base case.")
    w("")

    # --- Q13
    w("## 13. Any pro with 450+ CS in a game")
    w("")
    rows = []
    for y in YEARS:
        f = R[y]["q12_13"]
        rows.append({"year": y, "games": f["n_games"], "games with a 450+ CS player": f["games_450cs"],
                     "rate per game": fmt(100 * f["rate_450cs"], 1) + "%", "max single-game CS": fmt(f["max_cs"], 0)})
    w(md_table(pd.DataFrame(rows)))
    w("")
    for y in YEARS:
        t = R[y]["q12_13"]["top_cs"]
        w(f"{y} top single-game CS rows: " + "; ".join(
            f"{r.player} ({r.champion}, {r.team}) {int(r.cs)} CS" for _, r in t.iterrows()))
        w("")
    n_event = round(np.mean([R[y]["n_games"] for y in YEARS]))
    wl_k = sum(R[y]["q12_13"]["games_450cs"] for y in YEARS)
    wl_n = sum(R[y]["q12_13"]["n_games"] for y in YEARS)
    in_k, in_n = B["flags_cs_games"], B["flags"]["n_games"]
    p_pool = (wl_k + in_k) / (wl_n + in_n)
    pr = lambda p: 100 * (1 - (1 - p) ** n_event)
    w(f"**Base-rate answer for 2026:** Worlds 2024+2025: {wl_k}/{wl_n} games ({fmt(100 * wl_k / wl_n, 1)}%). "
      f"2026 international: {in_k}/{in_n} ({fmt(100 * in_k / in_n, 1)}%). Pooled: {fmt(100 * p_pool, 1)}%. "
      f"For a {n_event}-game event, P(at least one 450+ CS game) = {fmt(pr(p_pool), 0)}% pooled "
      f"({fmt(pr(wl_k / wl_n), 0)}% at the Worlds rate, {fmt(pr(in_k / in_n), 0)}% at the 2026 rate).")
    w("")
    w("**Confidence:** medium. The counts are small, and CS depends on game length, so the 32-minute split matters here.")
    w("")

    # --- Q14
    w("## 14. Role of Finals MVP")
    w("")
    w("Verified history (kept from the earlier section; the 2024 and 2025 roles were also checked against this data):")
    w("")
    rows = [{"year": y, "Finals MVP": p, "team": t, "role": r} for y, p, t, r in FINALS_MVP_VERIFIED]
    w(md_table(pd.DataFrame(rows)))
    w("")
    w("Stat leaders of each final's winning team (all games of that final series):")
    w("")
    for y in YEARS:
        win = R[y]["q14_winner"]
        t = R[y]["q14_table"].copy()
        t["kills_per_game"] = t.kills_per_game.map(lambda v: f"{v:.2f}")
        t["kda"] = t.kda.map(lambda v: f"{v:.2f}")
        t["dmg_per_game"] = t.dmg_per_game.map(lambda v: f"{v:.0f}")
        t["cs_mean"] = t.cs_mean.map(lambda v: f"{v:.0f}")
        w(f"**{y} final, winner {win}**")
        w("")
        w(md_table(t[["player", "role", "games", "kills", "deaths", "assists", "kda", "kills_per_game", "dmg_per_game", "cs_mean"]]))
        w("")
    w("**Base-rate answer for 2026:** over the four listed years, Top 2, Mid 1, Bot 1, Jungle 0, Support 0. "
      "Four samples is too few to lean hard. Use the finalists' star roster from the T2.4 simulation for the Finals MVP role.")
    w("")
    w("**Confidence:** medium on the list (verified); low on the role distribution (four samples).")
    w("")

    # --- Q15
    w("## 15. Number of regions among quarterfinalists")
    w("")
    rows = []
    for y in YEARS:
        ko = R[y]["ko_teams"]
        rows.append({"year": y, "regions": R[y]["ko_regions"],
                     "quarterfinalists (region)": "; ".join(f"{r.team} ({r.region})" for _, r in ko.sort_values("region").iterrows())})
    w(md_table(pd.DataFrame(rows)))
    w("")
    w(f"**Base-rate answer for 2026:** {R[2024]['ko_regions']} (2024), {R[2025]['ko_regions']} (2025). "
      f"Base rate {fmt((R[2024]['ko_regions'] + R[2025]['ko_regions']) / 2, 1)} regions. "
      f"Region = domestic league (Pacific leagues merged into LCP).")
    w("")
    w("**Confidence:** medium. Two events. The count depends on the Pacific merge: CTBC Flying Oyster (LCP) was the only "
      "Pacific quarterfinalist (2025), and no Pacific team reached the 2024 knockouts.")
    w("")

    # --- Q16
    w("## 16. LCS / LTA North team reaches Knockouts")
    w("")
    rows = [{"year": y, "NA teams in Knockouts": ", ".join(R[y]["ko_na"]) if R[y]["ko_na"] else "none",
             "NA teams in Worlds": ", ".join(sorted(R[y]["placements"].loc[R[y]["placements"].region == "NA", "team"])) or "none"}
            for y in YEARS]
    w(md_table(pd.DataFrame(rows)))
    w("")
    hits = sum(bool(R[y]["ko_na"]) for y in YEARS)
    w(f"**Base-rate answer for 2026:** yes in {hits} of 2 years, so about {fmt(100 * hits / 2, 0)}%. "
      f"2025's NA teams both lost before the knockouts, and the 2024 NA team (FlyQuest) reached the QF.")
    w("")
    w("**Confidence:** low. Two years only. NA had 3 Worlds teams in 2024 and 2 in 2025.")
    w("")

    # --- Q17
    w("## 17. T1 vs HLE placement")
    w("")
    rows = []
    for y in YEARS:
        pl = R[y]["placements"].set_index("team").placement.astype(str)
        rows.append({"year": y, "T1": pl.get("T1", "-"), "Hanwha Life Esports (HLE)": pl.get("Hanwha Life Esports", "-")})
    w(md_table(pd.DataFrame(rows)))
    w("")
    w("**Base-rate answer for 2026:** T1 placed higher in 2 of 2 years (2024 champion; 2025 champion). "
      "HLE reached the QF in both years. T1 is the favourite in this comparison.")
    w("")
    w("**Confidence:** medium on history, but this is a tournament-sim question and should follow the T2.4 simulation.")
    w("")

    # --- Q18
    w("## 18. Team that wins the shortest game")
    w("")
    for y in YEARS:
        t = R[y]["q18"].copy()
        t["duration"] = t.duration_sec.map(lambda s: f"{int(s) // 60}:{int(s) % 60:02d}")
        w(f"**{y}** (top 5 shortest)")
        w("")
        w(md_table(t[["winner", "opponent", "duration", "stage", "patch", "game_id"]]))
        w("")
    s24 = R[2024]["q18"].iloc[0]
    s25 = R[2025]["q18"].iloc[0]
    w(f"**Base-rate answer for 2026:** no base-rate winner. The shortest game went to {s24.winner} in 2024 and "
      f"{s25.winner} in 2025, so the two winners differ. Use the T2.4 win probabilities instead.")
    w("")
    w("**Confidence:** none (one game per year; noise question).")
    w("")

    # --- totals / scaling
    w("## Totals and scaling inputs")
    w("")
    rows = []
    for y in YEARS:
        r = R[y]
        rows.append({"year": y, "games": r["n_games"], "series": r["n_series"],
                     **{f"games {STAGE_LABEL[k]}": int(v) for k, v in r["stage_counts"].items()}})
    w(md_table(pd.DataFrame(rows)))
    w("")
    rows = []
    for y in YEARS:
        pl = R[y]["placements"]
        for p in PLACEMENT_ORDER:
            sub = pl[pl.placement.astype(str) == p]
            if len(sub) == 0:
                continue
            rows.append({"year": y, "placement": p, "teams": len(sub),
                         "avg games per team": fmt(sub.games.mean(), 1),
                         "games per team (each)": ", ".join(f"{t} {g}" for t, g in zip(sub.team, sub.games))})
    w(md_table(pd.DataFrame(rows)))
    w("")
    cnt = {y: R[y]["placements"].placement.astype(str).value_counts().to_dict() for y in YEARS}
    w("**Scaling note:** " + "; ".join(
        f"{y}: {R[y]['n_games']} games, {len(R[y]['placements'])} teams "
        f"({cnt[y].get('Play-In exit', 0)} block-1 exits, {cnt[y].get('Swiss exit', 0)} later pre-KO exits, "
        f"{int(R[y]['ko_teams'].shape[0])} knockout teams)" for y in YEARS)
        + ". Use the games-per-team-by-placement table for the 2026 game-count model.")
    w("")

    # --- Bonus 2026
    w("## Bonus: 2026 international baseline (MSI, FST, EWC)")
    w("")
    w(f"Games: {B['n_games']} (MSI 16.13, FST 16.05, EWC 16.13). Combined below, then per event.")
    w("")
    w(md_table(B["by_event_table"].assign(under_32_pct=lambda d: d.under_32_pct.map(lambda v: fmt(v, 1)))))
    w("")
    w("**Champion presence (combined, top 10):**")
    w("")
    p = add_disp(B["presence"], lambda r: f"{r.champ} {r.presence_pct:.1f}% (P {r.picks}, B {r.bans})")
    w(md_table(p[["rank", "disp"]].rename(columns={"disp": "champion (presence, picks, bans)"})))
    w("")
    fl = B["flags"]
    w(f"- Unique champions picked (combined): {B['unique_picked']}; picked or banned: {B['unique_picked_or_banned']}.")
    w(f"- Games with 15+ kills: {fl['games_15k']} / {fl['n_games']} ({fmt(100 * fl['rate_15k'], 1)}%); max kills {fl['max_kills']}.")
    w(f"- Games with 450+ CS: {fl['games_450cs']} / {fl['n_games']} ({fmt(100 * fl['rate_450cs'], 1)}%); max CS {fmt(fl['max_cs'], 0)}.")
    w(f"- Under 32:00: {fmt(B['dur'].iloc[0].under_32_pct, 1)}%; mean {fmt(B['dur'].iloc[0].mean_min, 1)} min, "
      f"median {fmt(B['dur'].iloc[0].median_min, 1)} min.")
    w("")
    w(f"- Teemo: {B['teemo_picks']} picks, {B['teemo_bans']} bans.")
    w("")
    w("**Use:** a 167-game current-meta sample on patches 16.05 (FST) and 16.13 (MSI, EWC). Use it to check the rates for "
      "Q1, Q10, Q11, Q12 and Q13 against the Worlds 2024/25 base.")
    w("")

    w("## Bonus: patch 16.17-16.20 champion presence (domestic playoffs + WLDQ)")
    w("")
    if B["patch_meta_n"] == 0:
        w("_(no games)_")
    else:
        pc = B["patch_meta_counts"]
        w(f"Games in scope: {B['patch_meta_n']}. Patches present in the data: "
          + ", ".join(sorted(pc.patch.unique())) + ". "
          + "Patches 16.18-16.20 have no games in the DB yet, so this table is effectively patch 16.17 only.")
        w("")
        w(md_table(pc.rename(columns={"league": "league", "patch": "patch", "games": "games"})))
        w("")
        pp = add_disp(B["patch_presence"], lambda r: f"{r.champ} {r.presence_pct:.1f}% (P {r.picks}, B {r.bans})")
        w(md_table(pp[["rank", "disp"]].rename(columns={"disp": "champion (presence, picks, bans)"})))
        w("")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        games, pg, teams = load(con)
        intl, intl_pg, meta = load_bonus(con)
    finally:
        con.close()
    R = {y: compute_year(games, pg, teams, y) for y in YEARS}
    B = bonus_2026(intl, intl_pg, meta)
    write_outputs(R, B)
    for y in YEARS:
        r = R[y]
        print(f"{y}: games={r['n_games']} series={r['n_series']} swiss_start={r['swiss_start'].date()} "
              f"stages={dict(r['stage_counts'])} KO={r['ko_teams'].team.tolist()}")
    print(f"wrote {OUT_MD} and {OUT_DIR}")


if __name__ == "__main__":
    main()
