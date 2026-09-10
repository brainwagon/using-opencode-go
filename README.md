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

Constants at the top of the script:

- `AUTH` — path to opencode's credential file, default
  `~/.local/share/opencode/auth.json`. The script reads the `opencode-go` key from it; no
  key is stored in the script itself.
- `CAPS` — the dollar caps per window. **Update these if opencode changes the plan**, since
  the API reports only percentages and cannot tell you the caps moved.
- `WINDOW_DAYS` — window lengths used for the pace math only.

### Known limitations

- The dollar amounts are derived, not authoritative — see "Checking your balance" above.
- `WINDOW_DAYS["monthly"]` assumes a flat 30 days, so pace is slightly off in 28- and
  31-day months. The "used / left" figures are unaffected.
- The 5-hour window is *rolling*, so its pace number is a rough indication only; the math
  treats it as a fixed window.
- The endpoint is undocumented and may change or disappear without notice.
- A `User-Agent` header is required. Cloudflare returns `403 Forbidden` for Python's
  default urllib agent.

## Reconciling with `opencode stats`

`opencode stats [--days N] [--models]` reports usage from the local database. Expect it to
*understate* what the server bills you: it only knows about sessions run on this machine,
so anything from the web UI, another box, or the GitHub agent is missing, and its cost
figures are computed locally rather than at opencode's metering prices. When the two
disagree, the server number is the one that counts against your cap.
