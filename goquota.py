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
