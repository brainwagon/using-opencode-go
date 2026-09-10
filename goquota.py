"""Shared helpers for querying opencode Go quota.

The API reports percentages only; the dollar caps below come from the published
plan documentation and must be updated by hand if opencode changes the plan.
"""
import json, urllib.request, datetime, os

# opencode stores its data under XDG_DATA_HOME; both paths take an env override
_DATA_HOME = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
AUTH = os.environ.get("GO_AUTH") or os.path.join(_DATA_HOME, "opencode", "auth.json")
ENDPOINT = os.environ.get("GO_ENDPOINT", "https://opencode.ai/zen/go/v1/usage")

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


def format_when(dt, now=None):
    """Local timestamp, carrying the year only when it is not the current one."""
    import datetime as _dt
    now = now or _dt.datetime.now(_dt.timezone.utc)
    local = dt.astimezone()
    fmt = "%d %b %H:%M %Z" if local.year == now.astimezone().year else "%d %b %Y %H:%M %Z"
    return local.strftime(fmt)


def format_hours(hours):
    """Render a duration: hours under a day, days and hours beyond that."""
    if hours < 0:
        return "overdue"
    if hours < 24:
        return f"{hours:.1f}h"
    # round to whole hours first, so 47.6h reads "2d 0h" and never "1d 24h"
    whole = round(hours)
    days, rem = divmod(whole, 24)
    return f"{days}d {rem}h"


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


DB = os.environ.get("GO_DB") or os.path.join(_DATA_HOME, "opencode", "opencode.db")
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


def all_models(since):
    """Every model used since `since`, across all providers, zero-cost included.

    Same local-data caveats as model_breakdown: this machine only, priced
    locally, so costs are estimates rather than the provider's bill.
    """
    import sqlite3, json as _json
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    try:
        rows = con.execute(
            "SELECT data FROM message WHERE time_created >= ? AND data LIKE '%\"cost\"%'",
            (int(since.timestamp() * 1000),)).fetchall()
    finally:
        con.close()

    agg = {}
    for (blob,) in rows:
        try:
            d = _json.loads(blob)
        except ValueError:
            continue
        model, provider = d.get("modelID"), d.get("providerID")
        if not model or d.get("cost") is None:
            continue
        t = d.get("tokens") or {}
        cache = t.get("cache") or {}
        e = agg.setdefault((provider, model), {
            "provider": provider, "model": model, "name": f"{provider}/{model}",
            "messages": 0, "cost": 0.0, "input": 0, "output": 0, "cache_read": 0})
        e["messages"] += 1
        e["cost"] += d["cost"]
        e["input"] += t.get("input") or 0
        e["output"] += t.get("output") or 0
        e["cache_read"] += cache.get("read") or 0
    return sorted(agg.values(), key=lambda r: (-r["cost"], -r["messages"]))


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


REGISTRY = os.environ.get("GO_REGISTRY", "https://models.dev/api.json")
_CACHE_HOME = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
REGISTRY_CACHE = os.environ.get("GO_REGISTRY_CACHE",
                                os.path.join(_CACHE_HOME, "go-usage-registry.json"))
REGISTRY_TTL = 24 * 3600


def pricing_catalog():
    """Map model id -> cost block ($/M tokens) from the models.dev registry.

    The Go /models endpoint lists availability but carries no pricing, and the
    published plan table is not machine readable, so pricing comes from the
    registry opencode itself uses. Cached for a day: the payload is ~4.5MB.
    """
    import time
    raw = None
    try:
        if time.time() - os.path.getmtime(REGISTRY_CACHE) < REGISTRY_TTL:
            raw = json.load(open(REGISTRY_CACHE))
    except (OSError, ValueError):
        raw = None
    if raw is None:
        req = urllib.request.Request(REGISTRY, headers={"User-Agent": "go-usage/1.0"})
        raw = json.load(urllib.request.urlopen(req, timeout=60))
        try:
            os.makedirs(os.path.dirname(REGISTRY_CACHE), exist_ok=True)
            json.dump(raw, open(REGISTRY_CACHE, "w"))
        except OSError:
            pass  # a working cache is nice, not required

    # prefer opencode's own entry for a model, fall back to any provider carrying it
    out = {}
    for pid, prov in raw.items():
        for mid, m in (prov.get("models") or {}).items():
            cost = m.get("cost")
            if not cost:
                continue
            if mid not in out or pid == "opencode":
                out[mid] = {"cost": cost, "provider": pid,
                            "name": m.get("name") or mid,
                            "context": (m.get("limit") or {}).get("context")}
    return out


def average_shape(since):
    """Mean tokens per assistant message from local history: the shape of *your*
    requests, used to price models against how you actually use them."""
    import sqlite3
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    try:
        rows = con.execute(
            "SELECT data FROM message WHERE time_created >= ? AND data LIKE '%\"cost\"%'",
            (int(since.timestamp() * 1000),)).fetchall()
    finally:
        con.close()
    n = 0
    tot = {"input": 0, "output": 0, "cache_read": 0}
    for (blob,) in rows:
        try:
            d = json.loads(blob)
        except ValueError:
            continue
        if not d.get("modelID"):
            continue
        t = d.get("tokens") or {}
        n += 1
        tot["input"] += t.get("input") or 0
        tot["output"] += t.get("output") or 0
        tot["cache_read"] += (t.get("cache") or {}).get("read") or 0
    if not n:
        return None
    return {k: v / n for k, v in tot.items()} | {"messages": n}


def cost_per_message(cost, shape):
    """Estimated $ for one message of `shape` at `cost` ($ per million tokens)."""
    read = cost.get("cache_read", cost.get("input", 0))
    return (shape["input"] * cost.get("input", 0)
            + shape["output"] * cost.get("output", 0)
            + shape["cache_read"] * read) / 1_000_000
