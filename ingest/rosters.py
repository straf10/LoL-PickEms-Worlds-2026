"""T1.3: Worlds 2026 rosters, aliases and Swiss seeding inputs from Leaguepedia (lol.fandom.com).

Every successful API response is cached as JSON under data/raw/leaguepedia/rosters/ and reused on
reruns. Requests are throttled to one every 2 s. Rate-limit and transient server errors are retried
with exponential backoff; other API errors are raised immediately (not cached).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "raw" / "leaguepedia" / "rosters"
API = "https://lol.fandom.com/api.php"
UA = "LOL_PICKEMS research script"
MIN_INTERVAL = 2.0
RETRY_CODES = {"ratelimited", "maxlag", "internal_api_error_DBQueryError", "readonly"}
MAX_TRIES = 12
_last_request = 0.0
_session = requests.Session()
_session.headers["User-Agent"] = UA


class APIError(RuntimeError):
    pass


def _cache_path(params: dict) -> Path:
    key = hashlib.sha1(json.dumps(sorted(params.items())).encode()).hexdigest()[:12]
    name = (params.get("tables") or params.get("action", "api")).replace("/", "_")
    return CACHE_DIR / f"{name}_{key}.json"


def api(params: dict) -> dict:
    """GET the API with caching, throttling and backoff. Returns the decoded JSON payload."""
    global _last_request
    path = _cache_path(params)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]

    delay = 20.0
    for attempt in range(1, MAX_TRIES + 1):
        wait = MIN_INTERVAL - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()
        try:
            resp = _session.get(API, params=params, timeout=60)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            data = {"error": {"code": "transport", "info": str(exc)[:200]}}
        if "error" in data:
            code = data["error"].get("code", "")
            if code in RETRY_CODES or code == "transport" or resp.status_code in (429, 503):
                print(f"[leaguepedia] try {attempt}: {code}; sleeping {delay:.0f}s", flush=True)
                time.sleep(delay)
                delay = min(delay * 2, 300)
                continue
            raise APIError(f"{code}: {data['error'].get('info', '')}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"params": params, "response": data}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return data
    raise APIError(f"gave up after {MAX_TRIES} tries: {params.get('tables') or params.get('action')}")


def cargo(tables: str, fields: str, where: str = "", join: str = "", limit: int = 500,
          group_by: str = "", order_by: str = "") -> list[dict]:
    """Run a cargoquery and return its row dicts (the 'title' payloads), paging to completion."""
    out: list[dict] = []
    offset = 0
    while True:
        params = {"action": "cargoquery", "format": "json", "tables": tables, "fields": fields,
                  "limit": limit, "offset": offset}
        for k, v in (("where", where), ("join_on", join), ("group_by", group_by), ("order_by", order_by)):
            if v:
                params[k] = v
        page = api(params).get("cargoquery", [])
        out.extend(r["title"] for r in page)
        if len(page) < limit:
            return out
        offset += limit


if __name__ == "__main__":
    # Step 1 probe: the Worlds 2026 tournament page(s).
    rows = cargo("Tournaments", "Name,OverviewPage,Region,Date_Start,Date_End,Prizepool,Teams",
                 where='OverviewPage LIKE "Worlds/2026%"', limit=50)
    print(json.dumps(rows, indent=1, ensure_ascii=False))
    sys.stdout.flush()
