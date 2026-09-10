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

### 5. Shift spend off other providers

Any work sent to a metered provider (OpenRouter and friends) while prepaid Go budget sits
idle is money spent twice. Prefer Go for anything with a comparable model on the plan,
until the monthly cap is the thing stopping you.

### 6. Watch pace, not totals

A raw "used $4.20" figure means nothing without knowing how far through the window you
are. `go-usage` prints a pace multiplier for this: 1.0x means you are exactly on track to
use the full cap, below 1.0x means you are leaving money unspent.

## `go-usage`

Prints remaining quota for all three windows, with reset times in local time, a burn-rate
multiplier, and the daily budget needed to finish the month at 100%.

### Usage

```
./go-usage
```

No arguments, no dependencies beyond the Python 3 standard library.

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

`go-alert` checks your monthly pace and raises a **Windows toast notification** when you
are underspending. It is meant to be run from cron.

```
./go-alert
```

It prints nothing and exits 0 when there is nothing to say, so cron stays quiet. When it
does fire you get a toast reading:

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
  Hence the PowerShell toast, which needs no extra packages (BurntToast is *not* required).
- Toasts are attributed to Windows PowerShell and land in the Action Center. If none
  appear, check Focus Assist / Do Not Disturb and that notifications are enabled for
  Windows PowerShell.

## Reconciling with `opencode stats`

`opencode stats [--days N] [--models]` reports usage from the local database. Expect it to
*understate* what the server bills you: it only knows about sessions run on this machine,
so anything from the web UI, another box, or the GitHub agent is missing, and its cost
figures are computed locally rather than at opencode's metering prices. When the two
disagree, the server number is the one that counts against your cap.
