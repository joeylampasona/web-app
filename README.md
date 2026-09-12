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

Then export your key and set `data.provider` to `polygon` in
`config/settings.yaml`:

```
export POLYGON_API_KEY=your_key_here
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
.github/     the nightly workflow
```

`PLAN.md` is the Phase 0 plan. `DECISIONS.md` records every choice made where
the brief left a gap, and the two places this build deviates from it.

---

## Scheduling

`.github/workflows/nightly.yml` runs weekdays at 6:30pm Eastern and posts to
`DISCORD_WEBHOOK_URL` with the failing stage if anything breaks. GitHub cron is
UTC only and does not follow US daylight saving, so both candidate hours are
scheduled and the job checks the real Eastern hour before doing any work.
Deployment is deliberately not scheduled.

Secrets it expects: `POLYGON_API_KEY`, optionally `EDGAR_USER_AGENT` and
`DISCORD_WEBHOOK_URL`.

---

## What this will not do

- Place, size or route an order.
- Tell you what to do with a stock. The site describes what has happened.
- Pretend a backtest is clean. Free data tiers carry no delisted companies, so
  every run is survivorship-biased, `survivorship_safe` is stamped `false`, and
  every return metric carries a PROVISIONAL flag until that changes.
