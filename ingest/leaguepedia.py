"""Ingest Leaguepedia (lol.fandom.com) Cargo data for the Worlds 2026 Pick'Em model.

Run from the project root:   python ingest/leaguepedia.py
Options:                     --discover   fetch only the Tournaments table and print the leagues found

Two phases:
  1. fetch  - every Cargo page is cached as JSON under data/raw/leaguepedia/games/<table>/.
              A cached page is never requested again, so a rerun with a full cache makes zero network calls.
  2. build  - rebuilds data/pickems.duckdb and outputs/ingest_report.md from the cache only.

Raw responses are JSON data files only; nothing downloaded is ever executed.
"""

import argparse
import datetime as dt
import json
import re
import sys
import time
import traceback
from pathlib import Path

import duckdb
import mwclient
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "leaguepedia" / "games"
DB_PATH = ROOT / "data" / "pickems.duckdb"
REPORT_PATH = ROOT / "outputs" / "ingest_report.md"

UA = "LOL_PICKEMS research script"
SITE = "lol.fandom.com"
PAGE = 500            # Cargo page size
MIN_GAP_S = 2.0       # minimum seconds between network requests
BACKOFF_S = [10, 30, 90, 180]   # retry waits after a ratelimit / HTTP error

YEARS = ["2024", "2025", "2026"]

# League values as Leaguepedia's Tournaments.League field spells them.
# Confirmed against the Tournaments table in the discovery run (see outputs/ingest_report.md).
MAIN_LEAGUES_2026 = {"LCK", "LPL", "LEC", "LCS", "LCP", "CBLOL"}
INTERNATIONAL_LEAGUES = {"World Championship", "Mid-Season Invitational", "First Stand", "Esports World Cup"}

SCOREBOARD_GAMES_FIELDS = (
    "GameId,MatchId,OverviewPage,Tournament,Team1,Team2,WinTeam,Winner,Gamelength,Gamelength_Number,"
    "DateTime_UTC,Patch,Team1Picks,Team2Picks,Team1Bans,Team2Bans,Team1Kills,Team2Kills,Team1Gold,Team2Gold,"
    "Team1Dragons,Team2Dragons,Team1Barons,Team2Barons,Team1Towers,Team2Towers,N_GameInMatch"
)
SCOREBOARD_PLAYERS_FIELDS = (
    "GameId,OverviewPage,Link,Name,Team,Champion,Role,Side,PlayerWin,Kills,Deaths,Assists,CS,Gold,"
    "DamageToChampions,VisionScore,TeamKills"
)
PICKS_BANS_FIELDS = (
    "GameId," + ",".join(f"Team{t}Ban{i}" for t in (1, 2) for i in range(1, 6)) + ","
    + ",".join(f"Team{t}Pick{i}" for t in (1, 2) for i in range(1, 6)) + ","
    + ",".join(f"Team{t}Role{i}" for t in (1, 2) for i in range(1, 6))
)
MATCH_SCHEDULE_FIELDS = "MatchId,OverviewPage,Team1,Team2,Winner,BestOf,DateTime_UTC,Team1Score,Team2Score"
TOURNAMENT_FIELDS = "Name,OverviewPage,League,Region,Year,DateStart,IsQualifier,IsPlayoffs"


class GiveUp(RuntimeError):
    """Raised when Leaguepedia keeps refusing requests after all backoff steps."""


# ----------------------------------------------------------------------------- fetch layer

def sanitize(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_")


class Fetcher:
    def __init__(self):
        self.site = None
        self.last_request = 0.0
        self.network_calls = 0
        self.failures = []          # (table, key, offset, message) for the report
        self._names = {}            # sanitized name -> raw key, to catch collisions

    def _site(self):
        if self.site is None:
            self.site = mwclient.Site(SITE, path="/", clients_useragent=UA)
        return self.site

    def _request(self, **kwargs):
        gap = MIN_GAP_S - (time.time() - self.last_request)
        if gap > 0:
            time.sleep(gap)
        attempt = 0
        while True:
            try:
                self.last_request = time.time()
                self.network_calls += 1
                return self._site().api("cargoquery", **kwargs)
            except mwclient.errors.APIError as e:
                code = e.args[0] if e.args else ""
                if code != "ratelimited":
                    raise   # a real query error (e.g. unknown field) - do not retry
                problem = f"ratelimited: {e.args[1] if len(e.args) > 1 else ''}"
            except (requests.RequestException, mwclient.errors.InvalidResponse, ConnectionError) as e:
                problem = f"HTTP/connection error: {e!r}"[:300]
            if attempt >= len(BACKOFF_S):
                raise GiveUp(problem)
            wait = BACKOFF_S[attempt]
            attempt += 1
            print(f"  ! {problem} - backing off {wait}s (retry {attempt}/{len(BACKOFF_S)})", flush=True)
            time.sleep(wait)

    def cached_rows(self, table: str, key: str, fields: str, where: str) -> list:
        """Return all Cargo rows for (table, key), reading each page from cache when possible."""
        safe = sanitize(key)
        previous = self._names.setdefault((table, safe), key)
        if previous != key:
            raise RuntimeError(f"Cache name collision in {table}: {previous!r} and {key!r} -> {safe!r}")
        folder = RAW / table
        folder.mkdir(parents=True, exist_ok=True)

        rows, offset = [], 0
        while True:
            path = folder / f"{safe}_{offset}.json"
            if path.exists():
                page = json.loads(path.read_text(encoding="utf-8"))
            else:
                print(f"  fetch {table} {key!r} offset={offset}", flush=True)
                try:
                    resp = self._request(tables=table, fields=fields, where=where, limit=PAGE, offset=offset)
                except GiveUp:
                    raise
                except mwclient.errors.APIError as e:
                    self.failures.append((table, key, offset, f"API error {e.args[0]}: {str(e.args[1])[:200]}"))
                    raise
                page = {
                    "table": table, "key": key, "where": where, "fields": fields, "offset": offset,
                    "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "response": resp,
                }
                tmp = path.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
                tmp.replace(path)
            batch = [r["title"] for r in page["response"].get("cargoquery", [])]
            rows.extend(batch)
            if len(batch) < PAGE:
                return rows
            offset += PAGE


def cargo_sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def fetch_tournaments(fetcher: Fetcher) -> list:
    tournaments = []
    for year in YEARS:
        tournaments += fetcher.cached_rows("Tournaments", f"year_{year}", TOURNAMENT_FIELDS, f"Year='{year}'")
    # de-duplicate on OverviewPage (a page could in principle appear twice across year queries)
    seen, unique = set(), []
    for t in tournaments:
        if t["OverviewPage"] not in seen:
            seen.add(t["OverviewPage"])
            unique.append(t)
    return unique


def in_scope(t: dict) -> bool:
    year = int(t["Year"])
    league = t["League"]
    if year == 2026:
        return league in MAIN_LEAGUES_2026 or league in INTERNATIONAL_LEAGUES
    if year in (2024, 2025):
        return league in INTERNATIONAL_LEAGUES
    return False


def fetch_games(fetcher: Fetcher, tournaments: list) -> None:
    for t in tournaments:
        page = t["OverviewPage"]
        where = f"OverviewPage={cargo_sql_quote(page)}"
        for table, fields in [
            ("ScoreboardGames", SCOREBOARD_GAMES_FIELDS),
            ("ScoreboardPlayers", SCOREBOARD_PLAYERS_FIELDS),
            ("PicksAndBansS7", PICKS_BANS_FIELDS),
            ("MatchSchedule", MATCH_SCHEDULE_FIELDS),
        ]:
            fetcher.cached_rows(table, page, fields, where)


# ----------------------------------------------------------------------------- build layer

def load_cached(table: str, keys: set | None = None) -> list:
    rows = []
    folder = RAW / table
    if not folder.exists():
        return rows
    for path in sorted(folder.glob("*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        if keys is not None and page["key"] not in keys:
            continue
        rows.extend(r["title"] for r in page["response"].get("cargoquery", []))
    return rows


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace("", None), errors="coerce")


def build(tournaments_all: list, fetch_failures: list, network_calls: int, discovery_only: bool = False) -> None:
    scope = [t for t in tournaments_all if in_scope(t)]
    scope_pages = {t["OverviewPage"] for t in scope}
    tmap = {t["OverviewPage"]: t for t in scope}

    tournaments = pd.DataFrame([{
        "overview_page": t["OverviewPage"],
        "name": t["Name"],
        "league": t["League"],
        "region": t["Region"],
        "year": int(t["Year"]),
        "date_start": pd.to_datetime(t["DateStart"] or None).date() if t["DateStart"] else None,
        "is_international": t["League"] in INTERNATIONAL_LEAGUES,
        "is_qualifier": t["IsQualifier"] == "1",
        "is_playoffs": t["IsPlayoffs"] == "1",
    } for t in scope])

    # --- games
    sg = pd.DataFrame(load_cached("ScoreboardGames", scope_pages))
    sp = pd.DataFrame(load_cached("ScoreboardPlayers", scope_pages))
    pb = pd.DataFrame(load_cached("PicksAndBansS7", scope_pages))
    ms = pd.DataFrame(load_cached("MatchSchedule", scope_pages))

    dup_games = int(sg["GameId"].duplicated().sum()) if len(sg) else 0
    sg = sg.drop_duplicates("GameId", keep="first")
    sp = sp.drop_duplicates(["GameId", "Link"], keep="first") if len(sp) else sp

    # Blue side: take Side of the players on Team1 (majority vote). Confirms whether Team1 is blue.
    blue_votes = {}
    if len(sp):
        side_rows = sp[sp["Side"].isin(["Blue", "Red"])]
        for (gid, team, side), n in side_rows.groupby(["GameId", "Team", "Side"]).size().items():
            blue_votes.setdefault(gid, {}).setdefault(team, {})[side] = n
    team1_is_blue, side_unknown = {}, 0
    for _, g in sg.iterrows():
        votes = blue_votes.get(g["GameId"], {}).get(g["Team1"], {})
        if votes.get("Blue", 0) > votes.get("Red", 0):
            team1_is_blue[g["GameId"]] = True
        elif votes.get("Red", 0) > votes.get("Blue", 0):
            team1_is_blue[g["GameId"]] = False
        else:
            side_unknown += 1
            team1_is_blue[g["GameId"]] = True   # fall back to the Leaguepedia convention
    sg["team1_is_blue"] = sg["GameId"].map(team1_is_blue)

    games = pd.DataFrame({
        "game_id": sg["GameId"],
        "match_id": sg["MatchId"],
        "overview_page": sg["OverviewPage"],
        "league": sg["OverviewPage"].map(lambda p: tmap[p]["League"]),
        "year": sg["OverviewPage"].map(lambda p: int(tmap[p]["Year"])),
        "date_utc": pd.to_datetime(sg["DateTime_UTC"].replace("", None), errors="coerce"),
        "patch": sg["Patch"].replace("", None),
        "team1": sg["Team1"],
        "team2": sg["Team2"],
        "winner_team": sg.apply(lambda g: "team1" if g["WinTeam"] == g["Team1"] else ("team2" if g["WinTeam"] == g["Team2"] else None), axis=1),
        "blue_team": sg.apply(lambda g: g["Team1"] if g["team1_is_blue"] else g["Team2"], axis=1),
        "red_team": sg.apply(lambda g: g["Team2"] if g["team1_is_blue"] else g["Team1"], axis=1),
        "duration_sec": num(sg["Gamelength_Number"]),
        "team1_kills": num(sg["Team1Kills"]).astype("Int64"),
        "team2_kills": num(sg["Team2Kills"]).astype("Int64"),
        "team1_gold": num(sg["Team1Gold"]),
        "team2_gold": num(sg["Team2Gold"]),
        "team1_picks": sg["Team1Picks"].replace("", None),
        "team2_picks": sg["Team2Picks"].replace("", None),
        "team1_bans": sg["Team1Bans"].replace("", None),
        "team2_bans": sg["Team2Bans"].replace("", None),
        "game_in_match": num(sg["N_GameInMatch"]).astype("Int64"),
    })

    # --- player games
    player_games = pd.DataFrame({
        "game_id": sp["GameId"],
        "overview_page": sp["OverviewPage"],
        "player_link": sp["Link"],
        "player_name": sp["Name"],
        "team": sp["Team"],
        "champion": sp["Champion"].replace("", None),
        "role": sp["Role"].replace("", None),
        "side": sp["Side"].replace("", None),
        "win": sp["PlayerWin"].map({"Yes": True, "No": False}),
        "kills": num(sp["Kills"]),
        "deaths": num(sp["Deaths"]),
        "assists": num(sp["Assists"]),
        "cs": num(sp["CS"]),
        "gold": num(sp["Gold"]),
        "damage": num(sp["DamageToChampions"]),
        "vision": num(sp["VisionScore"]),
        "team_kills": num(sp["TeamKills"]),
    }) if len(sp) else pd.DataFrame()

    # --- picks and bans (ordered)
    if len(pb):
        dup_pb = int(pb["GameId"].duplicated().sum())
        pb = pb.drop_duplicates("GameId", keep="first")
        picks_bans = pb.rename(columns=lambda c: c.lower() if c != "GameId" else "game_id")
        picks_bans["overview_page"] = picks_bans["game_id"].map(dict(zip(sg["GameId"], sg["OverviewPage"])))
        cols = ["game_id", "overview_page"] + [c for c in picks_bans.columns if c not in ("game_id", "overview_page")]
        picks_bans = picks_bans[cols]
        for c in picks_bans.columns:
            if c not in ("game_id", "overview_page"):
                picks_bans[c] = picks_bans[c].replace("", None)
    else:
        dup_pb = 0
        picks_bans = pd.DataFrame(columns=["game_id", "overview_page"])

    # --- series
    series = pd.DataFrame({
        "match_id": ms["MatchId"],
        "overview_page": ms["OverviewPage"],
        "team1": ms["Team1"],
        "team2": ms["Team2"],
        "winner": ms.apply(lambda m: m["Team1"] if m["Winner"] == "1" else (m["Team2"] if m["Winner"] == "2" else None), axis=1),
        "best_of": num(ms["BestOf"]).astype("Int64"),
        "team1_score": num(ms["Team1Score"]).astype("Int64"),
        "team2_score": num(ms["Team2Score"]).astype("Int64"),
        "date_utc": pd.to_datetime(ms["DateTime_UTC"].replace("", None), errors="coerce"),
    }).drop_duplicates("match_id", keep="first") if len(ms) else pd.DataFrame()

    # --- sanity checks
    per_game = player_games.groupby("game_id").size() if len(player_games) else pd.Series(dtype=int)
    games_without_10 = int((games.set_index("game_id").index.map(lambda g: per_game.get(g, 0)) != 10).sum())
    bad_winner = int((~games["winner_team"].isin(["team1", "team2"])).sum())
    dur_min = games["duration_sec"] / 60
    bad_duration = int(((dur_min < 15) | (dur_min > 70) | dur_min.isna()).sum())
    games_with_pb = int(games["game_id"].isin(set(picks_bans["game_id"])).sum()) if len(picks_bans) else 0
    team1_red_count = int((~pd.Series(team1_is_blue)).sum())

    counts = games.groupby("overview_page").size().rename("games")
    pg_counts = (player_games.groupby("overview_page").size().rename("player_rows")
                 if len(player_games) else pd.Series(dtype=int, name="player_rows"))
    per_tournament = tournaments.set_index("overview_page").join(counts).join(pg_counts).fillna({"games": 0, "player_rows": 0})

    # --- write DuckDB (rebuilt from scratch each run)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    for name, df in [("tournaments", tournaments), ("games", games), ("player_games", player_games),
                     ("picks_bans", picks_bans), ("series", series)]:
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    con.close()

    write_report(
        scope=scope, per_tournament=per_tournament, tournaments_all=tournaments_all,
        games=games, player_games=player_games, picks_bans=picks_bans,
        checks=dict(games_without_10=games_without_10, bad_winner=bad_winner, bad_duration=bad_duration,
                    games_with_pb=games_with_pb, team1_red=team1_red_count, side_unknown=side_unknown,
                    dup_games=dup_games, dup_pb=dup_pb, series=len(series)),
        fetch_failures=fetch_failures, network_calls=network_calls,
    )
    print(f"Built {DB_PATH.name}: {len(tournaments)} tournaments, {len(games)} games, "
          f"{len(player_games)} player rows, {len(picks_bans)} picks_bans, {len(series)} series.")


def write_report(scope, per_tournament, tournaments_all, games, player_games, picks_bans, checks,
                 fetch_failures, network_calls) -> None:
    lines = []
    add = lines.append
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    add("# Leaguepedia ingest report")
    add("")
    add(f"Generated {now} by `ingest/leaguepedia.py`. Network calls in this run: **{network_calls}** "
        "(0 means everything came from the cache).")
    add("")
    add("## Totals")
    add("")
    add(f"- Tournaments in scope: **{len(scope)}** (of {len(tournaments_all)} Tournaments rows for 2024-2026)")
    add(f"- Games: **{len(games)}**")
    add(f"- Player-game rows: **{len(player_games)}**")
    add(f"- Games with picks_bans: **{checks['games_with_pb']}** "
        f"({100 * checks['games_with_pb'] / max(len(games), 1):.1f}%)")
    add(f"- Series: **{checks['series']}**")
    add("")
    add("## Tournaments ingested")
    add("")
    add("| Overview page | League | Region | Year | Qualifier | Playoffs | Games | Player rows |")
    add("|---|---|---|---|---|---|---|---|")
    for page, r in per_tournament.sort_values(["year", "league", "date_start"]).iterrows():
        add(f"| {page} | {r['league']} | {r['region']} | {r['year']} | {'Y' if r['is_qualifier'] else ''} | "
            f"{'Y' if r['is_playoffs'] else ''} | {int(r['games'])} | {int(r['player_rows'])} |")
    add("")
    add("### Games by league and year")
    add("")
    by = games.groupby(["league", "year"]).size().rename("games").reset_index()
    add("| League | Year | Games |")
    add("|---|---|---|")
    for _, r in by.iterrows():
        add(f"| {r['league']} | {r['year']} | {r['games']} |")
    add("")
    add("## Sanity checks")
    add("")
    add(f"- Games whose player rows are not exactly 10: **{checks['games_without_10']}**")
    add(f"- Games where winner_team is not team1/team2: **{checks['bad_winner']}**")
    add(f"- Games with duration outside 15-70 min (or missing): **{checks['bad_duration']}**")
    add(f"- Games where Team1 is red side (Side field overrides the Leaguepedia convention): "
        f"**{checks['team1_red']}**; side could not be determined and fell back to Team1=blue: "
        f"**{checks['side_unknown']}**")
    add(f"- Duplicate GameIds dropped: **{checks['dup_games']}** (picks_bans duplicates: **{checks['dup_pb']}**)")
    add(f"- Games with missing patch: **{int(games['patch'].isna().sum())}**")
    add("")
    add("## Fetch failures and gaps")
    add("")
    if fetch_failures:
        for table, key, offset, msg in fetch_failures:
            add(f"- {table} / {key} (offset {offset}): {msg}")
    else:
        add("- No fetch failures recorded in this run.")
    add("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover", action="store_true", help="Fetch Tournaments only and list leagues")
    args = parser.parse_args()

    fetcher = Fetcher()
    try:
        tournaments_all = fetch_tournaments(fetcher)
        if args.discover:
            from collections import Counter
            c = Counter((t["Year"], t["League"]) for t in tournaments_all if t["Year"] in YEARS)
            for (year, league), n in sorted(c.items()):
                print(f"{year}\t{league}\t{n}")
            return 0
        fetch_games(fetcher, [t for t in tournaments_all if in_scope(t)])
    except GiveUp as e:
        print(f"GIVING UP: {e}. Cached data kept; rerun later.", file=sys.stderr)
        fetcher.failures.append(("*", "*", 0, f"Gave up after backoff: {e}"))
        return 2
    except Exception:
        traceback.print_exc()
        return 1

    build(tournaments_all, fetcher.failures, fetcher.network_calls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
