"""Patch and meta analysis for Worlds 2026 (T3.1).

Regenerates the data parts of outputs/patch_report.md and outputs/meta/*.csv.

Inputs:
  data/pickems.duckdb        read-only (games, player_games)
  data/champion_changes.csv  hand-curated from Riot's official patch notes
                             (cached text in data/raw/patches/riot_patch_26-*.txt)
Run:
  python -m crystal.meta

Patch labels: Oracle's Elixir label -> Riot patch
  16.17 -> 26.17 (live 2026-08-25)   16.18 -> 26.18 (2026-09-09)
  16.19 -> 26.19 (2026-09-22/23)     16.20 -> 26.20 (2026-10-06/07, the Worlds patch)
  16.19 is not present as a label in the DB; the DB's 16.18 label runs to 2026-10-08.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from functools import partial

import duckdb
import numpy as np
import pandas as pd

from common.paths import DB_PATH as DB, ROOT
from common.report import fmt_num, md_table

fmt = partial(fmt_num, missing="n/a")

sys.stdout.reconfigure(encoding="utf-8")

CHANGES = ROOT / "data" / "champion_changes.csv"
ROSTERS = ROOT / "data" / "rosters_2026.csv"
META_DIR = ROOT / "outputs" / "meta"
REPORT = ROOT / "outputs" / "patch_report.md"

TOP = ["LCK", "LPL", "LEC", "LCS", "LCP", "CBLOL", "WLDQ"]
RECENT_FROM = "2026-08-14"
EARLY_PATCHES = ["16.18", "16.20"]
PLAYIN_TEAMS = ["C9", "KC", "FUR", "MVK"]
MIN_RAW_PICKS = 5
TOP_N = 5
TOP30 = 30
WEIGHT = {"16.17": 0.5, "16.18": 1.0, "16.19": 1.0, "16.20": 1.0}  # recency weight of patch changes
MAG_PP = {1: 2.0, 2: 4.0, 3: 7.0}  # presence-point effect per change magnitude
ADJ_CAP = 12.0
EARLY_K = 600.0  # shrinkage constant for the early (16.18/16.20, any league) read
FIT_SCALE = 1.5  # pp per z-score for team meta fit
FIT_CAP = 3.0
SIGN = {"buff": 1, "nerf": -1, "adjust": 0}

# Narrative sections: written by hand after reviewing the results. The script keeps them verbatim.
NARRATIVE = {
    "worlds_patch": (
        "**Worlds patch: Patch 26.20 (Oracle label 16.20, live 2026-10-06/07).** Riot's 26.20 notes open with "
        "\"the Worlds patch is here\" and say \"For Summoner's Rift, this is the patch we'll be seeing our "
        "year-defining competitive play on\". Riot's 26.19 notes call 26.20 \"the Worlds patch (which is the "
        "patch after this one)\". Patch 26.21 is scheduled for 2026-10-21, after Worlds starts (third-party "
        "schedules; not yet live).\n"
        "Sources: official Riot notes, fetched 2026-10-11 and cached: "
        "https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-17-notes , "
        "...-26-18-notes , ...-26-19-notes , ...-26-20-notes (cached as data/raw/patches/riot_patch_26-*.txt). "
        "Schedule check: esports.net / esports.gg 2026 patch schedules (WebSearch, not cached)."
    ),
    "key_changes": (
        "- **Cassiopeia was nerfed, not left alone:** 26.18 rebalanced her (laning damage and move speed down, "
        "scaling AP ratios up), then 26.20 cut base HP 630 to 610 and base mana 480 to 450 to reduce pro "
        "early resources.\n"
        "- **Nocturne** nerfed in 26.17 (armor, HP) and 26.19 (R cooldown +20s at each rank). **Vi** nerfed in "
        "26.19 (base AD, passive shield). **Ryze** and **Rumble** nerfed in 26.19. **Ambessa, Ashe, K'Sante, "
        "Yunara** nerfed in 26.20. **Syndra, Nautilus, Zeri, Bard, Seraphine** nerfed in 26.18. Hextech "
        "Rocketbelt reworked in 26.20 (haste 20 to 10, active 135 + 15% AP), Experimental Hexplate nerfed "
        "(ranged mod 70% to 50%), Runaan's Hurricane nerfed.\n"
        "- **Buffs aimed at pro-level picks:** Kha'Zix and Lillia (26.19), Kindred, Diana, Smolder, Swain, "
        "Mordekaiser, Tahm Kench (26.20). Lucian had a 26.19 adjustment (passive down, Q up) and a 26.20 AD "
        "growth buff.\n"
        "- **System:** top role quest Teleport cooldown reduced (26.19). No objective, tower or gold changes "
        "in 26.17 to 26.20, so no tempo change from patches.\n"
        "- **Not in the official SR notes for 26.17 to 26.20:** Olaf, Jarvan IV, Jayce, Ezreal, Teemo, Lee Sin, "
        "Akali, Galio (Akali and Galio changes are Classic-only or Mayhem-only). Orianna: a third-party report "
        "of a 26.19 change, which Riot's official notes do not include. Sylas and Varus: a third-party report "
        "of changes pulled from 26.20, which the official notes do not mention.\n"
        "- Classic, ARAM: Mayhem and Arena changes are excluded from the CSV (not SR).\n"
    ),
    "meta_notes": (
        "- Top of the list: Cassiopeia (meta score 75), Nocturne (73), Vi (66), Lucian (56), Jarvan IV (55). "
        "Cassiopeia has the highest raw presence (90%) but 83% of it is bans. Her early read (16.18/16.20, any "
        "league) is 64%, which pulls her meta score down about 13 points, so she is still first but not as "
        "safe as the recent window suggests.\n"
        "- Early-read adjustments (16.18/16.20, any league): up for Qiyana (+15pp), Lulu (+9), Yunara (+5), "
        "Caitlyn (+4); down for Pantheon (-8), Olaf (-5), Orianna (-5). The early read comes from minor "
        "leagues and 16.18 covers 26.18 plus part of 26.19, so treat it as a rough signal.\n"
        "- Recent-window sample is small (522 top-level games), so presence has roughly +/-5pp of noise "
        "per champion. Heuristic weights: buff/nerf of 1/2/3 magnitudes = +/-2/4/7pp, patch recency weights "
        "0.5 (26.17) and 1.0 (26.18 to 26.20), cap +/-12pp. These are not fitted to outcomes."
    ),
    "crystal_notes": (
        "**Q1 (highest presence):** Cassiopeia (est. ~75%), Nocturne (~73%), Vi (~66%), Lucian (~56%), "
        "Jarvan IV (~55%). Presence counts bans, so Cassiopeia's ban rate drives her lead.\n\n"
        "**Q2 (highest win rate, Champion*):** Worlds-scale minimum is 5 picks in a ~95-game Worlds, i.e. a "
        "5.3% pick rate. With that filter: Leona 64.5% (31 games), Xayah 61.5% (52), Ashe 59.8% (92), Qiyana "
        "59.3% (54), Camille 59.2% (71). Without the Worlds-scale filter (raw 5 picks), Lux (72.7%, 11 "
        "games) leads, which shows low-pick champions dominating the WR leaderboard.\n\n"
        "**Q3 (highest average deaths per game, Champion*):** Worlds-scale filter: Rell 4.0 (45 games, 36% "
        "WR), Olaf 3.6 (99 games), Vi 3.5 (92), Camille 3.5 (71), Jax 3.5 (32). Raw 5-pick filter adds "
        "Lissandra (3.5, 17 games, 29% WR).\n\n"
        "**Q9 (Teemo picked at least once):** 2 Teemo picks in 2026 across all 9,634 games in the DB (LCKC "
        "2026-05-22 and PRM 2026-05-27), 0 in recent top-level play, and no buffs or nerfs since 16.17. Base "
        "rate about 2 picks per 9,634 games; at roughly 950 Worlds picks this is about 2% chance of at least "
        "one. Answer: No (about 2%).\n\n"
        "**Q10 (unique champions):** recent top-level window has 130 distinct champions in 522 games, "
        "**24.9 per 100 games**. Worlds 2024 and 2025 each had 95 distinct picks (the 95 claim checks out), "
        "giving about 90 and 113 per 100 games. Estimate for Worlds 2026: about 95, range 85 to 115.\n\n"
        "**Q11 (games under vs over 32:00):** recent top-level window 53% under 32:00 (n=522, mean 32.3 "
        "min); 16.18 (any league) 70%; 16.20 76% (n=78, small). Worlds 2024 48%, 2025 49%. The patches "
        "change no objective, tower or gold values, so pace is not changed by them. Answer: near a coin flip "
        "with a slight lean to under 32:00 (about 52 to 55%)."
    ),
    "team_notes": (
        "Adjustments are small (all within about +/-2pp) because the team-level spread is narrow.\n\n"
        "- **KC (+0.4pp):** meta fit 48.7% (middle), pool depth 10.8 (above average; Bot Ezreal/Ashe, "
        "Mid kyeahoo 13 champions). Neutral to slightly positive.\n"
        "- **C9 (-0.2pp):** meta fit 50.4% (high), pool depth 7.4 (below average). Mid Loki (50 games, "
        "partial 2026 tenure, depth 4) and Bot Tactical (51 games) are the thin spots. Neutral.\n"
        "- **FUR (-0.8pp):** meta fit 44.4% (low), pool depth 10.4 (good; Top Ambessa and K'Sante, Mid Ryze "
        "are their main picks). Slightly negative on meta fit.\n"
        "- **MVK (-1.8pp):** lowest meta fit (44.4%) and thin pool (7.2; Top Kratos depth 7, Mid Chika depth "
        "6 over 60 games). Most negative in this group, and the only Play-In team with both weak fit and "
        "weak depth.\n"
        "- Caveat: player-level 2026 samples mix teams (e.g. Loki, Tactical, Harky have partial 2026 "
        "tenure), so pool depth for them includes games from other rosters."
    ),
    "gaps": (
        "- Riot 26.16 notes (16.16) were not fetched, so SR changes before 26.17 are not encoded. "
        "16.16 games were played before 26.17, so only the 26.17+ changes apply to them.\n"
        "- The DB patch labels are noisy: 16.17 and 16.18 run past their Riot release dates (16.18 covers "
        "late 26.18 and most of 26.19), and 16.19 is missing.\n"
        "- Worlds 2025 has 84 games in the DB, which may be incomplete; this affects the Worlds game "
        "count W and the Q10/Q11 Worlds references.\n"
        "- Meta score weights are heuristics, not fitted. The early read is any-league (minor leagues "
        "included).\n"
        "- Teemo and the Q9 base rate use all-league 2026 games; the pick-count denominator is approximate.\n"
        "- Third-party-only claims (Orianna, Sylas/Varus) are not encoded."
    ),
}


def connect():
    for attempt in range(4):
        try:
            return duckdb.connect(str(DB), read_only=True)
        except duckdb.Error as exc:
            if "lock" in str(exc).lower() and attempt < 3:
                print(f"DB locked (attempt {attempt + 1}); waiting 60s before retry")
                time.sleep(60)
                continue
            raise
    raise RuntimeError("unreachable")


def load(con):
    games = con.sql(
        """select game_id, league, date_utc, patch, blue_picks, red_picks, blue_bans, red_bans,
                  duration_sec from games"""
    ).df()
    pg = con.sql(
        """select game_id, league, date_utc, patch, player, player_id, team, role, champion, win,
                  kills, deaths, assists, team_kills, damage from player_games"""
    ).df()
    return games, pg


def split_list(s):
    if not isinstance(s, str) or not s.strip():
        return []
    return [c.strip() for c in s.split(",") if c.strip()]


def game_champ_sets(games: pd.DataFrame):
    picked, banned = [], []
    for r in games.itertuples(index=False):
        for c in set(split_list(r.blue_picks)) | set(split_list(r.red_picks)):
            picked.append((r.game_id, c))
        for c in set(split_list(r.blue_bans)) | set(split_list(r.red_bans)):
            banned.append((r.game_id, c))
    return (pd.DataFrame(picked, columns=["game_id", "champion"]),
            pd.DataFrame(banned, columns=["game_id", "champion"]))


def champ_table(games_sub: pd.DataFrame, pg_sub: pd.DataFrame) -> pd.DataFrame:
    """Per-champion presence, pick, ban, win rate, deaths and roles for a set of games."""
    G = games_sub.game_id.nunique()
    pk, bn = game_champ_sets(games_sub)
    present = pd.concat([pk, bn]).drop_duplicates()
    t = pd.DataFrame({
        "picked_games": pk.groupby("champion").size(),
        "banned_games": bn.groupby("champion").size(),
        "present_games": present.groupby("champion").size(),
    }).fillna(0)
    p = pg_sub.groupby("champion").agg(
        pg_games=("win", "size"),
        wins=("win", "sum"),
        deaths_pg=("deaths", "mean"),
        kills_pg=("kills", "mean"),
        assists_pg=("assists", "mean"),
    )
    t = t.join(p, how="outer").fillna(0)
    t["G"] = G
    t["pick_pct"] = 100 * t.picked_games / max(G, 1)
    t["ban_pct"] = 100 * t.banned_games / max(G, 1)
    t["presence_pct"] = 100 * t.present_games / max(G, 1)
    t["wr"] = np.where(t.pg_games > 0, 100 * t.wins / t.pg_games.where(t.pg_games > 0, 1), np.nan)
    roles = (pg_sub.groupby(["champion", "role"]).size().rename("n").reset_index()
             .sort_values(["champion", "n"], ascending=[True, False]))
    role_str = {}
    for champ, d in roles.groupby("champion"):
        role_str[champ] = "/".join(str(x) for x in d.role.head(2))
    t["roles"] = pd.Series(role_str)
    t["roles"] = t["roles"].fillna("")
    t.index.name = "champion"
    return t.reset_index()


def patch_changes():
    ch = pd.read_csv(CHANGES, dtype=str)
    ch["magnitude"] = ch.magnitude.astype(int)
    ch["pro_relevant"] = ch.pro_relevant.str.lower().eq("true")
    ch["w"] = ch.patch.map(WEIGHT).fillna(0.0)
    ch["sign"] = ch.direction.map(SIGN).fillna(0)
    ch["pp"] = ch.magnitude.map(MAG_PP) * ch.sign * ch.w
    return ch


def main():
    META_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    games, pg = load(con)
    snapshot = con.sql("select max(date_utc) from games").fetchone()[0]
    worlds_counts = con.sql(
        """select year(date_utc) y, count(distinct game_id) n from games
           where league='WLDs' and year(date_utc) in (2024, 2025) group by 1 order by 1"""
    ).df()
    unique_worlds = {}
    for y in (2024, 2025):
        gy = games[(games.league == "WLDs") & (pd.to_datetime(games.date_utc).dt.year == y)]
        pk, _ = game_champ_sets(gy)
        unique_worlds[y] = pk.champion.nunique()
    con.close()

    W = int(round(worlds_counts.n.mean()))  # expected Worlds game count from the last two Worlds
    thr_rate = 100.0 * MIN_RAW_PICKS / W  # 5 picks at Worlds scale, in pick-rate percent

    games["date_utc"] = pd.to_datetime(games.date_utc)
    pg["date_utc"] = pd.to_datetime(pg.date_utc)

    recent_games = games[games.league.isin(TOP) & (games.date_utc >= RECENT_FROM)]
    recent_pg = pg[pg.game_id.isin(recent_games.game_id)]
    early_games = games[games.patch.isin(EARLY_PATCHES)]
    early_pg = pg[pg.game_id.isin(early_games.game_id)]
    p2026_games = games[games.league.isin(TOP) & (games.date_utc >= "2026-01-01")]
    p2026_pg = pg[pg.game_id.isin(p2026_games.game_id)]

    rec = champ_table(recent_games, recent_pg).set_index("champion")
    early = champ_table(early_games, early_pg).set_index("champion")
    ytd = champ_table(p2026_games, p2026_pg).set_index("champion")
    G_r, G_e = len(recent_games), len(early_games)

    ch = patch_changes()
    adj = ch[ch.kind == "champion"].groupby("name").pp.sum().clip(-ADJ_CAP, ADJ_CAP)
    db_champs = set(pg.champion.dropna().unique())
    unmatched = sorted(set(ch[ch.kind == "champion"].name) - db_champs)

    idx = sorted(set(rec.index) | set(early.index))
    m = pd.DataFrame(index=pd.Index(idx, name="champion"))
    for col in ["presence_pct", "pick_pct", "ban_pct", "picked_games", "wr", "pg_games",
                "deaths_pg", "kills_pg", "assists_pg", "roles"]:
        m[col] = rec[col].reindex(idx) if col in rec.columns else np.nan
    m["picked_games"] = m.picked_games.fillna(0).astype(int)
    m["presence_pct"] = m.presence_pct.fillna(0.0)
    m["pick_pct"] = m.pick_pct.fillna(0.0)
    m["ban_pct"] = m.ban_pct.fillna(0.0)
    m["pg_games"] = m.pg_games.fillna(0).astype(int)
    m["roles"] = m.roles.fillna("")
    m["patch_adj_pp"] = m.index.map(adj).fillna(0.0)
    m["early_pres_pct"] = early.presence_pct.reindex(idx).fillna(0.0)
    m["early_picks"] = early.picked_games.reindex(idx).fillna(0).astype(int)
    w_e = G_e / (G_e + EARLY_K)
    m["early_adj_pp"] = w_e * (m.early_pres_pct - m.presence_pct)
    m["meta_score"] = (m.presence_pct + m.patch_adj_pp + m.early_adj_pp).clip(0, 100)
    m["ytd2026_pres_pct"] = ytd.presence_pct.reindex(idx).fillna(0.0)

    changes_by = ch[ch.kind == "champion"].groupby("name")

    def changes_text(name):
        if name not in changes_by.groups:
            return ""
        d = changes_by.get_group(name)
        return "; ".join(f"{r.patch} {r.direction} ({r.summary})" for r in d.itertuples())

    m["changes"] = [changes_text(n) for n in m.index]
    m = m.sort_values("meta_score", ascending=False)
    m["rank"] = np.arange(1, len(m) + 1)

    def rationale(r):
        bits = [f"{r.presence_pct:.0f}% present ({r.pick_pct:.0f}% pick, {r.ban_pct:.0f}% ban) "
                f"in {G_r} recent top-level games"]
        if r.pg_games:
            bits.append(f"WR {r.wr:.0f}% over {int(r.pg_games)} games")
        if abs(r.patch_adj_pp) >= 0.5:
            bits.append(f"patch adj {r.patch_adj_pp:+.1f}pp")
        if r.early_picks and abs(r.early_adj_pp) >= 0.5:
            bits.append(f"16.18/16.20 any-league read {r.early_pres_pct:.0f}% "
                        f"(n={G_e} games, adj {r.early_adj_pp:+.1f}pp)")
        if r.changes:
            bits.append(r.changes.split("; ")[-1][:160])
        return "; ".join(bits)

    m["rationale"] = [rationale(r) for r in m.itertuples()]
    top30 = m.head(TOP30).copy()
    top30.reset_index().to_csv(META_DIR / "meta_all.csv", index=False)
    top30.reset_index()[["rank", "champion", "meta_score", "presence_pct", "pick_pct", "ban_pct",
                         "wr", "pg_games", "deaths_pg", "roles", "patch_adj_pp", "early_pres_pct",
                         "early_adj_pp", "rationale"]].to_csv(META_DIR / "meta_top30.csv", index=False)

    rec.reset_index().to_csv(META_DIR / "recent_champions.csv", index=False)
    early.reset_index().to_csv(META_DIR / "early_champions.csv", index=False)

    # Crystal Ball candidates
    q1 = m.head(TOP_N).reset_index()[["champion", "meta_score", "presence_pct", "pick_pct", "ban_pct"]]
    cand = rec[(rec.picked_games > 0) & (rec.pg_games > 0)].reset_index().copy()
    cand["picked_games"] = cand.picked_games.astype(int)
    cand["pg_games"] = cand.pg_games.astype(int)
    cand["pick_ok_worlds"] = cand.pick_pct >= thr_rate
    cand["pick_ok_raw"] = cand.picked_games >= MIN_RAW_PICKS
    q2_w = cand[cand.pick_ok_worlds].sort_values("wr", ascending=False).head(TOP_N)
    q2_r = cand[cand.pick_ok_raw].sort_values("wr", ascending=False).head(TOP_N)
    q3_w = cand[cand.pick_ok_worlds].sort_values("deaths_pg", ascending=False).head(TOP_N)
    q3_r = cand[cand.pick_ok_raw].sort_values("deaths_pg", ascending=False).head(TOP_N)
    n_worlds_ok = int(cand.pick_ok_worlds.sum())
    n_raw_ok = int(cand.pick_ok_raw.sum())
    cols = ["champion", "picked_games", "pick_pct", "wr", "pg_games", "deaths_pg", "roles"]
    q2_w[cols].to_csv(META_DIR / "q2_worlds_filter.csv", index=False)
    q3_w[cols].to_csv(META_DIR / "q3_worlds_filter.csv", index=False)

    # Q9 Teemo
    tee_games = games[games.date_utc >= "2026-01-01"]
    tee_pk, tee_bn = game_champ_sets(tee_games)
    tee_rows = tee_pk[tee_pk.champion == "Teemo"]
    tee_ban = tee_bn[tee_bn.champion == "Teemo"]
    tee_pg = pg[(pg.champion == "Teemo") & (pg.date_utc >= "2026-01-01")]
    tee_top = tee_rows[tee_rows.game_id.isin(recent_games.game_id)]
    q9 = {
        "pro_picks_2026_all": int(len(tee_rows)),
        "pro_bans_2026_all": int(len(tee_ban)),
        "pg_rows_2026": int(len(tee_pg)),
        "pick_in_recent_top": int(len(tee_top)),
        "last_pick": str(tee_pg.date_utc.max()) if len(tee_pg) else "none",
        "changes": changes_text("Teemo") or "none in 16.17-16.20 SR notes",
    }

    # Q10 unique champions
    rec_pk, _ = game_champ_sets(recent_games)
    n_unique = rec_pk.champion.nunique()
    per100 = n_unique / (G_r / 100.0) if G_r else np.nan
    ytd_pk, _ = game_champ_sets(p2026_games)
    n_unique_ytd = ytd_pk.champion.nunique()
    per100_ytd = n_unique_ytd / (len(p2026_games) / 100.0)

    # Q11 game length
    def short_share(g):
        if len(g) == 0:
            return np.nan, np.nan, 0
        return 100 * (g.duration_sec < 32 * 60).mean(), g.duration_sec.mean() / 60, len(g)

    s_rec = short_share(recent_games)
    s_e1618 = short_share(games[games.patch == "16.18"])
    s_e1620 = short_share(games[games.patch == "16.20"])
    s_e1617 = short_share(games[games.patch == "16.17"])
    s_w = {y: short_share(games[(games.league == "WLDs") & (games.date_utc.dt.year == y)])
           for y in (2024, 2025)}
    dur_by_patch = (games[games.patch.isin(["16.16", "16.17", "16.18", "16.20"])]
                    .groupby("patch").apply(lambda d: pd.Series({
                        "games": len(d),
                        "pct_under_32": 100 * (d.duration_sec < 32 * 60).mean(),
                        "mean_min": d.duration_sec.mean() / 60})))
    dur_by_patch["games"] = dur_by_patch.games.astype(int)
    dur_by_patch.reset_index().to_csv(META_DIR / "duration_by_patch.csv", index=False)

    # Team meta fit and pool depth
    rost = pd.read_csv(ROSTERS)
    starters = rost[rost.is_starter.astype(str).str.lower().eq("true")]
    top30_set = set(top30.index)
    nerf_set = set(ch[(ch.kind == "champion") & (ch.direction == "nerf")].name)
    buff_set = set(ch[(ch.kind == "champion") & (ch.direction == "buff")].name)
    team_rows, player_rows = [], []
    for team, grp in starters.groupby("team_id"):
        tot_g = 0
        top30_g = 0
        nerf_g = 0
        buff_g = 0
        depths = []
        for r in grp.itertuples(index=False):
            d = pg[(pg.player_id == r.player_id) & (pg.date_utc >= "2026-01-01")]
            if d.empty:
                d = pg[(pg.player == r.player) & (pg.date_utc >= "2026-01-01")]
            n = len(d)
            tot_g += n
            if n:
                top30_g += int(d.champion.isin(top30_set).sum())
                nerf_g += int(d.champion.isin(nerf_set).sum())
                buff_g += int(d.champion.isin(buff_set).sum())
            pool = d.groupby("champion").agg(g=("win", "size"), wr=("win", "mean"))
            depth = int(((pool.g >= 3) & (pool.wr >= 0.5)).sum())
            depths.append(depth)
            top3 = d.groupby("champion").size().sort_values(ascending=False).head(3)
            top3_str = ", ".join(f"{c} {k}" for c, k in top3.items())
            player_rows.append({
                "team": team, "role": r.role, "player": r.player, "games_2026": n,
                "top3": top3_str, "pool_depth": depth,
                "low_sample": n < 20,
                "top30_share_pct": 100 * (d.champion.isin(top30_set).mean() if n else np.nan),
            })
        team_rows.append({
            "team": team, "starters_games_2026": tot_g,
            "meta_top30_share_pct": 100 * top30_g / tot_g if tot_g else np.nan,
            "nerf_share_pct": 100 * nerf_g / tot_g if tot_g else np.nan,
            "buff_share_pct": 100 * buff_g / tot_g if tot_g else np.nan,
            "mean_pool_depth": float(np.mean(depths)) if depths else np.nan,
        })
    teams = pd.DataFrame(team_rows)
    players = pd.DataFrame(player_rows)
    z_fit = (teams.meta_top30_share_pct - teams.meta_top30_share_pct.mean()) / teams.meta_top30_share_pct.std()
    z_dep = (teams.mean_pool_depth - teams.mean_pool_depth.mean()) / teams.mean_pool_depth.std()
    teams["z_fit"] = z_fit
    teams["z_depth"] = z_dep
    teams["adj_pp"] = (FIT_SCALE * (z_fit + z_dep) / 2).clip(-FIT_CAP, FIT_CAP)
    teams = teams.sort_values("adj_pp", ascending=False)
    teams.to_csv(META_DIR / "team_fit.csv", index=False)
    players.to_csv(META_DIR / "playin_starters.csv", index=False)

    # Patch-changes reference, as used
    ch.to_csv(META_DIR / "changes_used.csv", index=False)

    write_report(
        snapshot=snapshot, G_r=G_r, G_e=G_e, W=W, thr_rate=thr_rate, q1=q1, q2_w=q2_w, q2_r=q2_r,
        q3_w=q3_w, q3_r=q3_r, n_worlds_ok=n_worlds_ok, n_raw_ok=n_raw_ok, q9=q9,
        n_unique=n_unique, per100=per100, n_unique_ytd=n_unique_ytd, per100_ytd=per100_ytd,
        unique_worlds=unique_worlds, s_rec=s_rec, s_e1618=s_e1618, s_e1620=s_e1620,
        s_e1617=s_e1617, s_w=s_w, dur_by_patch=dur_by_patch, top30=top30, m=m, ch=ch,
        teams=teams, players=players, unmatched=unmatched, w_e=w_e,
        worlds_counts=worlds_counts, n_games_ytd=len(p2026_games),
    )
    print(f"recent top-level games: {G_r}; early (16.18/16.20, any league) games: {G_e}")
    print(f"Worlds-scale pick threshold: {thr_rate:.2f}% (W={W}); cands passing: {n_worlds_ok} worlds, {n_raw_ok} raw")
    print(f"unmatched changes names: {unmatched}")
    print(f"report written: {REPORT}")


def write_report(*, snapshot, G_r, G_e, W, thr_rate, q1, q2_w, q2_r, q3_w, q3_r, n_worlds_ok,
                 n_raw_ok, q9, n_unique, per100, n_unique_ytd, per100_ytd, unique_worlds,
                 s_rec, s_e1618, s_e1620, s_e1617, s_w, dur_by_patch, top30, m, ch, teams,
                 players, unmatched, w_e, worlds_counts, n_games_ytd):
    out = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out.append("# Worlds 2026 patch and meta report\n")
    out.append(f"Generated by `crystal/meta.py` at {now}. DB snapshot: latest game {snapshot}. "
               "Part A patch data is hand-curated in `data/champion_changes.csv`; Part B numbers "
               "are computed from the read-only DB.\n")

    out.append("## 1. Worlds patch and sources\n")
    out.append(NARRATIVE["worlds_patch"] or "_(narrative pending)_")
    out.append("")
    out.append("Patch label mapping (Oracle's Elixir label -> Riot):\n")
    out.append(md_table(pd.DataFrame([
        ["16.16", "26.16", "not checked (not in cache)"],
        ["16.17", "26.17", "2026-08-25"],
        ["16.18", "26.18", "2026-09-09"],
        ["16.19", "26.19", "2026-09-22/23 (no 16.19 label in DB)"],
        ["16.20", "26.20", "2026-10-06/07 (Worlds patch)"],
        ["16.21 / 26.21", "-", "scheduled 2026-10-21 (not live at Worlds start)"],
    ], columns=["Oracle label", "Riot patch", "Live date"])))
    out.append("")
    out.append("Sources: official Riot notes (cached as `data/raw/patches/riot_patch_26-17.txt` "
               "to `riot_patch_26-20.txt`); patch schedule and third-party previews (not "
               "cached, used only for cross-checks).\n")

    out.append("## 2. Key changes (Summoner's Rift, pro-relevant)\n")
    pr = ch[(ch.kind != "system") & ch.pro_relevant][["patch", "kind", "name", "direction",
                                                       "magnitude", "summary"]]
    out.append(md_table(pr))
    out.append("")
    out.append("### Named champions (status per official SR notes, 16.17-16.20)\n")
    rows = []
    for name in ["Cassiopeia", "Nocturne", "Vi", "Orianna", "Olaf", "Jarvan IV", "Lucian", "Ezreal",
                 "Akali", "Lee Sin", "Syndra", "Nautilus", "Jayce", "Ryze", "Rumble", "Galio", "Teemo"]:
        d = ch[ch.name == name]
        if d.empty:
            rows.append([name, "no SR change in 16.17-16.20 notes"])
        else:
            rows.append([name, "; ".join(f"{r.patch} {r.direction} ({r.summary})"
                                         for r in d.itertuples())])
    out.append(md_table(pd.DataFrame(rows, columns=["champion", "changes"])))
    out.append("")
    out.append(NARRATIVE["key_changes"] or "_(narrative pending)_")
    out.append("")

    out.append("## 3. Meta top 30 (Worlds meta score)\n")
    out.append("meta_score = recent top-level presence + patch adjustment (buff/nerf x magnitude, "
               "pp, weighted by patch recency) + early read (16.18/16.20 any league, shrunk). "
               f"Recent window: {G_r} games in LCK, LPL, LEC, LCS, LCP, CBLOL, WLDQ since {RECENT_FROM}. "
               f"Early read: {G_e} games in 16.18/16.20 (any league), weight {w_e:.2f}.\n")
    t30 = top30.reset_index()[["rank", "champion", "meta_score", "presence_pct", "pick_pct",
                               "ban_pct", "wr", "pg_games", "roles", "rationale"]].copy()
    t30["meta_score"] = t30.meta_score.map(lambda x: fmt(x))
    t30["presence_pct"] = t30.presence_pct.map(lambda x: fmt(x))
    t30["pick_pct"] = t30.pick_pct.map(lambda x: fmt(x))
    t30["ban_pct"] = t30.ban_pct.map(lambda x: fmt(x))
    t30["wr"] = t30.wr.map(lambda x: fmt(x))
    out.append(md_table(t30))
    out.append("")
    out.append(NARRATIVE["meta_notes"] or "_(narrative pending)_")
    out.append("")

    out.append("## 4. Crystal Ball candidates\n")
    out.append(f"Worlds-scale minimum: 5 picks in a ~{W}-game Worlds (2024: "
               f"{int(worlds_counts[worlds_counts.y == 2024].n.iloc[0])} games, 2025: "
               f"{int(worlds_counts[worlds_counts.y == 2025].n.iloc[0])} games) = pick rate "
               f"{thr_rate:.1f}%. In the recent window {n_worlds_ok} champions pass that filter; "
               f"the raw 5-picks filter lets {n_raw_ok} through.\n")
    out.append("### Q1 - highest presence (estimated Worlds presence %)\n")
    out.append(md_table(q1.assign(meta_score=q1.meta_score.map(fmt),
                                  presence_pct=q1.presence_pct.map(fmt),
                                  pick_pct=q1.pick_pct.map(fmt),
                                  ban_pct=q1.ban_pct.map(fmt))))
    out.append("")
    out.append("### Q2 - highest win rate (Champion*)\n")
    out.append("Worlds-scale filter:\n")
    out.append(md_table(q2_w.assign(pick_pct=q2_w.pick_pct.map(fmt), wr=q2_w.wr.map(fmt),
                                    deaths_pg=q2_w.deaths_pg.map(fmt))[cols_q()]))
    out.append("")
    out.append("Raw 5-picks filter (for comparison; low-pick champions dominate):\n")
    out.append(md_table(q2_r.assign(pick_pct=q2_r.pick_pct.map(fmt), wr=q2_r.wr.map(fmt),
                                    deaths_pg=q2_r.deaths_pg.map(fmt))[cols_q()]))
    out.append("")
    out.append("### Q3 - highest average deaths per game (Champion*)\n")
    out.append("Worlds-scale filter:\n")
    out.append(md_table(q3_w.assign(pick_pct=q3_w.pick_pct.map(fmt), wr=q3_w.wr.map(fmt),
                                    deaths_pg=q3_w.deaths_pg.map(fmt))[cols_q()]))
    out.append("")
    out.append("Raw 5-picks filter:\n")
    out.append(md_table(q3_r.assign(pick_pct=q3_r.pick_pct.map(fmt), wr=q3_r.wr.map(fmt),
                                    deaths_pg=q3_r.deaths_pg.map(fmt))[cols_q()]))
    out.append("")
    out.append("### Q9 - Teemo picked at least once\n")
    out.append(f"- 2026 pro picks (all leagues in DB): {q9['pro_picks_2026_all']}; bans: "
               f"{q9['pro_bans_2026_all']}; picks in recent top-level window: "
               f"{q9['pick_in_recent_top']}; last 2026 pick: {q9['last_pick']}.")
    out.append(f"- Patch changes since 16.17: {q9['changes']}.\n")
    out.append("### Q10 - unique champions picked\n")
    out.append(f"- Recent top-level window: {n_unique} distinct champions over {G_r} games = "
               f"**{fmt(per100)} per 100 games**.")
    out.append(f"- All 2026 top-level play: {n_unique_ytd} distinct over "
               f"{n_games_ytd} games = {fmt(per100_ytd)} per 100.")
    wc = {int(r.y): int(r.n) for r in worlds_counts.itertuples(index=False)}
    for y in (2024, 2025):
        out.append(f"- Worlds {y}: {unique_worlds[y]} distinct over {wc[y]} games = "
                   f"{fmt(100.0 * unique_worlds[y] / wc[y], 0)} per 100 games (Fearless).")
    out.append(f"- Estimate for Worlds 2026 (~{W} games): about {W} unique champions "
               f"(Fearless keeps pushing this to roughly one new champion per game).\n")
    out.append("### Q11 - games under 32:00\n")
    out.append(f"- Recent top-level window: {fmt(s_rec[0])}% under 32:00 (n={s_rec[2]}, "
               f"mean {fmt(s_rec[1])} min).")
    out.append(f"- Patch 16.18 (any league): {fmt(s_e1618[0])}% (n={s_e1618[2]}, mean "
               f"{fmt(s_e1618[1])} min); patch 16.20: {fmt(s_e1620[0])}% (n={s_e1620[2]}, mean "
               f"{fmt(s_e1620[1])} min); patch 16.17 (any league): {fmt(s_e1617[0])}% (n={s_e1617[2]}).")
    out.append(f"- Worlds reference: 2024 {fmt(s_w[2024][0])}% under 32:00; 2025 {fmt(s_w[2025][0])}%.")
    out.append("")
    out.append(md_table(dur_by_patch.reset_index(drop=True).assign(
        pct_under_32=dur_by_patch.pct_under_32.map(fmt).values,
        mean_min=dur_by_patch.mean_min.map(fmt).values)))
    out.append("")
    out.append(NARRATIVE["crystal_notes"] or "_(narrative pending)_")
    out.append("")

    out.append("## 5. Play-In team meta fit\n")
    out.append("Team meta fit = share of 2026 starter games on the meta top 30. Pool depth = "
               "distinct champions with at least 3 games and at least 50% WR in 2026. "
               "adj_pp = clip(1.5 x mean(z_fit, z_depth), -3, +3), z-scored across all 19 teams "
               "in rosters_2026.csv.\n")
    tp = teams[teams.team.isin(PLAYIN_TEAMS)][["team", "starters_games_2026", "meta_top30_share_pct",
                                                "nerf_share_pct", "buff_share_pct",
                                                "mean_pool_depth", "z_fit", "z_depth", "adj_pp"]]
    tp = tp.assign(**{c: tp[c].map(fmt) for c in ["meta_top30_share_pct", "nerf_share_pct",
                                                 "buff_share_pct", "mean_pool_depth", "z_fit",
                                                 "z_depth", "adj_pp"]})
    out.append(md_table(tp))
    out.append("")
    out.append("All 19 teams (for context):\n")
    allt = teams[["team", "meta_top30_share_pct", "mean_pool_depth", "adj_pp"]].assign(
        meta_top30_share_pct=teams.meta_top30_share_pct.map(fmt),
        mean_pool_depth=teams.mean_pool_depth.map(fmt),
        adj_pp=teams.adj_pp.map(fmt))
    out.append(md_table(allt))
    out.append("")
    out.append("Starters (Play-In teams) with their top 3 2026 champions:\n")
    pp = players[players.team.isin(PLAYIN_TEAMS)][["team", "role", "player", "games_2026",
                                                    "top3", "pool_depth", "low_sample"]]
    out.append(md_table(pp.assign(low_sample=pp.low_sample.map({True: "yes", False: ""}))))
    out.append("")
    out.append(NARRATIVE["team_notes"] or "_(narrative pending)_")
    out.append("")

    out.append("## 6. Data gaps and caveats\n")
    out.append(f"- Unmatched change names (not in DB champion list): {unmatched or 'none'}.")
    out.append("- Patch 16.16 (Riot 26.16) notes were not fetched, so nothing before 26.17 is encoded.")
    out.append("- Patch labels in the DB are noisy: 16.17 and 16.18 extend past their Riot release "
               "dates, and 16.19 is missing. The 16.18 label covers Riot 26.18 and 26.19 games.")
    out.append("- Third-party reports of Orianna and Sylas/Varus changes were not in the official "
               "notes and are not encoded.")
    out.append(NARRATIVE["gaps"] or "")
    out.append("")
    REPORT.write_text("\n".join(out), encoding="utf-8")


def cols_q():
    return ["champion", "picked_games", "pick_pct", "wr", "pg_games", "deaths_pg", "roles"]


if __name__ == "__main__":
    main()
