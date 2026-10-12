"""Downloads team logos (Wikidata / Wikimedia Commons) and champion icons (Riot Data Dragon) for the charts.

Everything lands in data/raw/ (git-ignored):
    data/raw/logos/<team_id>.png        team logo, from the logo property (P154) of the team's Wikidata item
    data/raw/ddragon/champion.json      champion name -> icon id
    data/raw/ddragon/icons/<id>.png     champion square icons

Wikimedia rate-limits by HTTP 429. Requests back off and retry, and a run can be restarted: files that
already exist are skipped.

    python -m ingest.assets
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common.paths import ROOT

RAW = ROOT / "data" / "raw"
LOGO_DIR = RAW / "logos"
DD_DIR = RAW / "ddragon"
ICON_DIR = DD_DIR / "icons"
UA = "Mozilla/5.0 (personal analytics project; contact via repo owner)"

# team_id -> name used to find the team's Wikidata item
WIKIDATA_NAMES = {
    "GEN": "Gen.G", "HLE": "Hanwha Life Esports", "T1": "T1", "DK": "Dplus KIA", "AL": "Anyone's Legend",
    "BLG": "Bilibili Gaming", "TES": "Top Esports", "IG": "Invictus Gaming", "G2": "G2 Esports",
    "MKOI": "Movistar KOI", "KC": "Karmine Corp", "TL": "Team Liquid", "LYON": "LYON", "C9": "Cloud9",
    "TSW": "Team SecretWhales", "CFO": "CTBC Flying Oyster", "MVK": "MVK Esports", "LOS": "LØS",
    "FUR": "FURIA",
}
ESPORTS_HINT = re.compile(r"esport|gaming|team|organi[sz]ation", re.I)


def get(url: str, retries: int = 6) -> bytes:
    """GET with back-off on HTTP 429 (honours Retry-After when present)."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 60 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"still rate-limited after {retries} tries: {url}")


def wikidata_logo(name: str) -> tuple[str, str, str] | None:
    """(item id, description, Commons file name) for the first esports-looking Wikidata item with a logo."""
    q = urllib.parse.quote(name)
    hits = json.loads(get(f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={q}"
                          "&language=en&format=json&limit=5"))["search"]
    for hit in hits:
        desc = hit.get("description", "")
        if not ESPORTS_HINT.search(desc):
            continue
        ents = json.loads(get(f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={hit['id']}"
                              "&props=claims&format=json"))
        for claim in ents["entities"][hit["id"]]["claims"].get("P154", []):
            value = claim["mainsnak"].get("datavalue")
            if value:
                return hit["id"], desc, value["value"]
    return None


def download_logos() -> list[str]:
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for team, name in WIKIDATA_NAMES.items():
        out = LOGO_DIR / f"{team}.png"
        if out.exists():
            continue
        found = wikidata_logo(name)
        if not found:
            print(f"logo {team:5s} no logo found for {name!r}")
            failed.append(team)
            continue
        qid, desc, filename = found
        url = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
               + urllib.parse.quote(filename.replace(" ", "_")) + "?width=600")
        out.write_bytes(get(url))
        print(f"logo {team:5s} <- {name} ({qid}: {desc}) {filename}")
        time.sleep(5)              # keep well under the Wikimedia rate limit
    return failed


def download_icons() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    versions = json.loads(get("https://ddragon.leagueoflegends.com/api/versions.json"))
    ver = versions[0]
    champs = json.loads(get(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json").decode("utf-8"))["data"]
    (DD_DIR / "champion.json").write_text(json.dumps(champs, ensure_ascii=False), encoding="utf-8")
    for c in champs.values():
        out = ICON_DIR / f"{c['id']}.png"
        if not out.exists():
            out.write_bytes(get(f"https://ddragon.leagueoflegends.com/cdn/{ver}/img/champion/{c['id']}.png"))
    print(f"icons: {len(champs)} champions, patch {ver}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    download_icons()
    failed = download_logos()
    if failed:
        print("missing logos:", ", ".join(failed))


if __name__ == "__main__":
    main()
