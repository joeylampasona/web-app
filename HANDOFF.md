# Where things stand

Written 13 September 2026. Read this first when you come back.

---

## Where this got to

**The nightly works and the data branch is carrying real market data.**
Run #7, 2,129 names, live prices, every screen populated. Vercel is no
longer blocked — you can connect it whenever you like.

It took seven runs. Run #1 published a fixture in 65 seconds and called
it a success. Runs #2 to #5 died on a poisoned cache. Run #6 fetched
prices for 1h49m, built a universe of *zero* because SEC refused every
share-count request, published an empty site and went green. Run #7,
with a contactable `EDGAR_USER_AGENT`, worked.

Three guards now stand where those went wrong, and all three were added
because something reported success while doing the wrong thing:

- `cli universe` exits non-zero when nothing survives the funnel, instead
  of printing a suggestion and returning 0.
- SEC being unreachable raises rather than returning an empty dict behind
  a log line nobody prints. One company with no filed share count is
  ordinary and still degrades quietly; SEC refusing everything is not.
- Before the nightly publishes, it reads what it built: provenance, schema
  validity, **and** whether there is actually anything in it. A universe
  under 500 names or an empty set of screens stops the run.

### To check any future run

```
curl -s https://raw.githubusercontent.com/joeylampasona/web-app/data/meta.json | head -c 300
```

`"data_source":"live"` and a `universe_count` near 2,100. A run that
finishes in about a minute did not do the work — check this before
believing a green tick.

How long a run takes depends on what is cached. Prices cache between
runs; share counts and industries cache for 30 days. A normal night is a
few minutes. The first run after a month is closer to half an hour.

## What was built since we last spoke

Three commits on `claude/build-blhvg3`.

### 1. Share now sends a picture

Sharing used to send a link. On a phone that renders as a grey rectangle
with a domain in it, so the thing you were sharing — the chart, the
pivot, the numbers — was invisible until someone tapped through.

It now draws a PNG: the header line, a screenshot of the chart you are
looking at, the metric rows, and the disclaimer. No new dependency; it
is the canvas the browser already has plus the chart library's own
screenshot call.

You asked what it would cost to build this now rather than later. The
answer turned out to be: less than deferring it. The chart component had
to expose its screenshot handle either way, and doing that while the
share code was open was cheaper than coming back to it cold.

### 2. Accounts (Supabase), and the four features waiting on them

You picked Supabase. It is wired up.

Sign-in is a magic link: someone types an email, gets a one-time link,
clicks it, they are in. No password for this app to store, forget, or
leak.

The four gated features now work:

- **Watchlist** — rows live in a database against the account, so the
  list is the same on your phone and your desktop. Anything saved in a
  browser before accounts existed gets folded in on first sign-in.
- **Saved screens** — stores the detector and every dial position.
- **Export** — writes the CSV it had been promising. Every published
  column, nothing that is not published.
- **X-ray** — opens with the rest.

**This is switched off until you set it up.** With no Supabase project
configured, the site runs exactly as it does today: everything open, the
four features closed, and the sign-up sheet saying accounts are not
switched on rather than collecting an address it cannot mail anything to.

Setting it up is in "What you need to do" below.

### 3. The nightly checks its own output

Described above. Also fixed a security advisory in a CSS tool that ships
under Next.js, and a 404 the browser was firing on every page load
looking for an icon that did not exist.

---

## What you need to do

### Connect Vercel

Nothing blocks this any more.

1. Go to <https://vercel.com> and sign in with GitHub.
2. **Add New → Project**, pick `joeylampasona/web-app`.
3. Set **Root Directory** to `web`. This matters — without it the build
   will not find anything.
4. Deploy.

Vercel will run `npm run vercel-build`, which downloads the `data`
branch and then builds the site. If the data branch is missing or empty
the build fails loudly with instructions rather than shipping an empty
site.

### Make the nightly refresh the live site

Pushing to the data branch does not redeploy on its own, so without this
the site would serve one night's numbers forever.

1. In Vercel: **Project Settings → Git → Deploy Hooks**. Create one.
   Name it `nightly`, branch `main`. Copy the URL.
2. In GitHub: **Settings → Secrets and variables → Actions → New
   repository secret**. Name it `VERCEL_DEPLOY_HOOK`, paste the URL.

The workflow already calls it and does nothing if the secret is absent,
so nothing breaks before you get to this.

### When you want accounts switched on

This is independent of everything above — do it whenever.

1. Go to <https://supabase.com>, sign up, create a project. Free tier is
   enough. Pick a region near your readers.
2. In the project: **SQL Editor → New query**. Paste the entire contents
   of `supabase/schema.sql` from this repo and run it. That creates the
   two tables and the rules that keep one person's rows private from
   everyone else's.
3. In the project: **Project Settings → API**. Copy the **Project URL**
   and the **anon public** key.
   - Copy the one labelled **anon**, not **service_role**. The
     service_role key bypasses every privacy rule. It must never go into
     the website.
4. In Vercel: **Project Settings → Environment Variables**. Add two:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | the Project URL |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the anon public key |

5. In Supabase: **Authentication → URL Configuration**. Set **Site URL**
   to your Vercel address, and add `https://your-site.vercel.app/auth/callback`
   under **Redirect URLs**. Without this the magic links will not work.
6. Redeploy in Vercel. Accounts are live.

To try it on your own machine first, copy `web/.env.example` to
`web/.env.local` and fill in the same two values. That file is
gitignored, so it cannot be committed by accident.

**A note on the anon key.** It is public on purpose — it is compiled
into the pages and anyone can read it. It identifies the project, not a
person. Every table is behind a rule that says "you may only touch rows
where `user_id` is you", so that key on its own reads and writes nothing.

**Supabase's free tier pauses a project after a week of no activity.**
Once real people are using it that will not happen, but if you set this
up and then leave it alone for a fortnight, expect to click "restore" in
the Supabase dashboard.

---

## Still open

**Legal review.** Every page carries the disclaimer, no page uses banned
language, and every return figure is badged PROVISIONAL because the
universe is not survivorship-safe. That is me being careful, not a
lawyer signing anything off. Before you take money, or before this grows
past people you know, have a securities lawyer read the disclaimer and
the Learn pages. I cannot do that part.

**Multi-year screen — settled, it works now.** This was open; it is not
any more. You chose option A, leave the screen alone, and the fix turned
out to be one number rather than a redesign.

Shortening the window from 104 weeks to 78, measured on live data:

| | 104 weeks | 78 weeks |
|---|---|---|
| Total | 42 | 101 |
| forming | 42 | 28 |
| fresh breakouts | 0 | 2 |
| climbing | 0 | 13 |
| played out | 0 | 58 |

At 104 weeks the window was almost as long as all the history Polygon's
free tier serves, so there was nowhere for a breakout to sit after a
year-long base and everything stayed `forming` forever. At 78 there is
room. Nothing about the screen's logic changed.

The two-year history limit is still there — this stops it swallowing
the whole screen, it does not remove it. The window can go back toward
104 once the nightly has banked enough days.

**Two years of history generally.** Confirmed by probing: Polygon's free
Basic plan returns 403 for dates older than roughly two years. This
limits backtests, and it is why the backtest results carry the caveat
they do.

---

## Things that bit us, so they do not bite again

Worth knowing, because the pattern repeated:

**Three separate times, something reported success while doing the wrong
thing.** A cached position marker made the backfill fetch zero prices and
report a clean run. Industry lookups returned nothing and every stock
came back "Unclassified". The nightly published a fixture and went green.

In each case the fix was not only to correct the instance but to make
that failure loud: the database now refuses to mix one data source's
prices with another's tickers; the funnel counts "has a price on this
date" as its own visible step; the nightly checks what it actually built
before publishing it.

If you ever see something succeed suspiciously fast, that is the smell.
Check the output, not the green tick.

**Credentials in screenshots.** Early on I gave you commands that echoed
your API key and GitHub token to the screen, and you screenshotted them.
That was my fault, and both were rotated. Standing rule: before
screenshotting a terminal, scroll past anything where you pasted a
secret. And if a command I give you ever prints a credential, say so —
it is a bug in the command.

---

## Where things live

| What | Where |
|---|---|
| Pipeline settings | `config/settings.yaml` |
| Your local overrides (gitignored) | `config/settings.local.yaml` |
| Detector thresholds | `patterns/params.py` |
| Account database schema | `supabase/schema.sql` |
| Website env template | `web/.env.example` |
| Nightly job | `.github/workflows/nightly.yml` |
| Every decision and why | `DECISIONS.md` |

Run the pipeline by hand with `python -m cli universe --refresh`, then
`rank`, `scan`, `catalysts`, `publish`. Run the site with `npm run dev`
inside `web/`.
