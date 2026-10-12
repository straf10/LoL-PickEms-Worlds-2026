"""Build the Worlds 2026 team, roster and alias tables from data/pickems.duckdb.

Read-only on the DuckDB file (built by ingest/oracles.py). No network access.
Run from the project root:  python -m ingest.rosters_from_db

Writes:
  data/worlds2026_teams.csv   one row per Worlds team (OE name, OE team_id, seed, stage entry)
  data/rosters_2026.csv       starters (is_starter=True) and 2026 bench players per team
  data/aliases.csv            team names per OE team_id, player names per OE player_id
  outputs/rosters_report.md   replaces only the block between the GENERATED markers
"""
import sys

import duckdb
import pandas as pd

from common.paths import DB_PATH as DB, ROOT
TEAMS_CSV = ROOT / "data" / "worlds2026_teams.csv"
ROSTERS_CSV = ROOT / "data" / "rosters_2026.csv"
ALIASES_CSV = ROOT / "data" / "aliases.csv"
REPORT = ROOT / "outputs" / "rosters_report.md"
BEGIN = "<!-- BEGIN GENERATED: rosters_from_db.py -->"
END = "<!-- END GENERATED: rosters_from_db.py -->"

SEASON = 2026
DOMESTIC = ["LCK", "LPL", "LEC", "LCS", "LCP", "CBLOL"]
QUALIFIER = "WLDQ"
LAST_N = 10
ROLE_ORDER = ["Top", "Jungle", "Mid", "Bot", "Support"]

# code, OE teamname (exact), region, seed, stage_entry, domestic league, route evidence, notes
TEAMS = [
    ("GEN", "Gen.G", "LCK", "LCK1", "swiss", "LCK",
     "LCK 2026 Split 3 champion: won final 3-1 vs HLE (2026-09-13)", ""),
    ("HLE", "Hanwha Life Esports", "LCK", "LCK2", "swiss", "LCK",
     "LCK 2026 Split 3 runner-up: lost final 1-3 to GEN (2026-09-13)",
     "MSI 2026 champion in OE data: beat BLG 3-2 (2026-07-12, last MSI series)"),
    ("T1", "T1", "LCK", "LCK3", "swiss", "LCK",
     "LCK 2026 Split 3: lost 1-3 to HLE (2026-09-12), last T1 series", ""),
    ("DK", "Dplus Kia", "LCK", "LCK4", "swiss", "LCK",
     "LCK 2026 Split 3: lost 1-3 to T1 (2026-09-06), last DK series", ""),
    ("AL", "Anyone's Legend", "LPL", "LPL1", "swiss", "LPL",
     "LPL 2026 Split 3 champion: won final 3-1 vs BLG (2026-09-13)", ""),
    ("BLG", "Bilibili Gaming", "LPL", "LPL2", "swiss", "LPL",
     "LPL 2026 Split 3 runner-up: lost final 1-3 to AL (2026-09-13)", ""),
    ("TES", "Top Esports", "LPL", "LPL3", "swiss", "LPL",
     "WLDQ 2026-09-17: beat IG 3-1; no later TES game in OE data",
     "LPL3 is from earlier research. Data cannot confirm TES vs IG seed order. Lost 2-3 to IG in LPL playoffs 2026-09-05."),
    ("IG", "Invictus Gaming", "LPL", "LPL4", "swiss", "LPL",
     "WLDQ 2026-09-19: beat JDG 3-1 (confirmed in OE data)",
     "Brief item confirmed. Lost 2-3 to AL in LPL playoffs 2026-09-12. Seed vs TES unconfirmed."),
    ("G2", "G2 Esports", "LEC", "LEC1", "swiss", "LEC",
     "LEC Summer 2026 champion: won final 3-0 vs KOI (2026-09-20)", ""),
    ("MKOI", "Movistar KOI", "LEC", "LEC2", "swiss", "LEC",
     "LEC Summer 2026 runner-up: lost final 0-3 to G2 (2026-09-20)",
     "Not the academy 'Movistar KOI Fenix'."),
    ("KC", "Karmine Corp", "LEC", "LEC3", "playin", "LEC",
     "LEC Summer 2026: lost 0-3 to KOI (2026-09-19), last KC series",
     "Play-In entrant (UB2 vs C9)."),
    ("TL", "Team Liquid", "LCS", "LCS1", "swiss", "LCS",
     "LCS Summer 2026 champion: won final 3-1 vs LYON (2026-10-04)",
     "Old file said 'Team Liquid Alienware'; OE name is 'Team Liquid'."),
    ("LYON", "LYON", "LCS", "LCS2", "swiss", "LCS",
     "LCS Summer 2026 runner-up: lost final 1-3 to TL (2026-10-04)", ""),
    ("C9", "Cloud9", "LCS", "LCS3", "playin", "LCS",
     "LCS Summer 2026: lost 1-3 to LYON (2026-10-03), last C9 series",
     "Old file said 'Cloud 9 KIA'; OE name is 'Cloud9'. Play-In entrant (UB2 vs KC)."),
    ("TSW", "Team Secret Whales", "LCP", "LCP1", "swiss", "LCP",
     "LCP 2026 Split 3: won last series 3-0 vs CFO (2026-08-30)",
     "OE does not flag LCP playoffs; 'final' is inferred from being the last series (CFO also lost 0-3 to TSW on 08-23)."),
    ("CFO", "CTBC Flying Oyster", "LCP", "LCP2", "swiss", "LCP",
     "LCP 2026 Split 3: lost 0-3 to TSW (2026-08-30), inferred runner-up", "Same caveat as TSW."),
    ("MVK", "MVK Esports", "LCP", "LCP3", "playin", "LCP",
     "LCP 2026 Split 3: lost 1-3 to CFO (2026-08-29), last MVK series",
     "Play-In entrant (UB1 vs FUR). Vietnam."),
    ("LOS", "LØS", "CBLOL", "CBLOL1", "swiss", "CBLOL",
     "CBLOL 2026 Split 2 champion: won final 3-2 vs FURIA (2026-10-10)",
     "Verdict: CBLOL1 = LØS. LOUD is a different OE team_id (lost 0-3 to FURIA 2026-10-03). Not Play-In."),
    ("FUR", "FURIA", "CBLOL", "CBLOL2", "playin", "CBLOL",
     "CBLOL 2026 Split 2 runner-up: lost 2-3 to LØS (2026-10-10)",
     "Play-In per user brief (CBLOL2 slot). Play-In entrant (UB1 vs MVK)."),
]

# Names from the old partial report and old alias file. Kept as aliases even when OE never uses them.
OLD_NAMES = {
    "GEN": ["Gen G"], "HLE": ["Hanwha Life", "HLE"], "T1": [], "DK": ["Dplus KIA", "Dplus"],
    "AL": ["AL"], "BLG": ["BLG"], "TES": ["TES"], "IG": ["Shanghai Invictus Gaming", "Invictus Gaming"],
    "G2": ["G2"], "MKOI": ["KOI", "MKOI"], "KC": ["KC"],
    "TL": ["Team Liquid Alienware", "Team Liquid", "TLAW", "TL"],
    "LYON": [], "C9": ["Cloud 9 KIA", "Cloud 9", "Cloud9 Kia", "C9"], "TSW": ["TSW"],
    "CFO": ["CTBC Flying Oyster", "Flying Oyster", "CFO"], "MVK": ["MVK"],
    "LOS": ["LØS", "LOS"], "FUR": ["FURIA Esports", "FUR"],
}


def fmt(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def load(con):
    games = con.execute("""
        select game_id, league, year, date_utc, blue_team, blue_team_id, red_team, red_team_id, winner_team
        from games""").df()
    pg = con.execute("""
        select p.game_id, p.player, p.player_id, p.team, p.team_id, p.role, p.date_utc, g.league, g.year
        from player_games p join games g on g.game_id = p.game_id""").df()
    return games, pg


def team_name_rows(games):
    """Long table (name, tid, year, date) with one row per team appearance in a game."""
    blue = games.rename(columns={"blue_team": "name", "blue_team_id": "tid"})[["name", "tid", "year", "date_utc"]]
    red = games.rename(columns={"red_team": "name", "red_team_id": "tid"})[["name", "tid", "year", "date_utc"]]
    return pd.concat([blue, red], ignore_index=True)


def resolve_ids(names):
    out = {}
    for code, oe_name, *_ in TEAMS:
        sub = names[(names.name == oe_name) & names.year.isin([2024, 2025, 2026])]
        ids_2026 = sub[sub.year == SEASON].tid.dropna().unique()
        if len(ids_2026) != 1:
            raise SystemExit(f"{code}: expected one 2026 team_id for {oe_name!r}, got {list(ids_2026)}")
        tid = ids_2026[0]
        older = set(sub[sub.year < SEASON].tid.dropna().unique()) - {tid}
        if older:
            print(f"  WARNING {code}: older team_id(s) for {oe_name!r} differ from 2026: {older}")
        out[code] = tid
    return out


def team_games_2026(games, tid):
    g = games[(games.year == SEASON) & games.league.isin(DOMESTIC + [QUALIFIER])
              & ((games.blue_team_id == tid) | (games.red_team_id == tid))]
    return g.sort_values(["date_utc", "game_id"])


def history(pg, pid):
    """'Team (first..last, n games)' for 2025-2026, by team_id, earliest first."""
    h = pg[(pg.player_id == pid) & pg.year.isin([2025, 2026])]
    if h.empty:
        return ""
    parts = []
    for tid, grp in h.groupby("team_id", dropna=True):
        name = grp.sort_values("date_utc").team.iloc[-1]
        parts.append((grp.date_utc.min(), f"{name} ({fmt(grp.date_utc.min())}..{fmt(grp.date_utc.max())}, {grp.game_id.nunique()} games)"))
    return "; ".join(s for _, s in sorted(parts, key=lambda x: x[0]))


def player_facts(pg, pid):
    p = pg[pg.player_id == pid].sort_values("date_utc")
    last = p.iloc[-1]
    return {
        "games_2026": int(p[p.year == SEASON].game_id.nunique()),
        "last_game_date": fmt(last.date_utc),
        "last_team_id": last.team_id,
        "last_team": last.team,
        "names": list(dict.fromkeys(p.player.tolist()[::-1]))[::-1],
    }


def build_rosters(games, pg, ids):
    rows, team_info = [], {}
    for code, oe_name, region, seed, stage, dom, route, notes in TEAMS:
        tid = ids[code]
        g = team_games_2026(games, tid)
        last10 = g.tail(LAST_N)
        gids = set(last10.game_id)
        team_rows = pg[(pg.team_id == tid) & pg.game_id.isin(gids)]
        latest_gid = last10.game_id.iloc[-1]
        latest_pids = set(pg[(pg.game_id == latest_gid) & (pg.team_id == tid)].player_id)
        team_info[code] = {"tid": tid, "n2026": len(g), "n10": len(last10),
                           "first10": fmt(last10.date_utc.min()), "last": fmt(last10.date_utc.max())}

        by_role = (team_rows.sort_values("date_utc")
                   .groupby(["role", "player_id"])
                   .agg(n=("game_id", "size"), last=("date_utc", "max"), name=("player", "last"))
                   .reset_index())
        for role in ROLE_ORDER:
            sub = by_role[by_role.role == role].sort_values(["n", "last"], ascending=False)
            if sub.empty:
                print(f"  WARNING {code}: no {role} in last {LAST_N} games")
                continue
            st, others = sub.iloc[0], sub.iloc[1:]
            pid = st.player_id
            f = player_facts(pg, pid)
            flags = []
            if not others.empty:
                flags.append("ROLE_CHANGED_LAST10: also " + ", ".join(f"{r['name']}({r['n']})" for _, r in others.iterrows()))
            if pid not in latest_pids:
                flags.append("MISSED_LATEST_GAME")
            if f["last_team_id"] != tid:
                flags.append(f"LAST_GAME_ELSEWHERE: {f['last_team']} {f['last_game_date']}")
            if f["games_2026"] < 5:
                flags.append(f"LOW_2026_SAMPLE: {f['games_2026']} games")
            # share of this team's 2026 domestic+WLDQ games the starter played for it (mid-season swap)
            mine = pg[(pg.team_id == tid) & (pg.player_id == pid) & pg.game_id.isin(set(g.game_id))]
            tenure = int(mine.game_id.nunique())
            if tenure < 0.8 * len(g):
                flags.append(f"PARTIAL_2026_TENURE: {tenure}/{len(g)} team games, first {fmt(mine.date_utc.min())}")
            rows.append({"team_id": code, "role": role, "player": st["name"], "player_id": pid,
                         "games_2026": f["games_2026"], "last_game_date": f["last_game_date"],
                         "is_starter": True, "previous_teams_2025_2026": history(pg, pid),
                         "flag": "; ".join(flags), "_names": f["names"]})

        # 2026 bench: anyone else who played for this team_id in 2026 and is not a starter here
        starter_ids = {r["player_id"] for r in rows if r["team_id"] == code}
        bench = pg[(pg.team_id == tid) & (pg.year == SEASON)]
        for pid, grp in bench.groupby("player_id"):
            if pid in starter_ids:
                continue
            f = player_facts(pg, pid)
            role = grp.role.mode().iat[0]
            flag = "BENCH_2026"
            if f["last_team_id"] != tid:
                flag += f"; LAST_GAME_ELSEWHERE: {f['last_team']} {f['last_game_date']}"
            rows.append({"team_id": code, "role": role, "player": grp.sort_values("date_utc").player.iloc[-1],
                         "player_id": pid, "games_2026": f["games_2026"], "last_game_date": f["last_game_date"],
                         "is_starter": False, "previous_teams_2025_2026": history(pg, pid),
                         "flag": flag, "_names": f["names"]})
    return rows, team_info


def verify(games, pg, rows):
    print("\n== Checks")
    starters = [r for r in rows if r["is_starter"]]
    print(f"  starters: {len(starters)} (expect 95); unique player_ids: {len({r['player_id'] for r in starters})}")
    zero = [r["player"] for r in starters if r["games_2026"] == 0]
    print(f"  starters with 0 games in 2026: {zero or 'none'}")
    for name in ["Faker", "Peyz", "Gumayusi"]:
        p = pg[pg.player.str.lower() == name.lower()]
        if p.empty:
            print(f"  {name}: not found")
            continue
        pid = p.player_id.iloc[-1]
        f = player_facts(pg, pid)
        print(f"  {name}: games_2026={f['games_2026']} last={f['last_game_date']} team={f['last_team']} | 2025-26: {history(pg, pid)}")
    print("  last series per league (2026):")
    for lg in DOMESTIC + ["MSI", QUALIFIER]:
        g = games[(games.league == lg) & (games.year == SEASON)].copy()
        if g.empty:
            continue
        g["a"] = g[["blue_team", "red_team"]].min(axis=1)
        g["b"] = g[["blue_team", "red_team"]].max(axis=1)
        g["d"] = g.date_utc.dt.date
        series = []
        for (a, b, d), x in g.groupby(["a", "b", "d"]):
            series.append((x.date_utc.min(), a, b, int((x.winner_team == a).sum()), int((x.winner_team == b).sum())))
        for t0, a, b, aw, bw in sorted(series, key=lambda s: s[0], reverse=True)[:2]:
            print(f"    {lg}: {fmt(t0)} {a} {aw}-{bw} {b}")


def write_teams(ids):
    out = []
    for code, oe_name, region, seed, stage, dom, route, notes in TEAMS:
        out.append({"team_id": code, "team_name_oe": oe_name, "oe_team_id": ids[code], "region": region,
                    "seed": seed, "stage_entry": stage, "qualification_route": route, "notes": notes})
    df = pd.DataFrame(out)
    df.to_csv(TEAMS_CSV, index=False, encoding="utf-8")
    return df


def write_rosters(rows):
    df = pd.DataFrame(rows)
    team_order = {t[0]: i for i, t in enumerate(TEAMS)}
    role_order = {r: i for i, r in enumerate(ROLE_ORDER)}
    df["_team"] = df.team_id.map(team_order)
    df["_role"] = df.role.map(role_order).fillna(9)
    df = df.sort_values(["_team", "is_starter", "_role", "games_2026"], ascending=[True, False, True, False])
    df[["team_id", "role", "player", "player_id", "games_2026", "last_game_date", "is_starter",
        "previous_teams_2025_2026", "flag"]].to_csv(ROSTERS_CSV, index=False, encoding="utf-8")
    return df


def write_aliases(games, rows, ids):
    names = team_name_rows(games)
    new = []
    for code, oe_name, *_ in TEAMS:
        tid = ids[code]
        team_names = set(names[(names.tid == tid) & names.year.isin([2024, 2025, 2026])].name.dropna())
        team_names |= {oe_name, code} | set(OLD_NAMES.get(code, []))
        new += [("team", n, code) for n in sorted(team_names)]
    for r in sorted(rows, key=lambda r: not r["is_starter"]):  # starters first: they win alias clashes
        new += [("player", n, r["player_id"]) for n in r["_names"]]
    # keep old name-keyed player rows (canonical = name) for players not in OE data
    if ALIASES_CSV.exists():
        old = pd.read_csv(ALIASES_CSV, encoding="utf-8", dtype=str, keep_default_na=False)
        used = {alias for _, alias, _ in new}
        for _, o in old[old.entity_type == "player"].iterrows():
            if o.canonical_id == o.alias and o.alias not in used:
                new.append(("player", o.alias, o.canonical_id))
    seen, out = {}, []
    for etype, alias, canon in new:
        key = (etype, alias)
        if key in seen:
            if seen[key] != canon:
                # same handle used by two different OE players/teams: first (starter-derived) mapping wins
                print(f"  ALIAS CONFLICT {etype} {alias!r}: keeping {seen[key][-8:]}, dropping {canon[-8:]}")
            continue
        seen[key] = canon
        out.append((etype, alias, canon))
    pd.DataFrame(out, columns=["entity_type", "alias", "canonical_id"]).to_csv(ALIASES_CSV, index=False, encoding="utf-8")
    return len(out)


def report_block(teams_df, rosters_df):
    lines = [BEGIN, "",
             "### Worlds 2026 teams (generated from the OE data)", "",
             "| Code | OE name | OE team_id (last 8) | Seed | Entry | Evidence in 2026 data |",
             "|---|---|---|---|---|---|"]
    for _, t in teams_df.iterrows():
        lines.append(f"| {t.team_id} | {t.team_name_oe} | `{t.oe_team_id[-8:]}` | {t.seed} | {t.stage_entry} | {t.qualification_route} |")
    lines += ["", f"### Starting five (most frequent player per role in the last {LAST_N} domestic + WLDQ games of 2026)", ""]
    for code, oe_name, region, seed, stage, dom, route, notes in TEAMS:
        sub = rosters_df[rosters_df.team_id == code]
        st = sub[sub.is_starter == True]  # noqa: E712
        bench = sub[sub.is_starter == False]  # noqa: E712
        lines += [f"#### {code} - {oe_name} ({seed})", "",
                  "| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |",
                  "|---|---|---|---|---|---|"]
        for _, r in st.iterrows():
            lines.append(f"| {r.role} | {r.player} | `{r.player_id[-8:]}` | {r.games_2026} | {r.last_game_date} | {r.flag or '-'} |")
        if not bench.empty:
            lines += ["", "Other 2026 players for this team_id: " +
                      ", ".join(f"{b.player} ({b.role}, {b.games_2026}g)" for _, b in bench.iterrows())]
        lines.append("")
    lines.append(END)
    return "\n".join(lines) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(DB), read_only=True)
    games, pg = load(con)
    con.close()
    ids = resolve_ids(team_name_rows(games))
    print("== Team ids")
    for code, oe_name, *_ in TEAMS:
        print(f"  {code:5s} {oe_name:24s} {ids[code]}")
    rows, team_info = build_rosters(games, pg, ids)
    print("\n== Last-10 windows")
    for code, info in team_info.items():
        print(f"  {code:5s} 2026 domestic+WLDQ games={info['n2026']:3d}  last10 {info['first10']}..{info['last']}")
    verify(games, pg, rows)
    teams_df = write_teams(ids)
    rosters_df = write_rosters(rows)
    n_alias = write_aliases(games, rows, ids)
    print(f"\nwrote {TEAMS_CSV.name} ({len(teams_df)} teams), {ROSTERS_CSV.name} ({len(rosters_df)} rows), "
          f"{ALIASES_CSV.name} ({n_alias} aliases)")
    if REPORT.exists() and BEGIN in REPORT.read_text(encoding="utf-8"):
        text = REPORT.read_text(encoding="utf-8")
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        REPORT.write_text(head + report_block(teams_df, rosters_df) + tail.lstrip("\n"), encoding="utf-8")
        print(f"updated generated block in {REPORT.name}")
    else:
        print(f"report markers not found in {REPORT.name}; block not written")


if __name__ == "__main__":
    main()
