# Where things stand

Written 13 September 2026, while nightly run #6 was still backfilling.
Read this first when you come back.

---

## The one thing to know

**The `data` branch is currently holding demo data, not real prices.**

Nightly run #1 finished in 65 seconds, reported success, and pushed a
fixture. The runs after it failed on a poisoned cache. Run #6 is the
first one that can actually work, and it takes about two and a half
hours because it backfills 900 days from nothing.

So: **do not connect Vercel until a nightly run has finished green.** If
you connect it now, the public site will serve invented tickers with
invented prices. The site labels them honestly — every page carries a
"Demo data" banner — but that is not what you want strangers to see.

There is now a check that stops this happening again. Before the nightly
pushes anything, it reads what it built and refuses to publish unless
the file says `live`. See "Nightly" below.

---

## How to check the nightly

Open <https://github.com/joeylampasona/web-app/actions>.

Run #6 is the one to watch. Three outcomes:

**Green, and it took hours.** That is the real thing. Verify it:

```
curl -s https://raw.githubusercontent.com/joeylampasona/web-app/data/meta.json | head -c 400
```

You want `"data_source":"live"` and a `universe_count` in the low
thousands — about 2,100. If you see `"synthetic_demo"` or a count near
500, it is still the fixture.

**Green in about a minute.** Something is wrong. A real run cannot be
that fast. Check `meta.json` as above before believing it.

**Red.** Open the run and find the step with the X. The steps are named
so the failure names itself: `universe`, `rank`, `scan`, `catalysts`,
`publish`, `verify-output`, `data-branch`.

Once one run is green, every run after it is incremental — a few minutes,
because the price database is cached between runs.

---

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

### Now, while the nightly runs

Nothing. Let it finish.

### When the nightly is green

**Step 1 — verify it is real.** The `curl` command above. Look for
`"data_source":"live"`.

**Step 2 — merge this branch.** On GitHub, open a pull request from
`claude/build-blhvg3` into `main` and merge it. That brings in the share
image, accounts, and the publish guard.

**Step 3 — connect Vercel.**

1. Go to <https://vercel.com> and sign in with GitHub.
2. **Add New → Project**, pick `joeylampasona/web-app`.
3. Set **Root Directory** to `web`. This matters — without it the build
   will not find anything.
4. Deploy.

Vercel will run `npm run vercel-build`, which downloads the `data`
branch and then builds the site. If the data branch is missing or empty
the build fails loudly with instructions rather than shipping an empty
site.

**Step 4 — make the nightly refresh the live site.**

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

**Multi-year screen is thin.** You chose option A: leave it. Polygon's
free tier serves about two years of history, and this screen looks for a
lid that has held a year or more, so there is barely room for a breakout
to sit after the base. The last run on real data returned 42 setups,
every one of them `forming`.

I shortened the screen's window from 104 weeks to 78 — as far as it can
go and still mean "multi-year". **Whether that is enough, I do not know
yet**: no real run has finished since the change. Check this screen when
the nightly goes green. If it still shows nothing but `forming`, that is
the history being short, not the screen being broken, and it fixes
itself as the nightly accumulates days. Getting it working sooner means
a paid Polygon tier — your call, not one I will make.

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
