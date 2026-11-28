# Decisions, gaps and deviations

The brief lists a set of things it deliberately left open, and says to stop and
ask rather than invent them. This build was asked for in one go, so rather than
stop with nothing delivered, each gap below was filled with the most defensible
option and recorded here. **Every one of these is yours to overrule** — they are
all small, localised changes.

---

## Gaps from section 3, and what was built instead

| Gap | What was built | Where |
|---|---|---|
| **Grid vs list view on Screens** | The toggle is real. Cards is the default; List is a dense table — ticker, RS, close, vs pivot, base length, tightening, dry-up, stage. Compact cards were the other candidate and would be a small change. | `web/components/ScreenBrowser.tsx` |
| **Share button output** | Web Share API with a one-line summary and a link to the stock page, falling back to the clipboard. A rendered PNG of the chart plus metrics is the likelier answer and needs a decision. | `web/components/ShareButton.tsx` |
| **Industry and theme detail page** | One layout serves both: the group's RS, average member RS, leaders, fresh breakouts, the three RS-change windows, and the member table. Needed because the treemap and the rotation scatter both drill into it. | `web/components/GroupDetail.tsx` |
| **Guide and case study article layout** | Index only, as specced. Each card is marked "not written yet" rather than linking to a page that does not exist. Five honest article stubs seeded. | `web/content/reading.ts` |
| **Rotation "drag to trace a path"** | Skipped for v1, as instructed. | — |
| **"Ask a question" on the rotation map** | Skipped for v1, as instructed. | — |
| **Auth provider (Clerk vs Supabase)** | **Not chosen.** `lib/auth.tsx` is the seam: it reports signed-out and raises the sign-up sheet. Swap `signedIn`/`user` for the real client and all four gates start working without touching a component. The gates themselves are built and in place: watchlist, saved custom screens, export, X-ray. | `web/lib/auth.tsx` |
| **Subgroups** | Themes replace them, as the brief intends. | `config/themes.yaml` |

---

## Two deviations from the brief, both deliberate

**1. The legend on the VCP Learn schematic.** The brief specifies the wording
"up days (buying) / down days (selling)", and separately requires that the
words buy and sell never appear in the UI except the Learn page's step-1 label.
Those two lines conflict. The hard legal constraint wins: the legend reads
"up days (demand) / down days (supply)". Same for the backtest setting the
brief calls "Sell winners by", which reads "Exit winners by". Change either in
one line if your review disagrees.

**2. `SyntheticAdapter`.** Not in the brief. It exists because every
verification command and the entire web app need bars on disk, and no
credentials exist in this environment. It is a fixture, not a data source: a
fixed seed, invented tickers and company names — so no fabricated price series
is ever published under a real company's name — and a `synthetic_demo` stamp in
`meta.json` that the web app banners on every page. Point `data.provider` at
`polygon` and it disappears entirely.

---

## Judgement calls inside the specced scope

**Market-wide breakout counts.** Breadth's "broke out today" and "tested the
pivot and failed" use a screen-independent definition — a close above the
highest high of the prior 50 sessions — so the number means the same thing
whichever screen you are looking at. Screen-level breakout counts come from the
scan and are counted separately.

**Which gates a played-out name has to pass.** A setup that already broke out
is not asked to prove it is still near its pivot or still a leader. It is on
the screen so its outcome can be shown. The structural gates (base length,
depth, and the screen's own shape test) still apply to every stage.

**The custom-screen dial panel.** Every dial is generated from the detector
param schema. Five of them — the lookback window, the swing threshold, the
fresh-breakout window, the all-time-high tolerance and the listing-age limit —
decide *where the base is* before any published metric exists, so they cannot
be applied to an already published setup. They are shown, disabled, with the
reason stated, rather than quietly dropped from a panel that claims to be
generated from the schema. Making them live means a re-scan API route.

**Historical earnings dates in the backtest.** We only hold forward earnings
dates. When "skip earnings within 7 days" is on, historical ones are projected
backwards on a quarterly cadence from the next known date. That is an
approximation, it is stated in the run's notes, and it flags the affected
metrics provisional.

**Index additions and deletions.** The event type exists and stays empty. There
is no free automatic feed we are willing to depend on, and the alternative is
the hand-maintained events database the brief rules out.

**Read-through tags.** `supplier` is in the vocabulary and is never emitted.
We have no free supply-chain source, and asserting a supplier relationship we
cannot evidence would be inventing data. Peers in the same theme and the same
industry are tagged `competitor`; the rest are tagged `industry`. Only the
largest name in a theme emits read-throughs.

---

## Decided since

**Where `out/` lives in production: committed to a `data` branch, repository
public.** The tree was 54MB extrapolated, almost all of it bars stored as JSON
objects; as rows, and only for stocks actually on a screen, it is roughly 11MB.
The nightly job force-pushes it as a single commit so the branch carries no
history. A public repository means the Vercel build fetches it with no
credentials at all, which also ends the recurring git authentication problem.
Cloudflare R2 remains the escape hatch if the tree ever outgrows this.

**Custom backtest runs do not work on Vercel.** The route shells out to the
Python engine and Vercel's Node runtime has no Python. It returns a clear
message; the precomputed default per screen is served from JSON and works. A
separate worker would fix it if the feature turns out to matter.

## Answered: does free Basic serve grouped daily aggregates?

**Yes, with a roughly two-year history limit.** A recent session returns twelve
thousand tickers; a date beyond the window returns 403 on that date, not on the
endpoint. The backfill bisects for the oldest session the plan will serve and
starts there.

The cost of that limit is the multi-year screen. It looks for lids that have held
52+ weeks inside a 104-week window, and two years of history leaves no room for a
breakout to have happened after a year-long base — the first live run returned 42
setups, every one of them `forming`, zero breakouts. Either shorten that screen's
lookback to about 78 weeks, or get deeper history from Stooq, whose adapter is
already stubbed for the purpose.

## Answered: the auth provider

**Supabase, magic link.** Chosen by the owner over Clerk. It carries identity and
storage on one free account, and all four gated features need storage, so a
provider that only did identity would have meant standing up a database beside it
anyway. A magic link means no password for this app to store, forget or leak.

`@supabase/supabase-js` is the one dependency this added, and it was added on an
explicit choice rather than a judgement call, which is why it is here and not on
the stop list.

The two environment variables are absent in the repository, and that is a
supported state rather than a broken one: with no project configured the client
is null, the four features stay gated, and the sign-up sheet says accounts are
not switched on instead of collecting an address it cannot mail. A build must not
depend on a private project.

Row-level security carries the whole privacy model (`supabase/schema.sql`). Every
policy is `auth.uid() = user_id`, so the public anon key compiled into the pages
reads and writes one person's rows and nobody else's. The 50-ticker and 20-screen
limits are database triggers as well as UI, because a limit that only exists in
the client is not a limit. No service-role key is needed anywhere in this project.

## Answered: the share payload

**A PNG, composed in the browser.** A link renders on a phone as a grey rectangle
with a domain in it, which hides the only thing worth sharing. The image carries
the header line, a screenshot of the chart already on screen, the metric rows and
the disclaimer, and it falls back to a download, then a link, then the clipboard.

No new dependency: it is canvas plus `lightweight-charts`' own `takeScreenshot()`.
Building it now rather than later was cheaper than it looked, because the chart
component had to expose that handle either way.

## Answered: the multi-year screen

**Shortened, and that fixed it.** The lookback moved 104 → 78 weeks, which is as
far as it can go while still meaning "multi-year".

Measured on live data, before and after:

| | 104 weeks | 78 weeks |
|---|---|---|
| Total | 42 | 101 |
| forming | 42 | 28 |
| fresh_breakout | 0 | 2 |
| climbing | 0 | 13 |
| played_out | 0 | 58 |

At 104 the window and the available history were nearly the same length, so
there was one valid position and nowhere for a breakout to sit after a year-long
base — every setup was `forming` because the screen could not see past the base
it had just found. The detector was right; the window was wrong for the history.

This does not remove the two-year limit, it just stops that limit from consuming
the whole screen. Raise the window back toward 104 once the nightly has
accumulated enough days that it is meaningfully shorter than the history.

## Still open, and worth deciding before launch

1. **Legal review of the copy.** Especially the two deviations above. Every page
   carries the disclaimer and no page uses banned language, but that is care, not
   a lawyer's sign-off.
2. **Custom backtest runs on the live site.** The API route shells out to the
   Python engine, and Vercel's Node runtime has no Python, so a visitor can read
   the precomputed default for each screen but cannot move a dial and re-run.
   The route now declines with an accurate message rather than a guess. Fixing it
   means a small worker somewhere that does have Python — worth doing only if the
   feature turns out to matter to anyone.
3. **`postcss` is pinned through an `overrides` entry**, past GHSA-qx2v-qp2m-jg93
   and three siblings. It arrives under Next.js, and npm's only other route to a
   fix is Next 16, whose Turbopack rejects this project's `../out/**` tracing
   glob. The override should come out when Next ships a version that carries a
   patched postcss itself.


## Noted, not fixed: fractional share volume

Polygon returns fractional volume for recent sessions — 140 of the 180 bars
published per stock, starting at exactly 2026-02-23, identically across every
ticker. Older bars are whole numbers. We do not touch the value: the adapter
takes `v` from the grouped daily response and stores it.

A shared boundary date rules out split adjustment, which would fall on a
different date for each ticker. Beyond that the cause is unknown, and cannot be
established without querying Polygon directly for a single date and comparing.

Left alone because the effect on everything computed from it is about two parts
in a billion: the 20-day average dollar volume that drives the liquidity filter
differs by 0.0000002%, and the volume dry-up ratio the VCP detector uses is a
ratio, so the fractions very nearly cancel. Fractional share trading is real and
does reach the consolidated tape, so this may simply be what the data is.


## Ported from Market Desk, with two changes (2026-11-08)

The strength radar, leadership layers, quarterly earnings read and nights on
the screen all come from Market Desk's first weeks of November.

- **Layers are read against the stock's own industry, not an ETF.** Market
  Desk benchmarks each name against a theme or sector fund, which leaves most
  of a 2,700-name universe against SPY with no group. Here each industry with
  ten or more members gets an equal-weighted index of its members, read
  against SPY the way the radar reads its funds, so nearly every stock has a
  group. Smaller industries fall back to SPY, as Market Desk's ungrouped names
  do.
- **The earnings read now carries Market Desk's verdict (2026-11-09).** It
  first shipped without the takeaway sentence and "growth REAL / proof
  PENDING", on the grounds that every other number here is a measurement.
  The owner asked for the desk's card as it is, on its own Earnings tab, so
  both are in, on that tab and on the stock pages. They are rule outputs on
  the filed numbers and the card says so. Two departures from the desk: a
  backlog under a tenth of a year's revenue is not printed (it read "0.0×"),
  and a quarter with profit and cash in place but carried by deferred revenue
  or stock pay asks whether the cash flow holds without them, rather than the
  desk's fall-through "what turns the cash flow positive?".
- **The radar is not logged.** Market Desk writes every reading to a table so
  a week can be rebuilt. Every bar is already in this database, so the week
  ago is read again at an offset of five sessions instead.


## The printed market page (2026-11-10)

The site was redesigned away from "Ink & Amber" (cream cards, a dark hero
slab, Inter) because it read as a generic dashboard. The owner picked the
direction from a concept: a printed market page.

- **Rules, not boxes.** Square corners everywhere, sections divided by an ink
  rule, cards kept only where a thing is genuinely a card.
- **IBM Plex in three widths.** Sans for reading, Condensed for headlines and
  labels, Mono for every figure. Loaded from a `<link>` in the layout: the
  old `@import` sat after the token rules, where browsers ignore it, so Inter
  and JetBrains Mono had never loaded and the site had been in system fonts.
- **The lime is a highlighter.** It marks the phrase that carries the read,
  the active nav item, fresh breakouts and fully aligned groups. In light mode
  the brand "ink" is now ink itself, not gold.
- **A tape strip under the masthead** on every page: the indexes (delayed
  quote when there is one) and the day's counts.
- **Home page instruments** replace prose and uniform cards: the read as a
  headline with a four-cell meter, key ratios as bars from a centre line,
  the leadership layers as one proportional bar, the strength matrix, the
  week ahead as a bar per day, and the screens on one shared scale.
- **Light and dark both.** Dark is the same page in negative; the tape band
  becomes a raised strip with a lime edge.
- **Screen pages open with the pattern drawn**, beside the description, and
  the four stages are a ruled row of counts rather than buttons. On a phone
  the drawing leads the page as a band.
- **The breadth barcode**: every ranked stock as one tick, strongest on the
  left, coloured by which of its 50- and 200-day lines it is above. The
  figures under it are the share above both lines in each tenth of the
  ranking. It repeats nothing a screen or rating uses.
- **A signed-in reader's watchlist rides the tape**, first fourteen names,
  between the indexes and the market's counts. Prices come from the search
  index (last close) with the delayed quote laid over when there is one.

## Stored bars are adjusted for splits (2026-11-10)

Bars were fetched once and kept, so a split after the fetch left a false
cliff in the history: ITA read 64% behind the market after its 3-for-1 on
2026-11-04. `data/splits.py` now runs after each night's backfill. It asks
for the splits since its last check and, for each, compares the stored
closes either side of the execution date: a step near the split's ratio
means the earlier bars were never adjusted, and they are. Ratios under
3-for-2 are left alone, since a step that small cannot be told from an
ordinary day. A dry run on 2026-11-10 found 62 symbols to adjust, none of
them in the ranked universe (funds and sub-$3 reverse splits). The radar's
own guard, which sets a fund aside after a one-session move over 35%, stays.

The first night it ran (2026-11-11) it adjusted those 62 and missed ITA. The
provider lists ITA's split for 11-05, but the stored bars step between 11-03
and 11-04: a night's bar is fetched after midnight, by which time a split
executing that morning has already been applied, so the last session before
a split is stored at the new price. The check now also looks one session
before the listed date, and judges again every split the first rule called
already right. A dry run found 92 more that way, ITA, SOXX, MTUM and QUAL
among them, none in the ranked universe.

## The rest of the site set as the printed page (2026-11-11)

The home page, stock passport and screen pages had the new look and the
Market section did not. What changed, and why each is drawn the way it is:

- **The calendar is a week.** Five columns, a chip per name, strongest by RS
  first with the reader's watchlist ahead of them. Lime marks a name on a
  screen tonight; a dashed chip is an estimated date. A peer's report is its
  own short group under the names actually reporting.
- **The rotation map names its dots.** The furthest from the centre are
  labelled, each tail starts at the strength the group had a month ago, and
  each quarter has a faint wash. Tails and names are drawn only for maps of
  80 points or fewer: on the stocks tab they would be a hairball.
- **News is a ruled list** with the time in the left column. A day's law-firm
  notices fold into one line that says how many and against which names.
- **One chart on a stock's page.** Base and pivot, averages and levels are
  layers switched on one chart, where there were three charts of the same
  140 sessions. The six readings under it are a ruled strip.
- **Menus are grouped** under small headings, in the sidebar and the phone
  sheet alike.
- **Search opens from any page** on "/" or Ctrl/Cmd K. It asks `/api/search`
  for the best twelve rather than shipping the index to every page, and also
  finds the site's own pages by name. Search rows now carry the leadership
  layer.
- **Breadth figures each draw their history**, coloured by whether the week
  moved the constructive way (for the lows card, down).
- **Back issues.** The published tree is rebuilt whole each night, so an
  edition (the read, its four checks, where strength sat, the layers, the
  breadth strip in ten cells, screen counts) is stored in the `editions`
  table and the archive is written out from it every night. On its first
  night it also rebuilds the read and its checks for the sessions the breadth
  file still holds, and marks those editions as rebuilt. Nothing gated goes
  in an edition.
- **The digest email is the same page**: paper and ink, the headline under
  the highlighter, the meter as four cells, ratio bars from a centre line and
  the breadth strip in ten cells. Light only, since mail clients do not
  reliably honour a dark scheme.
- **Share tonight's read** draws the headline, meter and barcode as one
  1200 by 675 image, from the tokens of whichever theme the reader is in.

## Intraday quotes ask two sources (2026-11-21)

From the evening of 2026-11-19 Cboe's delayed-quote host refused every
request the pipeline made, 221 of 221 a run. A probe from the runner showed
why: the host now answers only requests that look like a browser arriving
from cboe.com (a browser's name with that page as Referer and Origin gets
200; every name the pipeline gives itself, and a browser's name alone, gets
403). That is a door Cboe closed on purpose, and the pipeline does not dress
up as their website to get through it.

- **Yahoo is the first source**, through the yfinance library the nightly
  already uses. Its quote endpoint answers two hundred names a request: the
  probe got 400 of 400 in under half a second, where one request a name took
  six minutes. The library's batch download stands behind the endpoint, since
  the endpoint is reached through the library's internals.
- **Cboe stays as the second source**, asked honestly and only for the names
  Yahoo left. It is abandoned for the sweep after twelve refusals with
  nothing answered, so a closed door costs seconds rather than eight minutes.
- **The sweep covers every name on a screen** now, not the nearest four
  hundred, because the cost is per request and not per name.
- **A sweep older than the published close is ignored by the site.** The last
  file from Thursday stayed up through Friday night and was overriding
  Friday's closes with Thursday's prices.
- **Headlines no longer wait on prices.** The quotes job stopped at the failed
  price step, so the session with no prices was also a session with no new
  headlines. Both later steps run regardless now, and the job still ends red.
- **Not fixed here:** the nightly's option chains come from the same host and
  have been falling back to Yahoo's shorter book since the same night, with
  nothing in the log saying so. The index figures the site reads live from
  Cboe at request time are refused too and fall back to the sweep.

## Every source says how its night went (2026-11-21)

Two sources failed in one week and neither said anything: the quote host
refused a whole session, the option-chain host did the same and the nightly
fell back to a shorter book, and the Market Desk stopped publishing while the
site carried on with its last file. Each showed only as a line missing from a
thousand-line log.

- **One row a source, in `meta.json` under `sources`.** Prices, option
  chains, earnings dates, forecasts, filings, the Market Desk and headlines:
  each with a status (`ok`, `partial`, `behind`, `down`), a sentence, and the
  date it covers. Stages record their own row as they run (`publish/health.py`
  keeps them in the key-value table, since stages are separate processes);
  publish judges prices and the desk itself, from the stored bars and the date
  of the desk's newest run.
- **Three readers of the one list**: the nightly log, the Discord summary
  (which now names any source not at full strength) and the colophon page.
- **Gamma says which book it was built from.** A chain carries its source, and
  a profile built from the shorter one is published with `book: "partial"`.
  The page marks those rows and says once at the top what that means:
  concentrations are understated and the peak strike can differ. Rows stored
  before this change carry no label until they are fetched again.
- **Cboe is left alone after twelve refusals in a row.** The nightly was being
  told no about twelve hundred times a night, twice each, with a pause
  between. Now it stops asking for the rest of the run and says so.
- **Cboe is given a plain client name.** It had been sent the contact string
  SEC requires, which carries an address and belongs with SEC only.
- **Quote rows carry volume** where the source has it (shares so far and an
  ordinary day's), so a move through a pivot can be read against its volume.

## Discord has three rooms, and cards have addresses (2026-11-21)

One webhook was carrying the nightly counts, the draft for X and every
failure notice. The server is private, which is also the only reason names
beyond the free sample may be posted there.

- **Three rooms, each a webhook of its own**: `DISCORD_WEBHOOK_EDITION`,
  `DISCORD_WEBHOOK_STOP_PRESS` and `DISCORD_WEBHOOK_OPS`. Each falls back to
  the original `DISCORD_WEBHOOK_URL` until it is set, so nothing changes on
  the day and a room starts working the moment its secret exists.
- **The edition is a picture.** The nightly posts the read as a card (headline,
  checks, a link to the back issue) with the screen counts under it. The card
  is drawn by the site, so the command waits up to seven minutes for the site
  to carry the session and posts without the picture rather than with last
  night's. Anything amiss goes to operations, with the draft for X.
- **Stop press** is posted from the intraday quotes job: a forming long setup
  now through its pivot, on a quote stamped today, with volume at least one and
  a half times an ordinary day's pace. Each name once a day, six a run at most.
  What has been posted rides on the quotes branch as `stop_press.json`, the
  job's only memory between runs. It uses the alert sweep's own detection, so
  a crossing in Discord and one in a subscriber's email are the same judgement.
- **A wrap on Saturday** (`wrap.yml`): the read each night, the market's
  breakouts against failed tests, and the week's base breakouts with how many
  still sit above their pivot. It reads the published tree only.
- **Cards are drawn by the server** so a link pasted anywhere unfurls into its
  card, and the same image serves the Discord post.

## Four more things said in Discord (2026-11-21)

- **A fourth room for earnings** (`DISCORD_WEBHOOK_EARNINGS`). After the
  nightly, the read on each company that reported in the last few days, as a
  card: the takeaway, the figures, the verdict and the question. Six a night
  at most, names on a screen first, each company once: what has been posted
  is kept in the database, which the nightly carries from night to night.
- **New on a screen** follows the edition: the names that started forming a
  base last night, by screen, from the nightly's own diff. Silent on a night
  with none.
- **The morning line** follows it too, posted by the nightly so it is there
  before anybody is awake and does not depend on a morning schedule firing:
  who on a screen reports next session, how many others do, and the notable
  data due. Silent when there is neither. It does not know market holidays.
- **Stop press, settled.** The first quotes run at least twenty minutes after
  the bell holds each of the day's stop press names up to the level it was
  posted against: held above, or fell back under. Once a day. The stop press
  note on the quotes branch now keeps that level beside each name. The hourly
  backstop for the quotes job gained a 4:41pm New York firing for it.

## Earnings in two parts: the reaction on the day, the read when it is filed (2026-11-21)

- **A read waits for its filing.** The read of a quarter is built from the
  10-Q, which is filed days after the print. Until then the read on file is of
  the quarter before, and the first cards sent to the earnings room included
  three of those under the date of the new report. Only a read that covers the
  reported quarter is posted now, within a fortnight of the report, and each
  card says which quarter its figures are from.
- **The reaction is posted on the day** (`earnings.yml`, `cli reporters`):
  about 9:20 in New York for the companies set to report before the bell, with
  the price before the bell, and about 18:00 for the rest, with the price after
  it. The figure against the estimate is given when Yahoo has it and said to
  be missing when it does not. Names on a screen first, then the largest;
  thirty looked up a run; each company once a day, kept on a `reporters`
  branch. The command picks its run from the New York clock and says nothing
  outside its two windows, so a schedule delivered late posts nothing.
- **A read is posted when its filing arrives, not at night.** Half the 10-Qs
  for a day's reports are in within a day and most within three, at no
  particular hour. Each of the day's two reporters runs asks SEC about the
  recent reporters still waiting on one, on the nightly's database restored
  read-only, and posts the read of any that has arrived. What those runs post
  is kept in their note on the `reporters` branch; the nightly reads that note
  and the runs read the nightly's own, so a card is sent once.
- **The move is set beside what the options priced.** Where the earnings file
  has an implied move for a report, the reaction line says it: six per cent is
  a shrug against twelve and a shock against three. Most companies have no
  figure, and their lines say nothing about options.
- **The week's earnings on Sunday evening** (`weekahead.yml`): for each day of
  the week to come, the names on a screen that report, with the priced move
  where known, and how many others in the universe report that day. One
  scheduled time so it posts once. It does not know market holidays.

## Option chains come from the clearing house and Yahoo (2026-11-25)

- **What broke.** Cboe has refused the nightly since 19 November. The
  fallback was Yahoo alone, read at two in the morning, and the first night
  on it gamma covered 225 companies holding 163,000 contracts, against 461
  and 13.7 million three nights earlier.
- **What was measured** (`probe.yml`, `only: chains`, 22:39 New York, sixty
  names). OCC's public series file answered for every company that has
  options, in about half a second each, and says "No data exists" for one
  that has none. Yahoo's own open interest was nearly as full as OCC's,
  16.5 million contracts against 17.6 million, and the same again at 02:30,
  so the hour is not what starved it on the 24th. What did is not known. 76% of Yahoo's contracts
  carried an implied volatility worth believing, 14% a quote too wide to be
  one, and most of the rest a figure drawn from an old trade.
- **The chain is joined** (`catalysts/chains.py`). Open interest is OCC's,
  the cleared figure, for every series on the expiries asked about. Implied
  volatility is Yahoo's, for expiries inside 95 days, believed only where
  the contract has a two-sided quote no wider than half its mid or traded
  on the latest session. Any other contract takes the nearest strike's on
  the same expiry. The High IV reading is
  built only from volatilities Yahoo quoted. Market Desk made the same join
  the same evening (`scanners/chains.py` there); the two were written
  separately and should be kept telling the same story.
- **Order of asking**: Cboe, which stands down after twelve refusals and
  would be the full book again if it reopened; then the join; and Yahoo's
  own open interest only when OCC does not answer, which is the one case a
  gamma row is still marked partial. A company OCC holds nothing for is not
  put to Yahoo at all.
- **Cboe's block is not worked around.** A browser's headers get past it.
  It was put up on purpose, in front of something Cboe sells.
- **The first night on it** (session of the 25th, read about 02:00): 415
  full books from the join, none from Yahoo alone, 27 companies with no
  chain; the gamma board at 502 names. OCC's file was exactly as full at
  02:30 as at 22:39, so the chains stay in the nightly and no evening run
  was built. OCC answers three to four times slower at that hour, 1.7
  seconds a company against half a second, and the options stage took 37
  minutes against 12.

## What Market Desk sends is read whole, and dated (2026-11-25)

- **Its options reads are judged by their own date.** The desk's stage list
  does not cover its options stages. The week its chain source went dark
  every stage said ok, and the move "priced" into Deere's report on the 25th
  had been read on the 18th. The source report now has a second row for the
  desk, dated by its newest chain read, and it is behind when that trails
  the desk's own run by more than two sessions.
- **A priced move carries the night it was read.** A read more than two
  weekdays older than it should be is marked stale in the earnings file, on
  the calendar's events and on the stock page, and the site says "read Nov
  18" beside it. Discord leaves a stale read out: a line that sets a move
  beside what options priced has no room to explain the date.
- **Four blocks that were dropped at the door are kept** (`desk_runs.extras`):
  dealer gamma for the index and the sector funds, the squeeze read for the
  names the desk ranked, FINRA short interest for the names it flagged, and
  the macro releases inside a five-session hold. Published as
  `market/dealer_gamma.json`, `market/squeeze.json`, two fields on a stock's
  page and one on the market context. All free: market level, or public
  FINRA figures. A stock with no short interest shown is one the desk did
  not flag that night, not one nobody is short.
- **Dealer gamma is the desk's reading, not ours.** The Tape's own gamma
  page reports concentration and labels the signed figure as resting on an
  assumption. The desk's index and sector table is that assumption applied,
  and the page says so.

## The day's earnings figures come from Finnhub when there is a key (2026-11-25)

- **Why.** Yahoo's earnings table fills in a reported figure hours after the
  release, a request a company, and has no revenue. Finnhub's calendar is
  one request for the day with earnings and revenue against their estimates
  soon after the print. The desk has used it for months.
- **How** (`catalysts/finnhub.py`, in `cli reporters`). With
  `FINNHUB_API_KEY` set, the morning and evening runs read the day's
  calendar first. A company it has a time and a figure for is not put to
  Yahoo at all. Where it has no figure yet, Yahoo's is used with Yahoo's own
  estimate, so a surprise is never one source's result against the other's
  expectation. Revenue is Finnhub's alone. Without the key the run is as it
  was.
- The key travels in a header, never in the address.

## What was added after the cross-check (2026-11-26)

- **Quotes have a working second source.** Yahoo, then Finnhub for the names
  Yahoo does not answer for, then Cboe. Finnhub is a request a company at
  the plan's sixty a minute, so it is a backstop for the names nearest their
  pivot, not a replacement.
- **The evening reporters run is its own scheduled task at 18:00 New York**,
  the morning one at 09:20. One schedule cannot say both.
- **A reaction settles.** The evening run says how the reactions already
  posted held up over a full session: a before-the-bell report in that day's
  session, an after-the-bell one in the next day's, close to close, beside
  the quote first given and whether the priced move held. Yahoo's session
  figure counts only when it is today's session, so a holiday waits.
- **The Earnings page shows the day's reporters** from the note on the
  `reporters` branch, through a route of its own, between nightly builds.
  The rows it reads carry no screen membership. Which screen a name is on is
  the paid half of the site and those rows are public.
- **The week's sources go to the ops room after the Saturday wrap**: a line
  a source, ok all week or which nights it was not and why. The nightly
  keeps three weeks of statuses and publishes them in `meta.json`, so the
  wrap still needs no database.
- **S&P 500 membership** is the public constituents list at
  github.com/datasets, fetched weekly. A convenience copy, not S&P's own
  publication. Null until fetched once, and a list of the wrong size is not
  believed.
- **The desk's options read and short volume per name** arrive with its
  schema 1.8, which was added to the desk for this. Kept for the site's own
  names; dated; never shown as zero for a name the desk did not read. The
  desk spells class shares without their dot, so those are absent.
- **A first read from the press release, by a model**
  (`data/press_release.py`, off without `ANTHROPIC_API_KEY`). The one part
  of the site that is not arithmetic over filed numbers, and labelled so
  wherever it appears. The release is treated as a stranger's document: the
  model is told it is data, the answer is held to a schema, its sentences
  are stripped of links and mentions, and revenue that disagrees with
  Finnhub's by more than half or double is withheld; one that differs by
  less is shown beside Finnhub's, since that is two counts of revenue and
  not a misreading. Eight a run. Read by the small model: on six real
  releases it and the next one up gave the same figures throughout, at a
  fifth of a cent a read against three cents. The run's last line says what
  it spent, and `PRESS_RELEASE_MODEL` changes the model without a change
  of code.
- **No Discord post can ping anybody** (`allowed_mentions` is empty on every
  message), since some of what is posted is now read out of documents the
  site did not write.

## Trades by members of the House, from the Clerk's own filings (2026-11-26)

- **The source is the Clerk of the House, and only the House.** A member
  who trades a security files a periodic transaction report. The Clerk
  publishes the year's reports as an index and each one as a PDF, and
  `data/congress.py` reads both. The other candidates were asked from the
  nightly's runner the same day: Finnhub's endpoint is a paid one, and the
  two community feeds that republished both chambers as JSON answered 403.
  The Senate publishes its reports behind a click-through session with no
  file to fetch, so senators are not covered and the page says so.
- **What was measured** (`probe.yml`, `only: congress`, the sixty newest
  reports): 54 had text and 6 were paper filings scanned as images, which
  are counted and not read. 440 transactions, 387 of them stocks, 386 with a
  ticker. The form's cells come out of the PDF run together, the two dates
  and the amount with nothing between them, and one row in the sixty had
  its transaction cells in the middle of its asset's name. Both are read.
- **Three things a reader has to know, and the page says each.** A member
  has 45 days to report and some take longer, so the filed date is shown
  beside the traded one with the gap. The amount is a band the form offers,
  never a figure. And whose account it was is given only when the report's
  owner column can be read off reliably; after a description long enough
  to have run on to a second line it is left unstated, because a guess
  would put a spouse's trade in a member's name.
- **An amended report restates the trade it corrects.** The two are told
  from two trades only by being the same in every published field, and
  then the newer filing stands.
- **A night reads at most 200 new reports inside 110 seconds** (sixty took
  32), newest first, so the first three nights fill in the year and after
  that a night has a handful. A report that does not answer is asked for
  again; a scanned or missing one is written off once. It stands down after
  four failures in a row, and it will not run at all without its PDF
  reader, because without one every report would look scanned and be
  written off for good.
- **Free to every reader, never behind the paywall, and whether to carry it
  at all is the owner's decision.** The statute that makes these reports
  public, 5 U.S.C. 13107, makes it unlawful to obtain or use one for any
  commercial purpose other than by news and communications media for
  dissemination to the general public. Every site that republishes these
  reports rests on that exception. This one sells subscriptions, so the
  section is published in the public tree, shown to everyone, kept out of
  the gated store and out of anything a subscriber gets that a visitor does
  not. That is the careful reading, not a legal opinion, and the owner may
  prefer not to carry it.

## The record, the on-watch rule, and the research ledger (2026-11-26)

The follow-through page lists every breakout a screen showed. Nothing counted
them into a verdict, and nothing happened to a screen whose breakouts stopped
paying. Now both.

- **The record** is `market/record.json`, built by `publish/record.py` from
  the follow-through payload the nightly already computes. Nothing is found
  or measured a second time, so the scoreboard cannot disagree with the list.
  For each screen and each horizon (5, 20 and 60 sessions) it gives how many
  breakouts reached the horizon, how many were up, how many closed at or
  above the pivot they cleared, the average and median move, and the
  benchmark's move over the same sessions. It is counts and rates only, never
  a name, and it is public. What is gated did not change.
- **The rule**, applied by code and printed on the page in these numbers:
  a screen is judged at 20 sessions after each breakout, over the same 180
  days follow-through covers. It takes 12 breakouts that have run their 20
  sessions to judge one; fewer is "too few to judge", which is not a
  verdict. A judged screen is **on watch** when fewer than 50% of those
  breakouts were up at 20 sessions **and** the median breakout trailed the
  benchmark over the same sessions. Both, not either: a screen that beat a
  falling market is doing its job, and so is one that lags a roaring market
  while most of its breakouts rise. Otherwise it is holding.
- **On watch is a label and nothing else.** The screen is not hidden, not
  reordered and loses no name. The label and the numbers behind it show on
  the record page, on the screen's own page and in one line on the front
  page. It comes off by the same rule on the first night the numbers no
  longer meet it. There is no memory.
- **The only baseline is the benchmark** over the same sessions. There is no
  control group of stocks that did not break out, and the page says so. The
  price history carries no delisted companies, so the figures are flattered;
  the rule is applied to them as they are. With no benchmark figure on file a
  screen cannot be put on watch.
- **The shape screens have no record.** Follow-through cannot rebuild a flag,
  wedge, triangle or squeeze from history, so those six are "too few to
  judge" with nothing counted, and the page says that is not the same as
  holding. A new screen is counted from whatever follow-through holds for it
  and is "too few to judge" until twelve of its breakouts have run.
- **The research ledger** is `research/ledger.yaml`, validated by
  `publish/ledger.py` and published as `research/ledger.json`. One entry a
  question the project put to real data: what was measured, the result, a
  verdict from held, refuted, refused, adopted or open, and where in the
  repository the measurement is written down. Failures stay. An entry may
  only state what the repository already records; an open one says what it
  is waiting for. History before November was squashed, so the earliest
  entries carry the date their result entered the repository.

## An MCP endpoint, public pages only (2026-11-26)

- **`/api/mcp` lets a reader's own AI ask the site.** It speaks the Model
  Context Protocol over HTTP: a client POSTs JSON-RPC and gets JSON back.
  Seven read-only tools: the edition, the list of screens, one screen, one
  company, earnings, the market's state, and a company search. `/mcp` is the
  page that explains it and carries the one-line connect command.
- **Hand-rolled, not the SDK.** The SDK's HTTP transport is written around a
  Node request and response and a table of sessions. A Next route handler on
  a serverless platform has neither. What this server needs of the protocol
  is five methods, and they are in `web/lib/mcp/protocol.ts` with no
  dependency.
- **Stateless.** No session id is issued, no stream is held open, GET and
  DELETE answer 405. Revisions 2025-06-18, 2025-03-26 and 2024-11-05 are
  accepted and a client asking for anything else is offered the newest.
  Batches are answered, up to twenty messages: 2025-03-26 has them,
  2025-06-18 removed them, and a server that keeps nothing between requests
  cannot know which a client negotiated, so it takes the lenient reading.
- **Public only, for now.** Every tool reads through the loaders the public
  pages use, from the published tree, which never holds the paid half. A
  screen answers with the same free rows its page shows and the true count
  at each stage, and says how many are withheld. A test compares
  `get_screen` with the published `screens/<key>.json` on every screen. The
  reason is that there is nobody to check: a browser session does not travel
  with an AI client, so the endpoint cannot tell a subscriber from anyone
  else, and it is left open with no key.
- **What keeps an open door safe**: nothing behind it writes; a request is
  at most 64 KB; an answer is at most 14,000 characters, and a longer one is
  replaced by a short message saying how to ask for less, never cut in the
  middle; symbols and screen keys are checked against a pattern and against
  the published list before anything is read; one address gets 120 requests
  a minute per server instance, which is a brake on a runaway loop and not a
  quota; answers are never cached. Any origin may call, because there are no
  credentials for an origin to borrow.
- **A subscriber's version is not built, and is the owner's to approve.** It
  would need a token a subscriber copies from their settings and sends as a
  bearer header, a table in Supabase to hold it (hashed, per subscriber,
  revocable, with a last-used time), a check of that subscriber's standing
  on each request, and the tools reading the paid tree for a valid token.
  That is a change to the Supabase schema and to who can reach paid data,
  so nothing here touches either.

## Price levels, a reclaim screen, and when the indexes disagree (2026-11-26)

- **Anchored VWAP** (`patterns/avwap.py`): the average price paid since the
  last report, since a live setup cleared its level, and since the year's
  first session. Computed from daily bars, each session's typical price
  weighted by its volume, and labelled "from daily bars" wherever it is
  shown, since a true VWAP needs every trade. The report's session is the
  heavier of the report day and the day after, because the source gives
  the day and not the hour. Drawn on the stock chart.
- **Prior-week high and low** sit with a stock's levels, with its normal
  day's range beside them.
- **Reclaim** (`patterns/reclaim.py`, dials in `patterns/params.py`): the
  daily version of a sweep. A session trades under the previous calendar
  week's low and a close comes back above it. Nothing is fitted, so its
  whole history replays from bars and its record starts measured rather
  than empty; the replay uses the same rule on each past day's own bars.
- **Index divergence** (`rankings/indexes.py`): one sentence on the breadth
  page when one of the indexes closes at a 20-session extreme and the
  others do not. Nothing when they agree.

## Options volume, a volatility line, and the morning's movers (2026-11-26)

- **Options volume** (`catalysts/optvol.py`): read off the chains the
  nightly already downloads, in the same pass as gamma, so no request is
  added. Only volume from the chain's latest session counts, since Yahoo
  shows a contract's last day traded. A contract is unusual at twice its
  open interest and at least 500 contracts; the board lists names with
  2,000 or more. Gated as the gamma board is: a few rows free, the rest
  for subscribers.
- **VIX against VIX3M** (`catalysts/volatility.py`), one line beside the
  regime. Calm under 15 and a ratio under 0.90; uneasy from 20 or 0.95;
  stressed from 30 or a ratio of 1, when near-term fear is priced above
  the three-month.
- **Before the bell**: the morning earnings run posts the names on a screen
  moving 3% or more before the open, up to eight each way, to the edition
  room once a day. Discord only, since which screen a name is on is the
  paid half, and the post says these are quotes in thin trading.

## Two things taken from Market Desk's own fixes (2026-11-27)

- **CPI and the jobs report are kept from the BLS schedule** as well as read
  from FRED (`catalysts/releases.py`, `BLS_SCHEDULE`). FRED lists a release
  only a few weeks ahead, so the calendar and the week ahead never showed
  more than the next print. The BLS had all of 2027 out. FRED still wins on
  any date it lists, since it hears first when a release is moved; the kept
  dates fill what it does not list yet. The nightly warns 45 days before
  they run out.
- **The chain stage has a clock** (`catalysts/chains.py`): forty-five minutes
  for the whole sweep, the largest companies asked first, so a night when a
  source answers slowly costs the smallest names their chain and not the
  whole run. Once Yahoo stands down OCC is not asked either, since its book
  has nothing to join to, and OCC itself stands down after three silences
  in a row, not eight.

## The desk's sentence per name, and its gap fade watch (2026-11-27)

Market Desk's export went to schema 1.9 with two additive blocks, and both are
now read.

- **`stories`**: the one sentence the desk's brief leads each ranked name
  with. It is shown at the top of a stock page's "Flagged by the market sweep"
  section, marked as the desk's brief and dated by the run it came in, and
  flagged when that run is old. It is cut to the site's own names, and cut at
  280 characters if it ever runs past the one line the contract promises. A
  name without one has none: the desk's brief only ranks a few dozen names a
  night. Stories are about one night, so a later run without them clears them.
- **`gap_fade`**: liquid names that gapped with no filing and no results
  behind the move, eight a side, with the desk's own 90-day record for each
  side. It has its own page, `/market/gap-fade`, public. Names the site does
  not follow are kept, without a link, because the list is the desk's. The
  record line says "too few readings" while the desk marks a slice thin, and
  never calls the list trades: the desk itself never scores it.

## Market holidays are known, not inferred (2026-11-27)

The night after Thanksgiving the nightly's gate took the holiday for a session
nobody had published. Its only guard for holidays was "the data branch was
written in the last four hours", and by 1:42am Friday it had been a day. So it
rebuilt Wednesday's edition for forty minutes and posted it to Discord a
second time, with the briefing and six earnings cards, under a "1 day behind"
warning.

The NYSE's full closures for 2026 and 2027 are now in
`data/market_calendar.py`, and the gate keeps the same list in bash because it
runs before the checkout. `tools/test_calendar.py` fails if the two differ and
runs the gate's own lines against the clock of that night. The pre-publish
staleness check and the morning line use the calendar too, so the line written
on a Wednesday before Thanksgiving is for Friday. The nightly log warns 45 days
before the list runs out. The four-hour guard stays for a closure nobody listed.

## An expiry's volatility reading stays near the money (2026-11-28)

The first full night on OCC's books put Marten Transport top of the High IV
page at 494%, with GRNT, NTST and FCPT near 400%. Each was a thin chain: its
six nearest strikes a side reached deep in the money, where a wide two-sided
quote (7.90 by 11.50 on a 7.50 call, stock at 11.77) passes the "believed"
test and implies a volatility near the 500% ceiling. A strike now has to be
within 25% of the price to count towards an expiry's reading. Those four
expiries have no reading inside that band, so the names drop off the page
rather than show a wrong number. The same morning, with and without the band:
no expiry of AAPL, NVDA, TSLA, SPY, SMCI, GME, MSTR or F changed. Gamma is
untouched; it reads every contract.
