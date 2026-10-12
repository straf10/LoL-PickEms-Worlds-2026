"""Cached, throttled Leaguepedia Cargo fetcher (T1.4). Internal helper for base_rates.py."""
import hashlib
import json
import re
import time
from pathlib import Path

import mwclient

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "raw" / "leaguepedia" / "worlds_hist"
PAGE = 500
MIN_GAP_S = 2.0
BACKOFF_S = (10, 30, 90)
_last_call = [0.0]
ALLOW_NETWORK = [False]  # off by default: reruns use the cache only (set via base_rates.py --fetch)


class MissingCache(RuntimeError):
    """Raised when a page is not cached and network access is disabled."""
_site = [None]


def _get_site():
    if _site[0] is None:
        _site[0] = mwclient.Site(
            "lol.fandom.com", path="/", clients_useragent="LOL_PICKEMS research script",
            connection_options={"timeout": 60}
        )
    return _site[0]


def _slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:60]


def cargo(name, tables, fields, where, join=None, order_by=None, group_by=None):
    """Return all rows of a Cargo query as a list of dicts (the 'title' payloads).

    Each page is cached as raw JSON under CACHE_DIR; cached pages are reused without
    touching the network. Paging stops when a page returns fewer than PAGE rows.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    params = dict(tables=tables, fields=fields, where=where, join_on=join,
                  order_by=order_by, group_by=group_by)
    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]
    rows, offset = [], 0
    while True:
        path = CACHE_DIR / f"{_slug(name)}__{key}__off{offset}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            if not ALLOW_NETWORK[0]:
                raise MissingCache(f"{name} page {offset} not cached")
            kw = dict(tables=tables, fields=fields, where=where, limit=PAGE, offset=offset)
            if join:
                kw["join_on"] = join
            if order_by:
                kw["order_by"] = order_by
            if group_by:
                kw["group_by"] = group_by
            payload = _live_call(kw)
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        page = [r["title"] for r in payload.get("cargoquery", [])]
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def live_api(**kw):
    """Throttled raw API call (for non-Cargo actions such as parse). Caller caches the result."""
    if not ALLOW_NETWORK[0]:
        raise MissingCache(f"{kw.get('action')} request not cached and network is disabled")
    return _live_call(kw, action=kw.pop("action", None) or "cargoquery")


def _live_call(kw, action="cargoquery"):
    site = _get_site()
    attempts = [None] + list(BACKOFF_S)
    last_err = None
    for i, wait in enumerate(attempts):
        if wait is not None:
            print(f"  backing off {wait}s after error: {last_err}", flush=True)
            time.sleep(wait)
        gap = MIN_GAP_S - (time.time() - _last_call[0])
        if gap > 0:
            time.sleep(gap)
        _last_call[0] = time.time()
        try:
            return site.api(action, **kw)
        except Exception as e:  # mwclient raises APIError / HTTP errors
            last_err = repr(e)[:300]
            if "Unknown" in last_err or "syntax" in last_err.lower():
                raise
    raise RuntimeError(f"Leaguepedia request failed after retries: {last_err}")
