"""Shared helpers for querying opencode Go quota.

The API reports percentages only; the dollar caps below come from the published
plan documentation and must be updated by hand if opencode changes the plan.
"""
import json, urllib.request, datetime, os

AUTH = os.path.expanduser("~/.local/share/opencode/auth.json")
ENDPOINT = "https://opencode.ai/zen/go/v1/usage"

# window key -> (label, dollar cap, window length in days)
WINDOWS = {
    "rolling": ("5-hour", 12.0, 5 / 24),
    "weekly":  ("weekly", 30.0, 7.0),
    "monthly": ("monthly", 60.0, 30.0),
}


def fetch():
    """Return the usage dict from the API. Raises on network/auth failure."""
    key = json.load(open(AUTH))["opencode-go"]["key"]
    req = urllib.request.Request(ENDPOINT, headers={
        "Authorization": "Bearer " + key,
        # Cloudflare 403s urllib's default agent
        "User-Agent": "go-usage/1.0",
    })
    return json.load(urllib.request.urlopen(req, timeout=20))["usage"]


def window_state(usage, key, now=None):
    """Return (pct, dollars_used, dollars_left, reset_dt, hours_left, elapsed_pct)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    _label, cap, days = WINDOWS[key]
    d = usage[key]
    pct = d["percent"]
    reset = datetime.datetime.fromisoformat(d["resetsAt"].replace("Z", "+00:00"))
    hours_left = (reset - now).total_seconds() / 3600
    elapsed_pct = 100 * (1 - hours_left / (days * 24))
    return pct, cap * pct / 100, cap * (100 - pct) / 100, reset, hours_left, elapsed_pct


DB = os.path.expanduser("~/.local/share/opencode/opencode.db")
PROVIDER = "opencode-go"


def models_available():
    """Set of model ids the Go plan serves, for spotting substitutable spend."""
    key = json.load(open(AUTH))["opencode-go"]["key"]
    req = urllib.request.Request(ENDPOINT.replace("/usage", "/models"), headers={
        "Authorization": "Bearer " + key,
        "User-Agent": "go-usage/1.0",
    })
    return {m["id"] for m in json.load(urllib.request.urlopen(req, timeout=20))["data"]}


def window_start(usage, key="monthly", now=None):
    """Approximate the start of a window from its reset time and nominal length."""
    import datetime as _dt
    _label, _cap, days = WINDOWS[key]
    reset = _dt.datetime.fromisoformat(usage[key]["resetsAt"].replace("Z", "+00:00"))
    return reset - _dt.timedelta(days=days)


def model_breakdown(since):
    """Per-model local usage since `since` (a tz-aware datetime).

    Reads opencode's own database, so this reflects only sessions run on this
    machine and prices computed locally -- see the README on reconciling with
    the server's figure. Returns (go_rows, other_rows), each a list of dicts
    sorted by cost descending. Zero-cost providers (local ollama models) are
    left out of other_rows, since they cost nothing to begin with.
    """
    import sqlite3, json as _json
    since_ms = int(since.timestamp() * 1000)
    # read-only, so a running opencode is never disturbed
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    try:
        rows = con.execute(
            "SELECT data FROM message WHERE time_created >= ? AND data LIKE '%\"cost\"%'",
            (since_ms,)).fetchall()
    finally:
        con.close()

    agg, others = {}, {}
    for (blob,) in rows:
        try:
            d = _json.loads(blob)
        except ValueError:
            continue
        cost = d.get("cost")
        model, provider = d.get("modelID"), d.get("providerID")
        if cost is None or not model:
            continue
        if provider != PROVIDER:
            if cost:
                o = others.setdefault(f"{provider}/{model}",
                                      {"model": model, "provider": provider,
                                       "name": f"{provider}/{model}",
                                       "messages": 0, "cost": 0.0})
                o["messages"] += 1
                o["cost"] += cost
            continue
        t = d.get("tokens") or {}
        cache = t.get("cache") or {}
        e = agg.setdefault(model, {"model": model, "messages": 0, "cost": 0.0,
                                   "input": 0, "output": 0, "cache_read": 0})
        e["messages"] += 1
        e["cost"] += cost
        e["input"] += t.get("input") or 0
        e["output"] += t.get("output") or 0
        e["cache_read"] += cache.get("read") or 0
    key = lambda r: r["cost"]
    return (sorted(agg.values(), key=key, reverse=True),
            sorted(others.values(), key=key, reverse=True))
