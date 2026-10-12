"""Build data/pickems.duckdb from Oracle's Elixir yearly CSVs in data/raw/oe/.

Run from the project root:  python ingest/oracles.py
Idempotent: drops and rebuilds all tables from the CSVs.
"""

import duckdb
import pandas as pd

from common.paths import DB_PATH as DB, ROOT

RAW = ROOT / "data" / "raw" / "oe"

INTERNATIONAL = {"WLDs", "MSI", "FST", "EWC"}
# OE also tags regional Worlds qualifiers (e.g. LPL/LCK last-chance series) as WLDs;
# only games from the actual Play-In start onward are international.
WORLDS_START = {2022: "2022-09-29", 2023: "2023-10-09", 2024: "2024-09-25", 2025: "2025-10-14", 2026: "2026-10-15"}
# Same for EWC: 2026 includes regional online qualifiers from April-June.
EWC_START = {2024: "2024-07-01", 2025: "2025-07-01", 2026: "2026-07-01"}
ROLE = {"top": "Top", "jng": "Jungle", "mid": "Mid", "bot": "Bot", "sup": "Support"}


def load_csvs() -> pd.DataFrame:
    frames = []
    for f in sorted(RAW.glob("*_LoL_esports_match_data_from_OraclesElixir.csv")):
        # patch as string: 16.20 must not collapse to 16.2
        df = pd.read_csv(f, low_memory=False, dtype={"patch": str, "gameid": str, "playerid": str, "teamid": str})
        frames.append(df)
        print(f"loaded {f.name}: {len(df)} rows")
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df["patch"] = df["patch"].map(normalize_patch)
    return df


def normalize_patch(p) -> str | None:
    """'16.2' read from a float-formatted CSV is ambiguous; OE writes patches as 16.01..16.24,
    so a one-digit minor means a trailing zero was dropped (16.2 -> 16.20)."""
    if not isinstance(p, str) or "." not in p:
        return None
    major, minor = p.split(".", 1)
    if len(minor) == 1:
        minor += "0"
    return f"{major}.{minor}"


def build_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    teams = df[df["position"] == "team"].copy()
    players = df[df["position"] != "team"].copy()

    blue = teams[teams["side"] == "Blue"].set_index("gameid")
    red = teams[teams["side"] == "Red"].set_index("gameid")
    common = blue.index.intersection(red.index)
    blue, red = blue.loc[common], red.loc[common]

    picks = lambda t: t[[f"pick{i}" for i in range(1, 6)]].fillna("").astype(str).agg(",".join, axis=1)
    bans = lambda t: t[[f"ban{i}" for i in range(1, 6)]].fillna("").astype(str).agg(",".join, axis=1)

    games = pd.DataFrame({
        "game_id": common,
        "league": blue["league"],
        "year": blue["year"],
        "split": blue["split"],
        "playoffs": blue["playoffs"].astype(bool),
        "date_utc": blue["date"],
        "patch": blue["patch"],
        "game_in_series": blue["game"],
        "blue_team": blue["teamname"],
        "red_team": red["teamname"],
        "blue_team_id": blue["teamid"],
        "red_team_id": red["teamid"],
        "winner_team": blue["teamname"].where(blue["result"] == 1, red["teamname"]),
        "blue_win": blue["result"] == 1,
        "duration_sec": blue["gamelength"],
        "blue_kills": blue["teamkills"],
        "red_kills": red["teamkills"],
        "blue_golddiff15": blue["golddiffat15"],
        "blue_picks": picks(blue),
        "red_picks": picks(red),
        "blue_bans": bans(blue),
        "red_bans": bans(red),
        "first_pick_blue": blue["firstPick"] == 1,
        "data_complete": blue["datacompleteness"] == "complete",
    }).reset_index(drop=True)
    worlds_start = pd.to_datetime(games["year"].map(WORLDS_START))
    is_worlds_qualifier = (games["league"] == "WLDs") & (games["date_utc"] < worlds_start)
    games.loc[is_worlds_qualifier, "league"] = "WLDQ"
    ewc_start = pd.to_datetime(games["year"].map(EWC_START))
    games.loc[(games["league"] == "EWC") & (games["date_utc"] < ewc_start), "league"] = "EWCQ"
    games["is_international"] = games["league"].isin(INTERNATIONAL)

    player_games = pd.DataFrame({
        "game_id": players["gameid"],
        "league": players["league"],
        "date_utc": players["date"],
        "patch": players["patch"],
        "player": players["playername"],
        "player_id": players["playerid"],
        "team": players["teamname"],
        "team_id": players["teamid"],
        "role": players["position"].map(ROLE),
        "side": players["side"],
        "champion": players["champion"],
        "win": players["result"] == 1,
        "kills": players["kills"],
        "deaths": players["deaths"],
        "assists": players["assists"],
        "team_kills": players["teamkills"],
        "cs": players["total cs"],
        "damage": players["damagetochampions"],
        "dpm": players["dpm"],
        "gold": players["totalgold"],
        "golddiff15": players["golddiffat15"],
        "vision": players["visionscore"],
        "pentakills": players["pentakills"],
        "duration_sec": players["gamelength"],
    }).reset_index(drop=True)
    player_games["league"] = player_games["game_id"].map(games.set_index("game_id")["league"])

    return {"games": games, "player_games": player_games}


def checks(t: dict[str, pd.DataFrame]) -> list[str]:
    g, p = t["games"], t["player_games"]
    out = [f"games: {len(g)}, player_games: {len(p)}"]
    per_game = p.groupby("game_id").size()
    out.append(f"games without exactly 10 player rows: {(per_game != 10).sum()}")
    out.append(f"games with duration outside 15-70 min: {((g.duration_sec < 900) | (g.duration_sec > 4200)).sum()}")
    out.append(f"games missing patch: {g.patch.isna().sum()}")
    return out


def main():
    df = load_csvs()
    tables = build_tables(df)
    con = duckdb.connect(str(DB))
    for name, frame in tables.items():
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.register("tmp", frame)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.close()
    for line in checks(tables):
        print(line)


if __name__ == "__main__":
    main()
