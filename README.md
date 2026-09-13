# US Equities Base & Breakout

Scans the liquid US equity universe after each close, detects base-and-breakout
structures, ranks by relative strength, overlays dated catalysts and
implied-volatility context, publishes static JSON, and serves it from a
five-tab mobile-first PWA with a configurable backtest engine.

**No order-placing code lives here and none ever will.** This is a screening
and market-analytics tool, not investment advice.

> The one thing that shapes this whole build: an out-of-sample study on a US
> universe found the *structural* components of VCP carried no measurable edge.
> The only component with statistical support was relative strength (p=0.006),
> at a transaction-cost floor of 0.198R. So relative strength is the primary
> ranking and the default sort everywhere, base and pivot detection is a
> presentation and timing layer, and no copy on the site claims a pattern
> predicts a return.

---

## Getting set up

Run these one at a time from the repository root.

```
python3 -m pip install -r requirements.txt
```
Installs the four Python dependencies. There is no numpy or pandas in the core
pipeline — every calculation here is a rolling mean, a true range or a
percentile, and dropping the two heaviest wheels keeps the nightly job fast and
the install trivial.

```
cd web && npm install && cd ..
```
Installs the web app's dependencies.

### Before you point this at real data

Verify that Polygon's free Basic tier still includes grouped daily aggregates.
That single endpoint is what makes this free.

```
curl "https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2026-09-11?adjusted=true&apiKey=YOUR_KEY"
```
A `results` array with several thousand entries means the plan holds. A
`NOT_AUTHORIZED` is a stop condition, not a detail.

**Switching provider needs `--reset`.** Prices from one provider and the ticker
list from another produce a universe that looks plausible and is wrong, so the
backfill refuses to mix them. When you change `data.provider`, run
`python -m cli universe --refresh --reset` once to clear the old bars.

Then export your key and set `data.provider` to `polygon` in
`config/settings.yaml`:

```
export POLYGON_API_KEY=your_key_here
```

Machine-specific settings belong in `config/settings.local.yaml`, which is
gitignored and layered over `config/settings.yaml`. Put your provider choice
there and pulling a change to the tracked file will never collide with it:

```
data:
  provider: polygon
  backfill_days: 900
```

Out of the box the provider is `synthetic`: a deterministic offline fixture so
every command below runs without credentials. It invents its own tickers and
company names rather than putting fabricated prices under a real company's
name, and everything built from it is stamped `data_source: synthetic_demo`,
which the web app banners on every page.

---

## The pipeline, one command per phase

```
python -m cli universe --refresh
```
Pulls reference data, backfills daily bars, and prints the liquidity funnel
stage by stage with the survivor count at each step.

```
python -m cli rank
```
Prints the top 20 by RS rating, the industry and theme tables, the sector ETF
ranking, the eight breadth metrics and the rotation quadrant counts.

```
python -m cli scan
```
Runs the four detectors and prints per-screen counts by stage, the first ten
setups, and what changed since the last scan.

```
python -m cli catalysts
```
Prints the dated events for everything currently on a screen, and the High IV
table.

```
python -m cli backtest --screen vcp --positions 5 --stop 8
```
Replays the rules over history and prints a summary table, the year-by-year
series and the trade list. Losing trades are included; that is the point.

```
python -m cli publish
```
Writes the `out/` JSON tree and validates `meta.json` against its schema.

```
python -m cli all
```
The whole sequence, which is what the nightly workflow runs.

---

## The web app

```
cd web && npm run dev
```
Serves the app at http://localhost:3000. It reads the `out/` tree the pipeline
wrote and never queries a database. The one exception is a custom backtest run,
which posts to `/api/backtest`; that route shells out to the Python engine, so
it needs Python on the same host. The default combination for each screen is
precomputed, so the backtest page loads instantly without it.

```
cd web && npm run build
```
Production build. Checks types and prerenders every static route.

---

## Layout

```
config/      settings.yaml and themes.yaml — every tunable
data/        adapters, the liquidity funnel, the SQLite store
patterns/    param schema, base detection, the four detectors, stages, the diff
rankings/    RS, group aggregation, breadth, rotation, treemap
catalysts/   dated events, read-through, implied-volatility scoring
backtest/    the configurable replay engine and its metrics
publish/     the out/ writer and the meta.json schema
cli/         python -m cli
web/         Next.js App Router, TypeScript
supabase/    the account tables and their privacy rules
.github/     the nightly workflow
```

**Picking this up after a break: start with `HANDOFF.md`.** It says what state
the deployment is in, what to check, and what to do next, in order.

`PLAN.md` is the Phase 0 plan. `DECISIONS.md` records every choice made where
the brief left a gap, and the two places this build deviates from it.

---

## Deployment

The site is a Next.js app that reads the JSON tree for every number it shows.
Nothing about a stock, a screen or a backtest comes from a database — hosting it
is hosting static-ish files plus a couple of server routes.

Accounts are the exception, and they are optional. With a Supabase project
configured, watchlists and saved screens live in two tables behind row-level
security. With no project configured the site runs exactly as it did before
accounts existed and those features stay gated, so the build never depends on a
private project. `HANDOFF.md` has the setup steps; `supabase/schema.sql` is the
schema.

**How the data gets there.** The nightly Action force-pushes `out/` to a branch
called `data` as a single commit, so that branch never accumulates history and
a few megabytes of JSON a night never grows the repository. At build time,
`web/scripts/fetch-data.sh` downloads that branch into `web/out`. The repository
is public, so no credentials are involved anywhere in that path.

**Vercel setup**, once the nightly job has run at least once:

| Setting | Value |
|---|---|
| Framework | Next.js (detected) |
| Root directory | `web` |
| Build command | leave default — `vercel-build` in package.json is picked up |
| Environment variables | none, unless you want accounts |

For accounts, add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
— the anon key, never the service-role key, which bypasses every privacy rule
and would be compiled into the pages. `web/.env.example` says the same thing next
to the variables themselves.

Pushing to the branch redeploys the site. The nightly job pushing to `data` does
not, so the workflow calls a deploy hook after it publishes. Create one in Vercel
and store it as the `VERCEL_DEPLOY_HOOK` secret; the step does nothing while the
secret is unset, so nothing breaks before you get to it.

**One thing does not work on Vercel:** a custom backtest run shells out to the
Python engine, and Vercel's Node runtime has no Python. That route returns a
clear message saying so. The precomputed default for each screen is served from
the JSON and works normally.

## Scheduling

`.github/workflows/nightly.yml` runs weekdays at 6:30pm Eastern and posts to
`DISCORD_WEBHOOK_URL` with the failing stage if anything breaks. GitHub cron is
UTC only and does not follow US daylight saving, so both candidate hours are
scheduled and the job checks the real Eastern hour before doing any work.
Deployment is deliberately not scheduled.

Secrets it expects, set under Settings → Secrets and variables → Actions:

- `POLYGON_API_KEY` — required
- `EDGAR_USER_AGENT` — a contactable address, e.g. `Your Name you@example.com`.
  SEC throttles anonymous callers hard.
- `DISCORD_WEBHOOK_URL` — optional, for failure alerts

Trigger it by hand the first time: Actions → Nightly scan → Run workflow, with
"Run even if it is not 6pm in New York" left on.

The job caches the SQLite database between runs. If that cache is ever evicted
the backfill starts over, which is about 100 minutes — the run will still
succeed, it will just take longer.

---

## What this will not do

- Place, size or route an order.
- Tell you what to do with a stock. The site describes what has happened.
- Pretend a backtest is clean. Free data tiers carry no delisted companies, so
  every run is survivorship-biased, `survivorship_safe` is stamped `false`, and
  every return metric carries a PROVISIONAL flag until that changes.
