# Getting the most out of an opencode Go subscription

Notes and tooling for the $10/month [opencode Go](https://opencode.ai/v2/docs/console/go)
plan. Written 2026-09-10.

## How the plan meters you

Go costs $10/month ($5 the first month). It is metered in **dollars of model usage** —
not tokens, not requests. There are three nested caps:

| Window         | Cap  | Resets                 |
| -------------- | ---- | ---------------------- |
| 5-hour rolling | $12  | rolling                |
| Weekly         | $30  | Sundays                |
| Monthly        | $60  | monthly anniversary    |

The advertised deal is "pay $10, we aim to give you 6x that in usage", so **$60/month is
the prize and the only cap that really binds**:

- Weekly: $30 x ~4.3 weeks = ~$129/month of theoretical headroom
- 5-hour: $12 x ~34 windows/week = ~$408/week of theoretical headroom

Both are far above the monthly cap. They exist to stop bursts, not to limit your total.
Spending the full $60 needs only ~$2/day, or ~$14 of the $30 weekly allowance.

Unused budget **does not roll over**. Anything left at reset is gone.

## Checking your balance

The console at <https://console.opencode.ai> shows usage. There is also an undocumented
JSON endpoint, which is what `go-usage` calls:

```
GET https://opencode.ai/zen/go/v1/usage
Authorization: Bearer <your opencode-go key>
```

```json
{"usage":{
  "rolling":{"status":"ok","percent":5,"resetsAt":"2026-09-10T22:28:25.778Z"},
  "weekly": {"status":"ok","percent":2,"resetsAt":"2026-09-14T00:00:00.778Z"},
  "monthly":{"status":"ok","percent":7,"resetsAt":"2026-09-30T23:29:32.778Z"}}}
```

It returns **percentages only** — the dollar figures everywhere below are that percentage
applied to the published caps, and the percentages look rounded to whole numbers, so
treat "7%" as roughly $3.90-$4.50 rather than exactly $4.20.

## Strategies

### 1. Stop reaching for flash models by reflex

The single biggest win. Because the plan meters *dollars*, cheap models buy you nothing —
unspent budget just evaporates at reset. At $2.77/day you can afford roughly:

| Model            | Cost/message (observed or est.) | Messages/day |
| ---------------- | ------------------------------ | ------------ |
| `glm-5.3-flash`  | ~$0.0022                       | ~1,250       |
| `glm-5.2`        | ~$0.0022                       | ~1,250       |
| `kimi-k3`        | ~$0.05                         | ~55          |

Route real work to `grok-4.5`, `kimi-k3`, `glm-5.2`, or `qwen3.8-max`. Keep the flash
tier for genuinely trivial calls.

### 2. Exploit cache pricing

Cached reads cost 10-50x less than fresh input (DeepSeek V4 Flash: $0.0028/M cached vs
$0.14/M input). Long-lived sessions with a stable prompt prefix are dramatically cheaper
than constantly starting fresh ones. Check your ratio with `opencode stats` — cache-read
tokens should dominate input tokens by an order of magnitude.

### 3. Burst deliberately

$12 per 5-hour window is a lot of room for parallel agents or a large refactor —
sustaining it takes ~$2.40/hr. Don't pace yourself against this cap; it is almost
certainly not your constraint.

### 4. Leave "Use balance" off

That console setting falls back to pay-as-you-go from your account balance when you hit a
limit instead of blocking. Turn it on only once you are routinely *hitting* the monthly
cap; while you are under it, it can only cost you money you didn't need to spend.

### 5. Shift substitutable spend off other providers

Work sent to a metered provider (OpenRouter and friends) while prepaid Go budget sits idle
is money spent twice. Prefer Go for anything with a comparable model on the plan, until
the monthly cap is the thing stopping you.

Check the size of this before acting on it, though — `go-usage --models` itemizes it. On
this machine it turned out to be worth almost nothing: of $0.88 spent off-plan in a
window, all but half a cent went to `gpt-5.6-sol`, which Go does not serve at all. Spend
on a model with no Go equivalent is not waste, and local `ollama` models cost nothing to
begin with. This strategy only pays where the *same* model is available on both.

### 6. Watch pace, not totals

A raw "used $4.20" figure means nothing without knowing how far through the window you
are. `go-usage` prints a pace multiplier for this: 1.0x means you are exactly on track to
use the full cap, below 1.0x means you are leaving money unspent.

## `go-usage`

Prints remaining quota for all three windows, with reset times in local time, a burn-rate
multiplier, and the daily budget needed to finish the month at 100%.

### Usage

```
./go-usage             # quota summary for all three windows
./go-usage --models    # also break the current billing month down by model
```

No dependencies beyond the Python 3 standard library.

```
opencode Go usage @ 2026-09-10 12:19 PDT

 5-hour: $  0.60 used / $12.00  -> $ 11.40 left  (5%, 0.14x pace)
         resets Thu 10 Sep 15:28 PDT (in 3.2h)  status=ok

 weekly: $  0.60 used / $30.00  -> $ 29.40 left  (2%, 0.04x pace)
         resets Sun 13 Sep 17:00 PDT (in 76.7h)  status=ok

monthly: $  4.20 used / $60.00  -> $ 55.80 left  (7%, 0.21x pace)
         resets Wed 30 Sep 16:29 PDT (in 484.2h)  status=ok
         budget to fully use: $2.77/day for the remaining 20.2 days
```

### Per-model breakdown

`--models` adds a table of where this billing month's money actually went:

```
Per-model usage this billing month (local data since 31 Aug 16:29 PDT)

  model                            msgs      cost    $/msg  share  cached
  glm-5.3-flash                     414    0.9033   0.0022    55%     96%
  qwen3.8-flash                     192    0.3010   0.0016    18%    100%
  deepseek-v4-flash-vision-exp      279    0.2266   0.0008    14%     96%
  kimi-k3                             3    0.1458   0.0486     9%     38%
  gpt-5.6-luna                       30    0.0551   0.0018     3%    100%
                                 ------ ---------
  local total                       918    1.6318
  server reports                             4.20   (local accounts for 39%)

Paid spend outside the Go plan, same window: $0.88
(billed to those accounts, separately from the Go subscription)

  openrouter/openai/gpt-5.6-sol                    31 msg    0.7920  no Go equivalent
  openrouter/deepseek/deepseek-v4-flash-0731       60 msg    0.0854  no Go equivalent
  openrouter/deepseek/deepseek-v4-flash-vision-exp    2 msg    0.0038  same model on Go

  $0.0038 of that used a model Go already serves, so it could have come
  out of the $55.80 of Go budget that expires unused instead.
```

- **$/msg** is the lever for strategy 1 above. The spread here is ~60x between
  `deepseek-v4-flash-vision-exp` and `kimi-k3`; at $2.77/day of unused budget, that gap is
  the whole argument for routing real work to the expensive models.
- **cached** is cache-read tokens as a share of all input tokens seen, so it measures
  strategy 2 directly. High is good. `kimi-k3` at 38% across only 3 messages is what a
  cold start looks like.
- **share** is share of the *local* total, not of the cap.

**The "paid spend outside the Go plan" section** answers a specific question: how much
real money left your pocket during a window in which prepaid Go budget expired unused.
OpenRouter and friends bill per token against their own balances, so that spend is
genuinely additional to the $10 subscription. Local `ollama` models are excluded — they
run on your own hardware and cost nothing, so they are not competing with Go budget.

Each row is marked by whether Go serves the same model, because only those could actually
have been moved. The match is on the bare model id after stripping any vendor prefix
(`openrouter/deepseek/deepseek-v4-flash-vision-exp` matches Go's
`deepseek-v4-flash-vision-exp`), and it is exact: a dated snapshot like
`deepseek-v4-flash-0731` reads as "no Go equivalent" even though Go serves the
undated `deepseek-v4-flash`, so treat that marking as conservative. A model with no Go
equivalent at all — `gpt-5.6-sol` here — is not waste; there is simply nothing on the plan
to switch it to.

**This table comes from local data and will understate the server.** The usage API reports
only three aggregate percentages — there is no per-model endpoint (`usage/models`,
`usage/breakdown` and friends all 404, and query parameters are ignored), so the breakdown
is computed from opencode's own SQLite database at
`~/.local/share/opencode/opencode.db`, read-only. The `server reports` line makes the gap
explicit rather than hiding it: on this machine local data accounts for only ~39% of what
opencode actually billed. See the reconciliation section at the end for why.

The window is derived by subtracting the nominal window length from the monthly reset
time, so it is approximate at the boundary in the same way the pace math is.

### Reading the output

- **used / left** — the reported percentage applied to the published cap.
- **pace** — spend as a fraction of window elapsed. `1.00x` is exactly on track to consume
  the cap; `0.21x` means you are on course to use about a fifth of it.
- **status** — passed through from the API (`ok`, or presumably a warning state near the
  cap).
- **budget to fully use** — monthly only: the daily spend that would land you at exactly
  100% on reset day.

### Configuration

Both scripts share `goquota.py`, which holds the constants in one place:

- `AUTH` — path to opencode's credential file, default
  `~/.local/share/opencode/auth.json`. The `opencode-go` key is read from it at runtime; no
  key is stored in this repo.
- `ENDPOINT` — the usage URL.
- `DB` — opencode's SQLite database, source of the `--models` breakdown.
- `PROVIDER` — the provider id counted against the Go plan (`opencode-go`); spend under
  any other provider is reported separately as billed elsewhere.
- `WINDOWS` — maps each window to its label, dollar cap, and length in days. **Update the
  caps here if opencode changes the plan**, since the API reports only percentages and
  cannot tell you the caps moved.

### Known limitations

- The dollar amounts are derived, not authoritative — see "Checking your balance" above.
- `WINDOW_DAYS["monthly"]` assumes a flat 30 days, so pace is slightly off in 28- and
  31-day months. The "used / left" figures are unaffected.
- The 5-hour window is *rolling*, so its pace number is a rough indication only; the math
  treats it as a fixed window.
- The endpoint is undocumented and may change or disappear without notice.
- A `User-Agent` header is required. Cloudflare returns `403 Forbidden` for Python's
  default urllib agent.

## Alerting from cron (WSL2)

`go-alert` checks your monthly pace and raises a **Windows notification** when you are
underspending. It is meant to be run from cron.

```
./go-alert
```

It prints nothing and exits 0 when there is nothing to say, so cron stays quiet. When it
does fire you get a notification reading:

```
opencode Go underused
0.21x pace - $55.80 unused with 20.2 days left. Spend $2.77/day to use it all.
```

### Tuning

Configured entirely by environment variable, so the cron line is the only thing to edit:

| Variable              | Default | Meaning                                              |
| --------------------- | ------- | ---------------------------------------------------- |
| `GO_PACE_TARGET`      | `0.6`   | Alert when pace drops below this multiplier           |
| `GO_MIN_ELAPSED`      | `20`    | Stay silent until this % of the month has elapsed     |
| `GO_ALERT_INTERVAL_H` | `24`    | Minimum hours between notifications                   |
| `GO_NOTIFY`           | `msgbox`| Notification backend: `msgbox` or `balloon`           |

`GO_MIN_ELAPSED` exists because pace is meaningless in the first hours after a reset — a
single day of light use looks like a catastrophic shortfall. `GO_ALERT_INTERVAL_H` is
enforced with a stamp in `~/.cache/go-alert.json`, so you can run the job hourly and still
be told at most once a day. Delete that file to re-arm immediately.

### Installing the cron job

```
crontab -e
```

```cron
# Check opencode Go pace every weekday at 09:00 and 17:00
0 9,17 * * 1-5 /home/markv/using-opencode-go/go-alert
```

Absolute path is required: cron runs with `PATH=/usr/bin:/bin`, which contains neither the
script nor `powershell.exe`. `go-alert` hardcodes the full path to `powershell.exe` for the
same reason.

### Notification backends

Getting a notification out of WSL2 turned out to be the hard part, so `notify.py` carries
three backends, chosen with `GO_NOTIFY`:

| Backend   | Mechanism                        | Status on this machine                    |
| --------- | -------------------------------- | ----------------------------------------- |
| `msgbox`  | modal `MessageBox` dialog        | **works** (default)                       |
| `balloon` | tray balloon via `NotifyIcon`    | untested/unconfirmed                      |
| `toast`   | native `Windows.UI.Notifications`| **disabled** — silently dropped, see below |

`msgbox` is the default because it is the only one confirmed to render here. The tradeoff
is that it steals focus and blocks until dismissed, which is tolerable twice a day but
would be obnoxious hourly.

Selecting an unavailable backend is refused loudly and exits non-zero, so cron mails you
instead of failing quietly.

**Why toast is disabled.** Native toasts fail *silently* for non-packaged apps. The API
call succeeds, `$notifier.Setting` reports `Enabled`, and nothing whatsoever appears on
screen. There is no exception to catch and no error to log, so a cron job using toasts
looks exactly like a cron job that never ran — which is strictly worse than having no
notifier at all. The `_toast` implementation is kept in `notify.py` for reference but is
not listed in `BACKENDS`, so it cannot be selected by accident.

Diagnostics ruled out the usual suspects: no Focus Assist / Do Not Disturb active, no
global toast toggle disabled, `explorer.exe` present in the same session, and the process
holding an interactive `WinSta0` window station. Registering an AppUserModelId did get
Windows to create a notification-settings entry for the app, but still produced no visible
toast; that key has since been removed and the repo leaves no registry state behind. If
you ever want to revisit it, installing the BurntToast module is the next thing to try.

### WSL2 specifics

These were verified on this machine, but they are the things that break on a fresh WSL
install:

- **cron must actually be running.** WSL2 only runs an init system when systemd is enabled.
  This machine has `systemd=true` in `/etc/wsl.conf` and `cron.service` is enabled and
  active. Without systemd, cron never starts and the job silently never fires. Check with
  `systemctl status cron`; enable with `sudo systemctl enable --now cron`.
- **cron only runs while the distro is running.** WSL shuts the VM down a few seconds after
  the last shell exits, taking cron with it. A missed schedule is *not* made up on next
  boot. If you want checks while no terminal is open, drive it from Windows Task Scheduler
  instead (`wsl.exe -d <distro> -e /home/markv/using-opencode-go/go-alert`), which starts
  the distro on demand.
- **`notify-send` does not work here.** WSLg provides a display but no notification daemon —
  it fails with `org.freedesktop.Notifications was not provided by any .service files`.
  Every backend therefore goes out through `powershell.exe`, none of which need extra
  packages installed.
- **GUI from WSL does reach the desktop.** `[Environment]::UserInteractive` is true, the
  window station is `WinSta0`, and dialogs render on the 1920x1080 primary screen. If a
  notification does not appear, the backend is at fault, not the WSL/Windows boundary.

## Reconciling with `opencode stats`

`opencode stats [--days N] [--models]` reports usage from the local database. Expect it to
*understate* what the server bills you: it only knows about sessions run on this machine,
so anything from the web UI, another box, or the GitHub agent is missing, and its cost
figures are computed locally rather than at opencode's metering prices. When the two
disagree, the server number is the one that counts against your cap.
