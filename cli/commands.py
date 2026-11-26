"""One function per subcommand. Each prints something a human can read."""
from __future__ import annotations

import datetime as dt

import json
import os

from data import settings, store


def _conn():
    return store.open_db()


def _banner(title: str) -> None:
    print()
    print(title)
    print("─" * len(title))


def cmd_universe(args) -> int:
    from data.edgar import EdgarUnavailable

    from data import universe
    conn = _conn()
    run = store.start_run(conn, "universe")
    try:
        if args.refresh:
            def progress(day: dt.date, count: int) -> None:
                if count:
                    print(f"  {day}  {count:,} bars")
            def notice(text: str) -> None:
                print(f"  → {text}")

            funnel = universe.refresh(conn, progress=progress, notice=notice,
                                      reset=getattr(args, "reset", False))
        else:
            def notice(text: str) -> None:
                print(f"  → {text}")

            funnel = universe.build(conn, notice=notice)
    except universe.ProviderMismatch as exc:
        store.finish_run(conn, run, "failed", str(exc))
        _banner("Stopped — provider mismatch")
        print(f"  {exc}")
        return 1
    except EdgarUnavailable as exc:
        store.finish_run(conn, run, "failed", str(exc))
        _banner("Stopped — SEC would not answer")
        print(f"  {exc}")
        print()
        print("  Every company's market cap is its share count times its price, so")
        print("  without SEC there are no market caps and the whole universe filters")
        print("  down to nothing. Stopping here rather than publishing an empty site.")
        return 1
    except Exception as exc:                      # noqa: BLE001
        store.finish_run(conn, run, "failed", str(exc))
        raise
    store.finish_run(conn, run, "ok", f"{funnel.final} survivors")
    # Kept where the published tree can read it. An alarm that exists only as a
    # line in a job log is an alarm nobody sees: the logs are long, they scroll,
    # and the one time this fired it was Meta going missing for weeks with
    # nothing anywhere saying so.
    store.set_kv(conn, "universe.lost_leaders",
                 json.dumps(funnel.lost_leaders, separators=(",", ":")))
    store.set_kv(conn, "universe.lost_leader_reasons",
                 json.dumps(funnel.lost_leader_reasons, separators=(",", ":")))
    _banner("Universe")
    print(funnel.render())
    print()
    print(f"  provider: {settings.get('data.provider')}"
          f"    database: {settings.db_path()}")
    if funnel.final == 0:
        # Not a success. A run that ends with no universe produces empty screens,
        # an empty market page and an empty search, and the stages above say
        # which filter did it. Exit non-zero so a nightly job stops here instead
        # of publishing that.
        print("\n  Nothing survived — see which stage above dropped everything.")
        print("  If every stage is 0, the database has no bars yet: run --refresh.")
        return 1
    return 0


def cmd_rank(args) -> int:
    from data.market import load
    from rankings import groups, rotation, rs, breadth
    conn = _conn()
    run = store.start_run(conn, "rank")
    market = load(conn)
    bundle = rs.Bundle(market)
    numeric = bundle.numeric_now()

    _banner(f"Top 20 by RS rating — {market.as_of}")
    print(f"  {'#':>3}  {'Ticker':<8}{'Name':<26}{'RS':>4}{'Δ1m':>7}{'Close':>10}{'Quadrant':>14}")
    print("  " + "─" * 76)
    ordered = sorted(numeric.items(), key=lambda kv: -kv[1])[:20]
    for i, (symbol, rating) in enumerate(ordered, 1):
        ref = market.refs.get(symbol)
        delta = bundle.change(symbol, "m1")
        quadrant = rotation.quadrant_for(rating, delta) or "—"
        close = market.last_close(symbol) or 0.0
        print(f"  {i:>3}  {symbol:<8}{(ref.name if ref else '')[:25]:<26}{rating:>4}"
              f"{('—' if delta is None else f'{delta:+d}'):>7}{close:>10,.2f}"
              f"{rotation.LABELS.get(quadrant, quadrant):>14}")

    not_ranked = [s for s, v in bundle.now.items() if not isinstance(v, int)]
    if not_ranked:
        print(f"\n  {len(not_ranked)} names return \"not ranked yet\" "
              f"(too little history): {', '.join(sorted(not_ranked)[:10])}")

    industries = groups.aggregate(market, bundle, "industry")
    _banner(f"Industries with {settings.get('rankings.min_group_members', 10)}+ members")
    print(groups.render_table(industries))

    themes = groups.aggregate(market, bundle, "theme")
    _banner("Themes")
    print(groups.render_table(themes))

    etfs = rs.etf_ratings(market)
    if etfs:
        _banner("Sector ETFs, ranked separately")
        for row in etfs[:6]:
            print(f"  {row['symbol']:<6}{row['rs_rating'] or 0:>4}"
                  f"  excess {row['excess_return_pct']:+.1f}%")

    b = breadth.compute(market)
    _banner("Breadth")
    for card in b["cards"]:
        unit = "%" if card["unit"] == "percent" else ""
        wow = card["wow_delta"]
        print(f"  {card['label']:<30}{card['value']:>8}{unit:<2}"
              f"  week-over-week {('—' if wow is None else f'{wow:+.2f}')}")

    rot = rotation.compute(market, bundle)
    _banner("Rotation quadrants")
    for kind in ("industries", "themes", "stocks"):
        counts = rot[kind]["counts"]
        print(f"  {kind:<12}" + "  ".join(
            f"{rotation.LABELS[q].lower()} {counts[q]}" for q in rotation.QUADRANTS))
    store.finish_run(conn, run, "ok", f"{len(numeric)} ranked")
    return 0


def cmd_scan(args) -> int:
    from data.market import load
    from patterns import scan, stages
    from patterns.params import SCREENS
    from rankings import rs
    conn = _conn()
    run = store.start_run(conn, "scan")
    market = load(conn)
    bundle = rs.Bundle(market)
    result = scan.run(market, bundle)
    changes = scan.diff(conn, result)

    _banner(f"Screens — {market.as_of}")
    header = f"  {'Screen':<26}{'Total':>7}" + "".join(
        f"{stages.LABELS[s]:>17}" for s in stages.ORDER)
    print(header)
    print("  " + "─" * (len(header) - 2))
    for key, setups in result.screens.items():
        counts = result.counts(key)
        print(f"  {SCREENS[key].name:<26}{len(setups):>7}" +
              "".join(f"{counts[s]:>17}" for s in stages.ORDER))

    _banner("First 10 setups")
    print(f"  {'Ticker':<8}{'Screen':<13}{'Stage':<16}{'RS':>5}{'Pivot':>10}"
          f"{'vs pivot':>10}{'Tighten':>9}{'Dry-up':>8}  Flags")
    print("  " + "─" * 92)
    shown = 0
    for key, setups in result.screens.items():
        for s in setups:
            if shown >= 10:
                break
            rs_text = s.rs_rating if isinstance(s.rs_rating, int) else "—"
            print(f"  {s.symbol:<8}{key:<13}{s.stage:<16}{rs_text:>5}{s.pivot:>10,.2f}"
                  f"{(s.now_vs_pivot_pct or 0):>9.1f}%"
                  f"{(s.tightening_atr_ratio or 0):>8.2f}×"
                  f"{(s.volume_dryup_ratio or 0):>7.2f}×  {', '.join(s.flags) or '—'}")
            shown += 1
        if shown >= 10:
            break

    _banner("Daily diff")
    if changes["first_run"]:
        print("  First scan on this database — nothing to compare against yet.")
    for key, block in changes["screens"].items():
        print(f"  {key:<12} broke out {len(block['broke_out_today']):>3}"
              f"   newly forming {len(block['newly_forming']):>3}"
              f"   left {len(block['left']):>3}")
    store.finish_run(conn, run, "ok",
                     ", ".join(f"{k}={len(v)}" for k, v in result.screens.items()))
    return 0


def cmd_catalysts(args) -> int:
    from catalysts import events as ev, iv as ivmod
    from data.adapters import get_adapter
    from data.market import load
    from patterns import scan
    from rankings import rs
    conn = _conn()
    run = store.start_run(conn, "catalysts")
    market = load(conn)
    bundle = rs.Bundle(market)
    result = scan.run(market, bundle)
    population = sorted({s.symbol for s in result.all_setups()})
    adapter = get_adapter()

    # The Market Desk sweeps the whole market overnight for filings, insider
    # clusters, tape anomalies and earnings dates. Ingested before the calendar
    # is built so its dates take precedence over our scraped fallback.
    from data import marketdesk
    desk_dates: dict = {}
    if marketdesk.enabled():
        try:
            marketdesk.ingest(conn, market.as_of,
                              notice=lambda m: print(f"  → {m}", flush=True))
            desk_dates = marketdesk.earnings_dates(conn)
        except marketdesk.DeskSchemaChanged as exc:
            # Loud, because it means someone changed the contract and the site
            # would otherwise quietly carry on with yesterday's signals.
            print(f"  → Market Desk NOT ingested: {exc}", flush=True)
        except marketdesk.DeskUnavailable as exc:
            print(f"  → Market Desk unavailable: {exc}", flush=True)
    else:
        print("  → Market Desk not configured; skipping.", flush=True)

    # Every stock with a page, not just the ones on a screen today. A roadmap
    # is a fact about the company — when it reports, when it goes ex-dividend —
    # and it does not stop being true because the stock is not currently in a
    # base. 1,329 of the 2,145 published pages showed an empty roadmap for that
    # reason alone, which reads as a fault rather than a boundary.
    #
    # It is affordable because the calendar's cost is not per-name. Dividends
    # and splits come market-wide in one paged call each and are filtered here,
    # so they widen for free. Earnings are per-ticker, but the seven-day cache
    # means a steady night asks about a seventh of the universe and keeps what
    # arrives. Insider filings and implied volatility stay on `population`:
    # those genuinely cost a request each.
    from publish import health
    heard = health.Listener(lambda m: print(f"  → {m}", flush=True))
    heard.keep("earnings_dates", "names fetched tonight")
    calendar = ev.build(market, market.universe, adapter, desk_earnings=desk_dates,
                        conn=conn, notice=heard)
    ev.attach(calendar, result.all_setups())
    if "earnings_dates" in heard.kept:
        # The stage's own sentence, kept word for word. Its "N of M" is how
        # many names have a date at all, which is the figure that matters.
        sentence = heard.kept["earnings_dates"].split(": ", 1)[-1]
        have, total = health.counted(sentence)
        health.record(conn, "earnings_dates", market.as_of,
                      sentence[:1].upper() + sentence[1:],
                      asked=total, answered=have)

    # Form 4s for the names on a screen. Filings never change once filed, so
    # this only ever fetches ones we have not read; the first run is the slow
    # one and every run after it is nearly free.
    from data import insiders
    from data.edgar import EdgarUnavailable
    try:
        def insider_progress(done: int, total: int, added: int,
                             parsed: int) -> None:
            print(f"  → insider filings {done:,}/{total:,} — "
                  f"{added:,} read, {parsed:,} transactions", flush=True)

        print(f"  → Reading insider filings for {len(population):,} names. "
              f"The first run takes a while; later ones read only what is new.",
              flush=True)
        added, parsed = insiders.fetch(conn, population, progress=insider_progress)
        print(f"  → {added:,} new Form 4 filings read, "
              f"{parsed:,} transactions parsed.", flush=True)
        if added and not parsed:
            # The shape of the bug that hid for weeks: filings fetched fine and
            # every one of them yielded nothing. Reading a document SEC serves
            # as HTML does exactly this, and "filings read" alone looks healthy.
            print("  → WARNING: every filing parsed to zero transactions. "
                  "That is a parsing or URL fault, not a quiet week.", flush=True)
    except EdgarUnavailable as exc:
        # A missing industry is a worse page; missing insider data is a missing
        # section. Neither is worth failing a nightly run over.
        print(f"  → Insider filings skipped: {exc}", flush=True)

    # The one hand-kept list here. Said out loud every run, because the whole
    # case for keeping it by hand is that running out cannot happen silently.
    from catalysts import fomc as fomcmod
    fomc_state = fomcmod.status(market.as_of)
    print(f"  → {'FOMC LIST NEEDS ATTENTION: ' if fomc_state['stale'] else ''}"
          f"{fomc_state['message']}", flush=True)

    # When the data comes out, not when the Fed meets — see catalysts/releases.
    # One call, and the whole thing is optional: no key, no tab, no failure.
    from catalysts import releases as rel
    try:
        found = rel.fetch(market.as_of, notice=lambda m: print(f"  → {m}", flush=True))
        if found:
            rel.store(conn, found)
            gone = rel.prune(conn, market.as_of)
            if gone:
                print(f"  → {gone:,} past release dates dropped.", flush=True)
    except Exception as exc:                      # noqa: BLE001
        print(f"  → Data releases skipped: {exc}", flush=True)

    # Headlines, market-wide. Fetched once for everyone rather than per ticker:
    # five calls a minute would be three hours one name at a time.
    from catalysts import news as newsmod
    rows = newsmod.fetch(conn, notice=lambda m: print(f"  → {m}", flush=True))
    dropped = newsmod.prune(conn)
    print(f"  → {rows:,} headline rows written, {dropped:,} stale ones dropped.",
          flush=True)
    health.record(conn, "news", market.as_of,
                  f"{rows:,} headline rows written, {dropped:,} stale ones dropped.",
                  status="ok" if rows else "down")

    _banner(f"Upcoming events — {len(population)} tickers on a screen")
    upcoming = sorted(
        (e for rows in calendar.by_ticker.values() for e in rows
         if e.date >= market.as_of),
        key=lambda e: (e.date, e.ticker))
    print(f"  {'Date':<12}{'In':>5}  {'Ticker':<8}{'Type':<14}{'Status':<11}Note")
    print("  " + "─" * 76)
    for e in upcoming[:20]:
        note = ""
        if e.readthrough:
            note = f"read-through from {e.readthrough['from']} ({e.readthrough['tag']})"
        print(f"  {e.date.isoformat():<12}{e.days_until(market.as_of):>4}d  {e.ticker:<8}"
              f"{ev.TYPE_LABELS.get(e.type, e.type):<14}{e.confirmed:<11}{note}")
    owned = sum(1 for rows in calendar.by_ticker.values() for e in rows if not e.readthrough)
    through = sum(1 for rows in calendar.by_ticker.values() for e in rows if e.readthrough)
    print(f"\n  {owned} ticker-owned events, {through} read-through events, "
          f"{len(upcoming)} total in the window.")

    names = {s: (market.refs[s].name if s in market.refs else s) for s in population}
    # Gamma rides along on the option chains the IV reading already downloads,
    # so this costs no extra request. Stored here because publish never reaches
    # the network.
    # Analyst coverage. Capped per night: the universe over the freshness
    # window is the steady rate, but a cold cache would otherwise try every
    # name at once, which is exactly how the earnings scrape got itself
    # throttled before it was given one.
    # Which companies are in the S&P 500: fetched weekly, here because this
    # is the stage that reaches the network.
    from data import indexes as indexes_mod
    indexes_mod.refresh(conn, market.as_of, notice=lambda m: print(f"  → {m}", flush=True))

    # Trades by members of the House, from the Clerk's own filings: the
    # newest reports not yet read, capped a night and by the clock.
    from data import congress as congress_mod
    congress_mod.record(conn, market.as_of, congress_mod.refresh(
        conn, dt.date.today(), notice=lambda m: print(f"  → {m}", flush=True)))

    from catalysts import forecast as forecastmod
    asked_forecasts, kept_forecasts = forecastmod.fetch(
        conn, market.universe, limit=400,
        notice=lambda m: print(f"  → {m}", flush=True),
        priority=market.caps)
    health.record(conn, "forecasts", market.as_of,
                  (f"{kept_forecasts:,} of {asked_forecasts:,} asked about tonight "
                   f"came back with data." if asked_forecasts else
                   "Every name still had a fresh forecast; none asked about tonight."),
                  asked=asked_forecasts, answered=kept_forecasts)

    from catalysts import gamma as gammamod
    gamma_profiles: dict = {}
    iv_stats: dict = {}
    rows = ivmod.compute(calendar, population, names, adapter,
                         gamma_out=gamma_profiles, stats=iv_stats)
    # Said every night, not only on a bad one. The night the full-book source
    # began refusing, the fallback answered, both sections filled, and the
    # only trace was a slower run.
    wanted_chains = iv_stats.get("asked", 0) - iv_stats.get("no_event", 0)
    from_cboe = iv_stats.get("from_cboe", 0)
    joined = iv_stats.get("from_occ+yahoo", 0)
    full = from_cboe + joined
    short = iv_stats.get("from_yahoo", 0)
    other = iv_stats.get("chain_ok", 0) - full - short
    none = max(0, wanted_chains - iv_stats.get("chain_ok", 0))
    detail = (f"{full:,} full books ({from_cboe:,} from Cboe, {joined:,} from "
              f"OCC's open interest with Yahoo's quotes), {short:,} thinner "
              f"books from Yahoo alone, {none:,} with none.")
    if other > 0:
        detail = (f"{iv_stats.get('chain_ok', 0):,} of {wanted_chains:,} chains "
                  f"arrived, {none:,} with none.")
    # Judged by which book answered, not by the share that answered: plenty
    # of companies have no listed options at all, and counting those as
    # misses would call an ordinary night partial every night.
    status = "ok"
    if wanted_chains and not iv_stats.get("chain_ok", 0):
        status = "down"
    elif short > full:
        # Answered, but mostly with Yahoo's own open interest.
        status = "partial"
    health.record(conn, "options", market.as_of, detail, asked=wanted_chains,
                  answered=iv_stats.get("chain_ok", 0), status=status)
    print(f"  → option chains: {detail}", flush=True)
    try:
        from catalysts import cboe as cboemod
        tally = ", ".join(f"{k} {v:,}" for k, v in sorted(
            cboemod.OUTCOMES.items(), key=lambda kv: -kv[1]))
        if tally:
            print(f"  → cboe outcomes: {tally}", flush=True)
        if cboemod.standing_down():
            print(f"  → cboe refused {cboemod.REFUSALS_BEFORE_STANDING_DOWN} names "
                  f"in a row and was not asked about the rest.", flush=True)
        from catalysts import chains as chainsmod, occ as occmod, yf as yfmod

        def tallied(counter) -> str:
            return ", ".join(f"{k} {v:,}" for k, v in sorted(
                counter.items(), key=lambda kv: -kv[1]))
        for label, counter in (("occ outcomes", occmod.OUTCOMES),
                               ("yahoo chain requests", yfmod.CHAIN_OUTCOMES),
                               ("joined chains", chainsmod.OUTCOMES)):
            if counter:
                print(f"  → {label}: {tallied(counter)}", flush=True)
        if occmod.standing_down():
            print(f"  → OCC went unanswered {occmod.FAILURES_BEFORE_STANDING_DOWN} "
                  f"names in a row and was not asked about the rest; Yahoo's "
                  f"own open interest stood in.", flush=True)
        if yfmod.chains_standing_down():
            print(f"  → Yahoo answered 'too many requests' "
                  f"{yfmod.RATE_LIMITS_BEFORE_STANDING_DOWN} times in a row and "
                  f"was not asked for the remaining chains.", flush=True)
    except Exception:                             # noqa: BLE001
        pass
    # Persist before printing. This is the only stage allowed to reach the
    # network, so if these rows are not kept here they do not exist.
    if rows:
        ivmod.store(conn, rows, market.as_of)
    else:
        # Same reasoning as the gamma notice below: an empty High IV page and a
        # market with no rich options look identical from the outside.
        print("  → implied volatility: no name returned a usable chain. The "
              "High IV section will fall back to the last stored night.",
              flush=True)
    if gamma_profiles:
        kept = gammamod.store(conn, gamma_profiles)
        total_oi = sum(g.open_interest for g in gamma_profiles.values())
        print(f"  → gamma: {kept:,} names with open interest at strikes, "
              f"{total_oi:,} contracts outstanding.", flush=True)
    else:
        # Loud, because the failure mode is a section that renders empty while
        # everything reports fine. Open interest is the field most likely to
        # arrive as NaN, and a silent zero here looks identical to a market
        # with no options in it.
        # Which of the two it is, in numbers. "Either ... or" was honest and
        # useless: the fix for a throttled source and a source that dropped a
        # field are different, and a night of counts settles it in one line.
        print(f"  → gamma: of {iv_stats.get('asked', 0):,} names asked, "
              f"{iv_stats.get('no_event', 0):,} had no dated event, "
              f"{iv_stats.get('chain_error', 0):,} errored, "
              f"{iv_stats.get('chain_none', 0):,} returned nothing, "
              f"{iv_stats.get('chain_empty', 0):,} came back with no rows, "
              f"{iv_stats.get('chain_ok', 0):,} carried rows, "
              f"{iv_stats.get('no_spot', 0):,} had no underlying price.",
              flush=True)
        print("  → gamma: no name returned usable open interest. Either the "
              "source stopped supplying it or every chain was empty — the "
              "gamma section will be blank.", flush=True)
    _banner("High IV — ticker-owned dated events only")
    print(f"  {ivmod.COPY['subhead']}")
    print()
    print(f"  {'Ticker':<8}{'Event':<20}{'Date':<12}{'In':>5}{'IV':>8}{'Rich':>8}"
          f"  {'Band':<11}Dots")
    print("  " + "─" * 82)
    for r in rows[:15]:
        dots = "●" * r.dots + "○" * (int(settings.get("iv.dots", 5)) - r.dots)
        print(f"  {r.ticker:<8}{r.event_label[:19]:<20}{r.event_date.isoformat():<12}"
              f"{r.days_until:>4}d{100*r.catalyst_iv:>7.1f}%{r.iv_richness:>8.2f}"
              f"  {ivmod.BAND_LABELS[r.iv_band]:<11}{dots}")
    skipped = len(population) - len(rows)
    print(f"\n  {len(rows)} names qualify. {skipped} are absent — no listed options, or "
          f"no dated catalyst of their own.")
    print(f"  {ivmod.COPY['footer']}")
    store.finish_run(conn, run, "ok", f"{len(upcoming)} events, {len(rows)} IV rows")
    return 0


def _next_earnings_map(market, symbols):
    from catalysts import events as ev
    from data.adapters import get_adapter
    calendar = ev.build(market, symbols, get_adapter())
    out = {}
    for symbol in symbols:
        nxt = calendar.next_earnings(symbol)
        if nxt:
            out[symbol] = nxt.date
    return out


def cmd_backtest(args) -> int:
    from backtest import engine, metrics
    from backtest.settings import BacktestSettings
    from data.market import load
    from patterns.params import SCREENS
    conn = _conn()
    run = store.start_run(conn, "backtest")
    payload = {
        "screen": args.screen, "enter": args.enter, "positions": args.positions,
        "stop_pct": args.stop, "exit_rule": args.exit_rule, "risk": args.risk,
        "risk_pct": args.risk, "starting_capital": args.capital, "period": args.period,
        "skip_weak_markets": args.skip_weak, "skip_earnings_7d": args.skip_earnings,
    }
    payload.pop("risk")
    config = BacktestSettings.parse({k: v for k, v in payload.items() if v is not None})

    market = load(conn, include_all=True)
    earnings = _next_earnings_map(market, market.universe) if config.skip_earnings_7d else {}
    result = engine.run(market, config, earnings)
    summary = metrics.summarise(result)

    if getattr(args, "as_json", False):
        import json
        path = settings.out_dir() / "backtest" / "presets" / f"{config.hash()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, default=str), encoding="utf-8")
        print(json.dumps(summary, default=str))
        store.finish_run(conn, run, "ok", f"{len(summary['trades'])} trades")
        return 0

    _banner(f"Backtest — {SCREENS[config.screen].name}")
    print(f"  enter {config.enter} · {config.positions} positions · stop "
          f"{config.stop_pct:g}% · {config.exit_rule} · risk {config.risk_pct:g}% · "
          f"period {config.period}")
    print(f"  each position is about ${config.position_size(config.starting_capital):,.0f} "
          f"at {config.risk_pct:g}% risk with a {config.stop_pct:g}% stop")
    print()
    print(metrics.render(summary))

    _banner("Year by year")
    for row in summary["yearly"]:
        bar = "█" * max(0, min(40, int(abs(row["return_pct"]) / 2)))
        print(f"  {row['year']}{row['return_pct']:>9.2f}%  {bar}")

    _banner(f"Trades ({len(summary['trades'])}) — losers included")
    print(f"  {'Ticker':<8}{'Entry':<12}{'Price':>9}  {'Exit':<11}{'Price':>9}"
          f"{'Return':>9}{'R':>7}  Reason")
    print("  " + "─" * 86)
    for t in summary["trades"][:25]:
        print(f"  {t['ticker']:<8}{t['entry_date']:<12}{t['entry_price']:>9,.2f}"
              f"  {t['exit_date']:<11}{t['exit_price']:>9,.2f}{t['return_pct']:>8.2f}%"
              f"{t['r_multiple']:>7.2f}  {t['exit_reason']}")
    if len(summary["trades"]) > 25:
        print(f"  … and {len(summary['trades']) - 25} more")
    store.finish_run(conn, run, "ok", f"{len(summary['trades'])} trades")
    return 0


def _pipeline(conn, with_followthrough: bool = True):
    """The nightly sequence, shared by `publish` and `all`."""
    from backtest import engine, metrics
    from backtest.settings import BacktestSettings
    from catalysts import events as ev, iv as ivmod
    from data.adapters import get_adapter
    from data.market import load
    from patterns import followthrough, scan
    from patterns.params import BASE_SCREEN_KEYS
    from rankings import rs

    market = load(conn, include_all=True)
    bundle = rs.Bundle(market)
    result = scan.run(market, bundle)
    changes = scan.diff(conn, result)
    scan.nights(conn, result)
    adapter = get_adapter()

    population = sorted({s.symbol for s in result.all_setups()})
    # The Market Desk sweeps the whole market overnight for filings, insider
    # clusters, tape anomalies and earnings dates. Ingested before the calendar
    # is built so its dates take precedence over our scraped fallback.
    from data import marketdesk
    desk_dates: dict = {}
    if marketdesk.enabled():
        try:
            marketdesk.ingest(conn, market.as_of,
                              notice=lambda m: print(f"  → {m}", flush=True))
            desk_dates = marketdesk.earnings_dates(conn)
        except marketdesk.DeskSchemaChanged as exc:
            # Loud, because it means someone changed the contract and the site
            # would otherwise quietly carry on with yesterday's signals.
            print(f"  → Market Desk NOT ingested: {exc}", flush=True)
        except marketdesk.DeskUnavailable as exc:
            print(f"  → Market Desk unavailable: {exc}", flush=True)
    else:
        print("  → Market Desk not configured; skipping.", flush=True)

    # Every stock with a page, not just the ones on a screen today. A roadmap
    # is a fact about the company — when it reports, when it goes ex-dividend —
    # and it does not stop being true because the stock is not currently in a
    # base. 1,329 of the 2,145 published pages showed an empty roadmap for that
    # reason alone, which reads as a fault rather than a boundary.
    #
    # It is affordable because the calendar's cost is not per-name. Dividends
    # and splits come market-wide in one paged call each and are filtered here,
    # so they widen for free. Earnings are per-ticker, but the seven-day cache
    # means a steady night asks about a seventh of the universe and keeps what
    # arrives. Insider filings and implied volatility stay on `population`:
    # those genuinely cost a request each.
    calendar = ev.build(market, market.universe, adapter, desk_earnings=desk_dates,
                        conn=conn, notice=lambda m: print(f"  → {m}", flush=True))
    ev.attach(calendar, result.all_setups())
    # Read, never fetch: publish must not depend on Yahoo being up.
    #
    # This line used to call ivmod.compute, which fetches. It therefore asked
    # Yahoo for several hundred option chains a second time, minutes after the
    # catalysts stage had already asked for them — and on a night Yahoo
    # answered the second run with HTTP 429, every chain came back None, the
    # bare `except` inside compute swallowed it, and publish wrote zero rows
    # over the 567 the catalysts stage had just found. Every step reported
    # success.
    iv_rows, iv_as_of = ivmod.load(conn, market.as_of)
    if iv_as_of is not None and iv_as_of < market.as_of:
        print(f"  → implied volatility: using the {iv_as_of} set, "
              f"the most recent one stored.", flush=True)
    elif not iv_rows:
        print("  → implied volatility: nothing stored; the High IV section "
              "will be empty. Run the catalysts stage.", flush=True)
    from catalysts import gamma as gammamod
    gamma_rows = gammamod.load(conn, market.universe, market.as_of)
    from catalysts import forecast as forecastmod
    forecast_rows = forecastmod.load(conn, market.universe)

    backtests: dict[str, dict] = {}
    follow: dict = {}
    # Read from the cache the catalysts stage fills; publish never fetches.
    # Fetching is limited to names on a screen, because each one costs SEC
    # requests. Reading is not: a name that has left a screen still has the
    # filings we already read, and its page should still show them.
    from catalysts import news as news_mod
    from data import insiders as insiders_mod
    from data import marketdesk as desk_mod
    desk_rows = desk_mod.by_symbol(conn, market.universe)
    desk_run = desk_mod.latest_run(conn)
    insider_rows = insiders_mod.summary(conn, market.universe)
    insider_recent = insiders_mod.recent(conn, market.universe)
    news_rows = news_mod.by_symbol(conn, market.universe)
    if with_followthrough:
        earnings = {s: e.date for s in market.universe
                    if (e := calendar.next_earnings(s)) is not None}
        # Four backtests over years of prices, and nothing to show for the best
        # part of a minute. Silence that long is indistinguishable from a hang,
        # so say what is happening and tick as each one lands.
        print(f"  → Replaying {len(BASE_SCREEN_KEYS)} default backtests over "
              f"{len(market.calendar):,} sessions. A minute or so.", flush=True)
        timeline = engine.rs_timeline(market)      # computed once, reused per screen
        for index, screen in enumerate(BASE_SCREEN_KEYS, 1):
            config = BacktestSettings.parse({"screen": screen})
            run_out = engine.run(market, config, earnings, timeline)
            summary = metrics.summarise(run_out)
            backtests[config.hash()] = summary
            print(f"    {index}/{len(BASE_SCREEN_KEYS)}  {screen} — "
                  f"{len(summary.get('trades', []))} trades", flush=True)
        print("  → Checking what happened to recent breakouts.", flush=True)
        follow = followthrough.compute(market, timeline)
        for key, row in follow["screens"].items():
            print(f"    {key} — {row['settled']} settled, {row['up']} up, "
                  f"{row['failed_fast']} failed fast", flush=True)
    return (market, bundle, result, changes, calendar, iv_rows, gamma_rows,
            forecast_rows, backtests, follow, insider_rows, insider_recent,
            news_rows, desk_rows, desk_run)


def cmd_headlines(args) -> int:
    """Headlines published since the nightly's newest, beside the quotes.

    Run by the hourly quotes job. Reads the published tree, asks the news
    endpoint for anything newer, and writes out/news_live.json for the quotes
    branch. A failure here leaves the site on the nightly's headlines, which
    is what it showed before this existed.
    """
    from catalysts import news as newsmod
    out = settings.out_dir()
    payload = newsmod.live(out)
    (out / "news_live.json").write_text(json.dumps(payload))
    print(f"  {len(payload['articles'])} headline(s) since {payload.get('since')}"
          + (f" ({payload['note']})" if payload.get("note") else ""))
    return 0


def cmd_quotes(args) -> int:
    """Write a delayed price for every name currently on a screen.

    Runs on its own schedule during the session, separate from the nightly.
    It reads the screens the nightly already published and writes one small
    file; it never touches the database, the detectors or the rest of the
    tree, so it cannot corrupt an end-of-day figure by running at an odd
    moment.
    """
    import pathlib

    from catalysts import quotes as quotesmod

    out = settings.out_dir()
    screens = out / "screens"
    if not screens.is_dir():
        print("No published screens to quote. Run the nightly first.")
        return 1

    # Nearest its pivot first. The file exists to answer "is this breaking out
    # right now", and that question is live for a name sitting half a percent
    # under its level and academic for one thirty per cent past it. A name on
    # several screens keeps its closest reading.
    from publish import gated as gatedmod

    distance: dict[str, float] = {}
    free: set[str] = set()
    full_lists: list[dict] = []

    def absorb(payload: dict, public: bool) -> None:
        full_lists.append(payload)
        for stage in (payload.get("setups") or {}).values():
            for row in stage:
                symbol = row.get("symbol")
                if not symbol:
                    continue
                if public:
                    free.add(symbol)
                gap = row.get("now_vs_pivot_pct")
                # No reading at all goes to the back rather than to the front,
                # which is where a missing value sorted as zero would land it.
                rank = abs(float(gap)) if gap is not None else 9_999.0
                if symbol not in distance or rank < distance[symbol]:
                    distance[symbol] = rank

    for path in sorted(screens.glob("*.json")):
        if path.stem == "diff":
            continue
        try:
            absorb(json.loads(path.read_text()), public=True)
        except (OSError, ValueError):
            continue

    # The benchmark, the Nasdaq proxy and the sector ETFs, ahead of everything
    # else and always public.
    #
    # They were not in this sweep at all, which made the whole feature look
    # broken: the two biggest numbers on the home page are SPY and QQQ, they
    # are read straight from the nightly file, and so they showed Friday's
    # close all through Monday no matter how often this job ran. A reader
    # checking whether the site updates during the day looks at exactly those
    # two numbers.
    #
    # Market-level and already free, so they stay in the public file whoever
    # is looking. Sorted to the front with a negative distance because the
    # sweep is budget-limited and these are the ones everybody sees.
    market_wide = [settings.get("universe.benchmark", "SPY")]
    try:
        payload = json.loads((out / "indexes.json").read_text())
        market_wide += [row["symbol"] for row in (payload.get("rows") or [])]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    market_wide += list(settings.get("rankings.sector_etfs", []) or [])
    for symbol in market_wide:
        symbol = str(symbol).upper()
        distance[symbol] = -1.0
        free.add(symbol)

    # The published screens are the free sample now, so reading only those
    # would quote the free names and leave a subscriber's own rows as the only
    # ones on the page with no live price — the paid half of the product with
    # worse data than the free half. So the full lists are read back from the
    # gated store, and the result is split the same way everything else is.
    gated_screens = gatedmod.fetch("screens/")
    for payload in gated_screens.values():
        absorb(payload, public=False)
    if gated_screens:
        print(f"  read {len(gated_screens)} gated screen list(s); "
              f"{len(distance) - len(free)} name(s) beyond the free sample")
    elif any((json.loads(p.read_text()).get("gated")
              for p in screens.glob("*.json") if p.stem != "diff")):
        # Loud, because the failure is invisible in the output: the sweep
        # succeeds, publishes a shorter file, and nothing says the subscriber
        # half is missing.
        print("  WARNING: the screens are gated but the gated store could not "
              "be read. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, or "
              "subscribers get no intraday price on the names they paid for.")

    if not distance:
        print("The published screens list no names; nothing to quote.")
        return 1

    alerting = bool(getattr(args, "alerts", False))
    if alerting:
        # Names a subscriber is waiting on go just behind the market-wide few,
        # so the sweep's budget never runs out before the one they starred.
        from digest import alerts as alertsmod
        for symbol in alertsmod.watched_symbols():
            if symbol in distance and distance[symbol] >= 0:
                distance[symbol] = -0.5

    ordered = sorted(distance, key=lambda s: (distance[s], s))
    _banner(f"Quotes — {len(ordered):,} names on a screen, nearest pivot first")
    payload = quotesmod.collect(ordered, notice=lambda m: print(f"  → {m}", flush=True))

    quotes = payload.get("quotes") or {}
    alert_failures = 0
    if alerting:
        # After the sweep and before the split, so a subscriber's alert can be
        # about a name outside the free sample. A failure here is reported but
        # does not stop the quotes being published.
        _banner("Watchlist alerts")
        try:
            alert_failures = alertsmod.run(
                full_lists, quotes, send=bool(getattr(args, "send_alerts", False)),
                notice=lambda m: print(f"  {m}", flush=True))
        except Exception as exc:  # noqa: BLE001 - never cost the quotes
            alert_failures = 1
            print(f"  alerts failed: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
    if getattr(args, "stop_press", False):
        _banner("Stop press")
        try:
            _stop_press(args, out, full_lists, quotes)
        except Exception as exc:  # noqa: BLE001 - never cost the quotes
            print(f"  stop press failed: {type(exc).__name__}: {str(exc)[:200]}", flush=True)

    locked = {symbol: quote for symbol, quote in quotes.items()
              if symbol not in free}
    payload["quotes"] = {symbol: quote for symbol, quote in quotes.items()
                         if symbol in free}
    payload["count"] = len(payload["quotes"])
    payload["gated_count"] = len(locked)

    target = pathlib.Path(args.out) if getattr(args, "out", None) else out / "quotes.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"  wrote {target} — {payload['count']:,} public quotes")

    if locked:
        document = gatedmod.Document(
            "market/quotes.json",
            {**{k: v for k, v in payload.items() if k != "quotes"},
             "count": len(locked), "quotes": locked},
            dt.date.today())
        # sweep=False, and it matters. This writes under market/, the delete is
        # by prefix and date, and a Monday run sweeping market/ would remove
        # Friday's gamma and seasonals for carrying an older session.
        report = gatedmod.upload([document], dt.date.today(), sweep=False)
        print(f"  {report.render()}")
        if report.configured and not report.ok:
            return 1

    if alert_failures:
        # A warning, not an exit code: the quotes are published by the next
        # step, which a non-zero exit here would skip, and a missed email is
        # not worth a page of stale prices.
        print(f"::warning::{alert_failures} watchlist alert email(s) failed to send")

    # A file of nothing is worse than no file: the page would show a delayed
    # price section that is permanently empty and say nothing about why.
    return 0 if (payload["count"] or locked) else 1


def _stop_press(args, out, full_lists: list[dict], quotes: dict[str, dict]) -> None:
    """Post the session's new crossings to Discord, each name once a day.

    What has been posted is kept in a small file that rides on the quotes
    branch: the job has no other memory between runs.
    """
    import pathlib

    from digest import alerts as alertsmod
    from publish import discord

    now = dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(alertsmod.NEW_YORK)
    today = local.date()
    # {symbol: {"pivot": ..., "screen": ...}}: the level each name was posted
    # against, so the close can be held up to the same one.
    posted: dict[str, dict] = {}
    settled = False
    state_path = getattr(args, "stop_press_state", None)
    if state_path:
        try:
            kept = json.loads(pathlib.Path(state_path).read_text())
            if kept.get("date") == today.isoformat():
                was = kept.get("posted") or {}
                posted = dict(was) if isinstance(was, dict) else {s: {} for s in was}
                settled = bool(kept.get("settled"))
        except (OSError, ValueError):
            pass

    def keep() -> None:
        (out / "stop_press.json").write_text(json.dumps(
            {"date": today.isoformat(), "posted": posted, "settled": settled}))

    keep()
    if not alertsmod.in_session(now):
        # After the bell, once: how the day's names stood. Twenty minutes
        # past, because the quotes are that much behind and an earlier one is
        # still a price from inside the session.
        after = local.weekday() < 5 and local.time() >= dt.time(16, 20)
        if after and posted and not settled:
            message = discord.settled_message(posted, quotes, today,
                                              local.strftime("%-I:%M %p"))
            if message:
                print(message)
                if getattr(args, "send_stop_press", False) and discord.post(
                        "stop_press", message, username="The Tape · stop press"):
                    settled = True
                    keep()
                    print("  sent to Discord.")
                return
        print("  outside the regular session; nothing posted.")
        return
    names = {row["symbol"]: row.get("name") or ""
             for payload in full_lists
             for stage in (payload.get("setups") or {}).values()
             for row in stage if row.get("symbol")}
    levels = alertsmod.forming_levels(full_lists)
    events = alertsmod.detect(levels, quotes, list(levels))
    rows = discord.crossings(events, quotes, names, session=today, already=set(posted))
    crossed = sum(1 for e in events if e.kind == "crossed")
    print(f"  {crossed} name(s) through a pivot, {len(rows)} new with volume behind them")
    if not rows:
        return
    message = discord.stop_press_message(rows, local.strftime("%-I:%M %p"))
    print(message)
    if not getattr(args, "send_stop_press", False):
        return
    if discord.post("stop_press", message, username="The Tape · stop press"):
        posted.update({row["symbol"]: {"pivot": row["pivot"], "screen": row["screen"]}
                       for row in rows})
        keep()
        print("  sent to Discord.")
    else:
        print("  no Discord webhook is set; nothing was sent.")


def cmd_publish(args) -> int:
    from publish import schema, writer
    conn = _conn()
    run = store.start_run(conn, "publish")
    try:
        lost_leaders = json.loads(store.get_kv(conn, "universe.lost_leaders", "[]"))
    except (TypeError, ValueError):
        lost_leaders = []
    try:
        lost_reasons = json.loads(
            store.get_kv(conn, "universe.lost_leader_reasons", "{}"))
    except (TypeError, ValueError):
        lost_reasons = {}
    (market, bundle, result, changes, calendar, iv_rows, gamma_rows,
     forecast_rows, backtests, follow, insider_rows, insider_recent,
     news_rows, desk_rows, desk_run) = _pipeline(conn)
    from catalysts import releases as rel
    release_rows = rel.load(conn, market.as_of)

    # The Market Desk's weekly positioning table, when it has supplied one.
    from data import marketdesk as desk_mod
    positioning = desk_mod.positioning(conn)
    # And its 1.6/1.7 blocks: put/call and regime, the priced earnings read,
    # and the tracked funds' holders. Each is None until the desk sends it.
    market_context = desk_mod.market_context(conn)
    earnings_iv = desk_mod.earnings_iv(conn)
    holders = desk_mod.holders(conn)
    desk_extras = desk_mod.extras(conn)
    from data import indexes as indexes_mod
    sp500_members, sp500_on = indexes_mod.sp500(conn)
    from data import congress as congress_mod
    congress_trades = congress_mod.load(conn, market.universe, market.as_of)

    # Filed figures, from the fundamentals step's cache. Never fetched here.
    from data import fundamentals as fundamentals_mod
    filed = fundamentals_mod.load(conn)

    # How each company has moved across its recent reports, from the bars we
    # already hold and the report dates the earnings cache already keeps.
    from catalysts import reactions
    from catalysts import yf as yfmod
    reported = yfmod.reported_dates(conn, market.universe, market.as_of)
    earnings_moves = {}
    for symbol, dates in reported.items():
        found = reactions.summary(reactions.moves(
            market.series.get(symbol) or [], dates, market.as_of))
        if found:
            earnings_moves[symbol] = found
    print(f"  → Earnings moves measured for {len(earnings_moves):,} of "
          f"{len(market.universe):,} names.", flush=True)

    # A read of every recent reporter's filed quarter, for the Earnings tab
    # and the stock pages.
    from data import earnings_read
    earnings_reads = earnings_read.build(
        filed, reported, market.as_of,
        settled=(earnings_iv or {}).get("settled"), signals=desk_rows)
    print(f"  → Earnings reads for {len(earnings_reads):,} recent reporters.", flush=True)

    from publish import health
    sources = health.report(conn, market.as_of, desk_run,
                            provider=str(settings.get("data.provider", "") or ""))
    sources_history = health.remember(conn, market.as_of, sources)
    for line in health.summary(sources):
        print(f"  → source report: {line}", flush=True)
    if sources and not health.summary(sources):
        print(f"  → source report: all {len(sources)} sources ok.", flush=True)

    written = writer.publish(market, bundle, result, calendar, iv_rows, changes, backtests,
                             follow=follow, insiders=insider_rows,
                             news=news_rows, desk=desk_rows, desk_run=desk_run,
                             releases=release_rows, gamma=gamma_rows,
                             insider_recent=insider_recent,
                             forecasts=forecast_rows,
                             lost_leaders=lost_leaders,
                             lost_leader_reasons=lost_reasons,
                             positioning=positioning,
                             earnings_moves=earnings_moves,
                             market_context=market_context,
                             earnings_iv=earnings_iv,
                             holders=holders,
                             desk_extras=desk_extras,
                             sources_history=sources_history,
                             sp500=(sp500_members, sp500_on),
                             congress=congress_trades,
                             fundamentals=filed,
                             earnings_reads=earnings_reads,
                             sources=sources)

    out = settings.out_dir()
    # Tonight's front page kept as an edition, and the archive written out
    # again from the database: the tree itself is rebuilt whole every night.
    try:
        from publish import editions
        kept = editions.record(conn, out, market.benchmark)
        written += kept
        print(f"  → {max(0, len(kept) - 1)} edition(s) in the archive.", flush=True)
    except Exception as exc:                                    # noqa: BLE001
        print(f"  → Editions not written: {type(exc).__name__}: {exc}", flush=True)
    _banner(f"Published — {len(written)} files under {out}")
    tree = {}
    for path in written:
        rel = path.relative_to(out)
        key = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        tree[key] = tree.get(key, 0) + 1
    for key in sorted(tree):
        print(f"  {key:<16}{tree[key]:>5} file(s)")

    meta = json.loads((out / "meta.json").read_text())
    problems = schema.validate(meta)
    _banner("meta.json")
    print(f"  as of {meta['as_of']}   provider {meta['provider']}"
          f"   data source {meta['data_source']}")
    print(f"  universe {meta['universe_count']:,}"
          f"   survivorship safe: {str(meta['survivorship_safe']).lower()}")
    for row in meta["screens"]:
        print(f"  {row['name']:<28}{row['total']:>5}  {row['stages']}")
    print()
    print("  schema: VALID" if not problems else "  schema: INVALID")
    for problem in problems:
        print(f"    - {problem}")
    from publish import gated as gatedmod
    staged = gatedmod.load()
    _banner("Gated")
    if staged:
        print(f"  {len(staged)} document(s) staged under {gatedmod.gated_dir()}")
        print(f"  free gamma sample: {gatedmod.FREE_GAMMA_ROWS} name(s)")
        print("  nothing is uploaded here — run `python -m cli gated` for that,")
        print("  which is a separate step so a Supabase outage cannot stop the")
        print("  public tree from being published.")
    else:
        print("  nothing staged. Every page is public.")

    store.finish_run(conn, run, "ok" if not problems else "failed", f"{len(written)} files")
    return 0 if not problems else 1


def _briefing_setups(out) -> tuple[list[dict], str]:
    """Every setup at every stage, and where they were read from.

    The public screens no longer carry the forming stage — that is the paywall
    — so reading them here would name no forming stocks at all and count none.
    The staged gated documents hold the full lists and are written by publish
    whether or not they are ever uploaded. The stock pages are the fallback:
    each one still carries its own setups, which is the same data one company
    at a time.
    """
    import pathlib

    from publish import gated as gatedmod

    staged = sorted((gatedmod.gated_dir() / "screens").glob("*.json"))
    if staged:
        rows: list[dict] = []
        for path in staged:
            payload = json.loads(path.read_text()).get("payload") or {}
            for stage_rows in (payload.get("setups") or {}).values():
                rows.extend(stage_rows)
        return rows, f"{len(staged)} gated screen list(s)"

    rows = []
    for path in sorted(pathlib.Path(out, "stocks").glob("*.json")):
        rows.extend(json.loads(path.read_text()).get("setups") or [])
    return rows, "the stock pages"


def cmd_briefing(args) -> int:
    """Compose the X post draft, and optionally send it to Discord.

    A draft, not a post. It lands in Discord and a person reads it and posts
    it, so a wrong number costs nothing until somebody has looked at it.
    """
    import os
    import urllib.request

    from publish import briefing

    out = settings.out_dir()
    try:
        meta = json.loads((out / "meta.json").read_text())
        feed_path = out / "breakouts" / f"{meta['as_of']}.json"
        inputs = {
            "meta": meta,
            "indexes": json.loads((out / "indexes.json").read_text()),
            "breadth": json.loads((out / "breadth.json").read_text()),
            "feed": (json.loads(feed_path.read_text()) if feed_path.exists()
                     else {"setups": []}),
        }
    except (OSError, ValueError, KeyError) as exc:
        print(f"No published tree to brief from ({exc}). Run publish first.")
        return 1

    setups, source = _briefing_setups(out)
    post = briefing.compose(setups=setups, **inputs)

    _banner(f"Briefing — {meta['as_of']}, setups from {source}")
    print(post)

    if not getattr(args, "send", False):
        return 0
    from publish import discord
    # The post alone, as its own message, so copying it copies nothing else.
    # To the operations room: it is a draft for whoever posts it, not reading
    # for everybody.
    try:
        if not discord.post("ops", post, username="The Tape · X draft"):
            print("\nNo Discord webhook is set; the draft was not sent.")
            return 1
    except Exception as exc:                       # noqa: BLE001
        print(f"\nDiscord refused the draft: {exc}")
        return 1
    print("\nSent to Discord.")
    return 0


def cmd_edition(args) -> int:
    """Tonight's read to the edition room, and anything amiss to operations.

    Run by the nightly after the site has been told to rebuild. The picture is
    drawn by the site, so this waits for the rebuild before posting; if the
    site has not caught up in time the post goes out without the picture
    rather than with last night's.
    """
    from publish import discord

    out = settings.out_dir()
    try:
        meta = json.loads((out / "meta.json").read_text())
    except (OSError, ValueError) as exc:
        print(f"No published tree to post from ({exc}). Run publish first.")
        return 1
    try:
        edition = json.loads((out / "editions" / f"{meta['as_of']}.json").read_text())
    except (OSError, ValueError):
        edition = None

    send = bool(getattr(args, "send", False))
    if getattr(args, "extras_only", False):
        # What follows the edition, without the edition: for trying those
        # posts out on a night whose edition has already gone.
        _edition_extras(out, meta, send=send)
        return 0
    picture = False
    if edition and send and not getattr(args, "no_wait", False):
        picture = discord.site_has(meta["as_of"])
        print(f"  site rebuilt for {meta['as_of']}: {'yes' if picture else 'not in time'}")
    content, embeds = discord.edition_message(
        meta, edition, behind=int(getattr(args, "behind", 0) or 0),
        picture=picture or not send)
    ops = discord.ops_lines(meta)

    _banner(f"Discord — the edition for {meta['as_of']}")
    print(content)
    for embed in embeds:
        print(f"  [card] {embed['title']}  {embed.get('image', {}).get('url', 'no picture')}")
    if ops:
        print("\n".join(ops))
    if not send:
        _edition_extras(out, meta, send=False)
        return 0

    together = discord.same_room("edition", "ops")
    if together and ops:
        # One room for everything: one message, as it always was.
        content = content + "\n\n" + "\n".join(ops)
    if not discord.post("edition", content, embeds=embeds):
        print("\nNo Discord webhook is set; nothing was sent.")
        return 1
    if ops and not together:
        discord.post("ops", f"**{meta['as_of']}**\n" + "\n".join(ops))
    print("\nSent to Discord.")
    _edition_extras(out, meta, send=True)
    return 0


def _edition_extras(out, meta: dict, *, send: bool) -> None:
    """What follows the edition: new names, the morning line, earnings reads.

    Each is its own message and each may have nothing to say, in which case
    it says nothing. A failure in one does not stop the others, and none of
    them can fail the run: the edition has already gone out.
    """
    from publish import discord

    def load(*parts: str) -> dict:
        try:
            return json.loads(out.joinpath(*parts).read_text())
        except (OSError, ValueError):
            return {}

    as_of = dt.date.fromisoformat(meta["as_of"])
    labels = {s["key"]: s["name"] for s in meta.get("screens") or []}
    on_screen: dict[str, str] = {}
    try:
        setups, _ = _briefing_setups(out)
        for row in setups:
            if row.get("symbol"):
                on_screen.setdefault(row["symbol"],
                                     labels.get(row.get("screen"), row.get("screen") or "a screen"))
    except Exception as exc:                       # noqa: BLE001
        print(f"  names on a screen unavailable: {type(exc).__name__}")

    def say(room: str, what: str, content: str | None, **kw) -> bool:
        if not content and not kw.get("embeds"):
            print(f"\n  {what}: nothing to say tonight.")
            return False
        print(f"\n{content or ''}")
        for embed in kw.get("embeds") or []:
            print(f"  [card] {embed['title']}")
        if not send:
            return False
        try:
            return discord.post(room, content or "", **kw)
        except Exception as exc:                   # noqa: BLE001
            print(f"  {what}: Discord refused the post ({type(exc).__name__})")
            return False

    say("edition", "new on a screen",
        discord.new_on_screens(load("screens", "diff.json"), meta))
    say("edition", "the morning line",
        discord.morning_line(load("catalysts", "upcoming.json"),
                             load("catalysts", "releases.json"), on_screen, as_of))

    # Earnings reads, each company once. What has been posted is kept in the
    # database, which the nightly carries from one night to the next.
    posted: dict[str, str] = {}
    conn = None
    try:
        conn = _conn()
        posted = json.loads(store.get_kv(conn, "discord.earnings_posted", "{}") or "{}")
    except Exception as exc:                       # noqa: BLE001
        print(f"  earnings memory unavailable: {type(exc).__name__}")
    # And whatever the day's two reporters runs posted as filings came in, so
    # the same card is not sent again at night. READS_POSTED_FILE is their
    # note, fetched by the workflow; absent, there is nothing to add.
    theirs = _reads_file(os.environ.get("READS_POSTED_FILE") or "")
    posted.update(theirs)
    rows = discord.reads_to_post(load("market", "earnings.json").get("reads") or [],
                                 on_screen, as_of, posted)
    sent = say("earnings", "earnings reads",
               "**Earnings reads**: reported since the last edition" if rows else None,
               embeds=[discord.read_embed(row, on_screen) for row in rows] or None,
               username="The Tape · earnings")
    if sent and conn is not None:
        store.set_kv(conn, "discord.earnings_posted",
                     json.dumps(discord.remember_reads(posted, rows, as_of)))


def _names_on_screens(out) -> dict[str, str]:
    """Every name on a screen and the screen it is on, public and gated: the
    rooms these go to are private. A name on several keeps the first."""
    from publish import gated as gatedmod

    on_screen: dict[str, str] = {}

    def absorb(payload: dict) -> None:
        for stage in (payload.get("setups") or {}).values():
            for row in stage:
                if row.get("symbol"):
                    on_screen.setdefault(row["symbol"], payload.get("name") or "a screen")

    for path in sorted((out / "screens").glob("*.json")):
        if path.stem != "diff":
            try:
                absorb(json.loads(path.read_text()))
            except (OSError, ValueError):
                continue
    try:
        for payload in gatedmod.fetch("screens/").values():
            absorb(payload)
    except Exception as exc:                       # noqa: BLE001
        print(f"  gated screens unavailable: {type(exc).__name__}")
    return on_screen


def cmd_weekahead(args) -> int:
    """The week's earnings for the names on a screen, for the earnings room.

    Run on a Sunday evening. Reads the published calendar and nothing else.
    """
    from publish import discord

    out = settings.out_dir()
    try:
        upcoming = json.loads((out / "catalysts" / "upcoming.json").read_text())
    except (OSError, ValueError) as exc:
        print(f"No published calendar to read ({exc}).")
        return 1
    try:
        implied = discord.implied_moves(json.loads((out / "market" / "earnings.json").read_text()))
    except (OSError, ValueError):
        implied = {}
    today = (dt.date.fromisoformat(args.day) if getattr(args, "day", None)
             else dt.datetime.now(discord.NEW_YORK).date())
    message = discord.week_ahead_message(upcoming, _names_on_screens(out), implied, today)
    if not message:
        print("Nobody in the universe reports in the week to come.")
        return 0
    _banner("The week's earnings")
    print(message)
    if not getattr(args, "send", False):
        return 0
    try:
        if not discord.post("earnings", message, username="The Tape · earnings"):
            print("\nNo Discord webhook is set; nothing was sent.")
            return 1
    except Exception as exc:                       # noqa: BLE001
        print(f"\nDiscord refused the post: {type(exc).__name__}")
        return 1
    print("\nSent to Discord.")
    return 0


def cmd_reporters(args) -> int:
    """Who reported today and how the price took it, for the earnings room.

    Twice a day: before the open for the companies that report before the
    bell, and in the evening for the rest. It reads the published calendar for
    who is due, asks Yahoo for the prices and the figure against the estimate,
    and names each company once a day. The full read of the quarter is a
    different post: it waits for the 10-Q.
    """
    import pathlib
    import time

    from catalysts import yf as yfmod
    from publish import discord, gated as gatedmod

    out = settings.out_dir()
    now = dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(discord.NEW_YORK)
    day = (dt.date.fromisoformat(args.day) if getattr(args, "day", None) else local.date())
    wanted = getattr(args, "when", "auto") or "auto"
    run = wanted if wanted in ("pre", "post") else discord.which_run(now)

    posted: list[str] = []
    # Today's lines as a public page may show them, the reactions still
    # waiting on their session, and the ones that have had it. The last two
    # outlive the day; the first two lists do not.
    rows_today: list[dict] = []
    pending: list[dict] = []
    settled_kept: list[dict] = []
    # Which companies have had a first read posted from their press release,
    # and the day: {symbol: "YYYY-MM-DD"}. Kept a fortnight.
    releases: dict[str, str] = {}
    state_path = getattr(args, "state", None)
    if state_path:
        try:
            kept = json.loads(pathlib.Path(state_path).read_text())
            if kept.get("date") == day.isoformat():
                posted = list(kept.get("posted") or [])
                rows_today = list(kept.get("rows") or [])
            pending = list(kept.get("pending") or [])
            settled_kept = list(kept.get("settled") or [])
            releases = {k: v for k, v in (kept.get("releases") or {}).items()
                        if str(v) >= (day - dt.timedelta(days=14)).isoformat()}
        except (OSError, ValueError):
            pass

    def keep() -> None:
        # The reads posted from here ride in the same note. They are written
        # by the reads step, so whatever it left is carried, not overwritten.
        reads: dict = {}
        for source in (out / "reporters.json", pathlib.Path(state_path or "")):
            try:
                reads = json.loads(source.read_text()).get("reads") or {}
                break
            except (OSError, ValueError):
                continue
        (out / "reporters.json").write_text(json.dumps(
            {"date": day.isoformat(), "posted": sorted(set(posted)), "reads": reads,
             "rows": rows_today, "pending": pending,
             "settled": settled_kept[:discord.SETTLED_KEPT],
             "releases": releases}))

    keep()
    if getattr(args, "reads", False):
        # Whatever the hour: a filing arrives when it arrives.
        try:
            _reads_as_filed(args, out, day, state_path, today=posted)
        except Exception as exc:                   # noqa: BLE001 - never cost the reaction
            print(f"  reads as filed: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
    if run is None:
        print(f"  {local.strftime('%-I:%M %p')} New York is outside both windows; "
              f"no reaction post.")
        return 0

    # In the evening, before anything else: how the reactions already posted
    # held up over a full session. It needs nobody to be reporting today.
    if run == "post" and pending:
        try:
            closes = yfmod.report_day_quotes([row["symbol"] for row in pending])
            done, pending[:] = discord.settle(pending, closes, day)
            print(f"  settled {len(done)} of the reactions waiting on a session; "
                  f"{len(pending)} still waiting")
            text = discord.reactions_settled_message(done, day)
            if text:
                print(text)
                if not getattr(args, "send", False):
                    # A dry run settles nothing: the note is not its to change.
                    pending.extend(discord.unsettled(done))
                elif discord.post("earnings", text, username="The Tape · earnings"):
                    settled_kept[:0] = done
                else:
                    pending.extend(discord.unsettled(done))
            keep()
        except Exception as exc:                   # noqa: BLE001 - never cost the reaction
            print(f"  settling: {type(exc).__name__}: {str(exc)[:200]}", flush=True)

    # Whatever the reaction post does below, and however it returns, the
    # first reads from the press releases are attempted after it: for the
    # companies named today, this run's included.
    try:
        try:
            upcoming = json.loads((out / "catalysts" / "upcoming.json").read_text())
        except (OSError, ValueError) as exc:
            print(f"No published calendar to read ({exc}).")
            return 1
        def listed(on: dt.date) -> set[str]:
            return {e["ticker"] for e in upcoming.get("events") or []
                    if e.get("type") == "earnings" and e.get("date") == on.isoformat()
                    and not e.get("readthrough")}

        due = sorted(listed(day))
        # The calendar's date for a report can be a day out: it is refreshed
        # weekly and companies move. So the days either side are asked about too,
        # and kept only where Yahoo has the report on today.
        nearby = sorted((listed(day - dt.timedelta(days=1))
                         | listed(day + dt.timedelta(days=1))) - set(due))
        _banner(f"Reporters — {day.isoformat()}, the {'morning' if run == 'pre' else 'evening'} run")
        print(f"  {len(due)} due today by the calendar, {len(nearby)} listed a day either "
              f"side, {len(posted)} already named")
        if not due and not nearby:
            return 0

        on_screen = _names_on_screens(out)
        try:
            implied = discord.implied_moves(json.loads((out / "market" / "earnings.json").read_text()))
        except (OSError, ValueError):
            implied = {}

        # Finnhub's calendar for the day: one request, every reporter, with
        # earnings and revenue against their estimates soon after the print.
        # Empty without a key, and then Yahoo is read alone as before.
        from catalysts import finnhub
        figures = finnhub.calendar(day)
        if finnhub.enabled():
            print(f"  finnhub: {len(figures):,} companies on the day, "
                  f"{sum(1 for r in figures.values() if r['eps'] is not None):,} "
                  f"with a reported figure ({dict(finnhub.OUTCOMES)})")
        else:
            print("  finnhub: no FINNHUB_API_KEY set; figures from Yahoo alone.")

        quotes = yfmod.report_day_quotes(due + nearby)
        moved = [s for s in nearby if (quotes.get(s) or {}).get("due_on") == day.isoformat()
                 or s in figures]
        if moved:
            print(f"  {len(moved)} of those are on today by Yahoo or Finnhub: "
                  f"{', '.join(moved)}")
            due = sorted(set(due) | set(moved))
        named = discord.reporters_to_name(due, quotes, on_screen, set(posted))
        tables: dict[str, dict | None] = {}
        asked_yahoo = 0
        for symbol in named:
            theirs = figures.get(symbol)
            if finnhub.complete(theirs):
                # When in the day and the figure are both in hand: Yahoo's table
                # has nothing to add, and it is the slow request of the two.
                tables[symbol] = finnhub.merged(None, theirs)
                continue
            tables[symbol] = finnhub.merged(yfmod.report_row(symbol, day), theirs)
            asked_yahoo += 1
            time.sleep(0.4)
        if finnhub.enabled():
            print(f"  Yahoo's table was needed for {asked_yahoo} of {len(named)}.")
        rows = discord.reporter_rows(run, named, quotes, tables, on_screen, implied)
        others = len([s for s in due if s not in posted]) - len(named)
        print(f"  prices for {len(quotes)} of {len(due)}; looked up {len(named)}, "
              f"{sum(1 for t in tables.values() if t)} with a line for today; "
              f"{len(rows)} to name in this run")
        message = discord.reporters_message(run, rows, day, local.strftime("%-I:%M %p"),
                                            others=max(0, others))
        if not message:
            print("  nobody to name in this run.")
            return 0
        print(message)
        if not getattr(args, "send", False):
            return 0
        try:
            if discord.post("earnings", message, username="The Tape · earnings"):
                posted += [row["symbol"] for row in rows]
                read_at = local.strftime("%Y-%m-%dT%H:%M")
                rows_today += [discord.public_row(row, day, run, read_at) for row in rows]
                pending += [{"symbol": row["symbol"], "name": row["name"],
                             "day": day.isoformat(), "when": row["when"],
                             "move": row["move"], "implied": row.get("implied")}
                            for row in rows if discord.awaits_session(row)]
                keep()
                print("\nSent to Discord.")
            else:
                print("\nNo Discord webhook is set; nothing was sent.")
        except Exception as exc:                       # noqa: BLE001
            print(f"\nDiscord refused the post: {type(exc).__name__}")
            return 1
        return 0

    finally:
        try:
            _release_reads(args, out, day, posted, pending, releases, keep)
        except Exception as exc:                   # noqa: BLE001 - never cost the run
            print(f"  press releases: {type(exc).__name__}: {str(exc)[:200]}", flush=True)


#: How many press releases one run sends to the model. Each is a request
#: that costs money; the names on a screen go first.
RELEASE_READS_A_RUN = 8


def _release_reads(args, out, day: dt.date, posted: list[str], pending: list[dict],
                   releases: dict[str, str], keep) -> None:
    """A first read from the press release for the companies named today.

    The read of a quarter waits days for its 10-Q. The release is filed the
    same hour, as an exhibit to an 8-K, and a model can read the handful of
    figures a reader wants that evening. Needs ANTHROPIC_API_KEY; without it
    this says so once and does nothing.
    """
    import requests

    from catalysts import finnhub
    from data import edgar, press_release
    from publish import discord

    # Today's names, and yesterday's after-the-bell ones still waiting on
    # their session: a release filed after last evening's run is read in the
    # morning.
    recent = {row["symbol"]: row.get("day") for row in pending
              if str(row.get("day")) >= (day - dt.timedelta(days=1)).isoformat()}
    wanted = [s for s in list(dict.fromkeys(list(posted) + list(recent)))
              if s not in releases]
    if not wanted:
        return
    if not press_release.enabled():
        print(f"  press releases: no ANTHROPIC_API_KEY set; {len(wanted)} first "
              f"reads not attempted.")
        return
    on_screen = _names_on_screens(out)
    order = {symbol: index for index, symbol in enumerate(wanted)}
    wanted.sort(key=lambda s: (s not in on_screen, order[s]))
    agent = edgar._user_agent()
    session = requests.Session()
    try:
        cik_map = edgar._ticker_to_cik(session)
    except edgar.EdgarUnavailable as exc:
        print(f"  press releases: SEC is not answering ({str(exc)[:120]}).")
        return
    second = {}
    names = {}
    try:
        names = {symbol: (json.loads((out / "stocks" / f"{symbol}.json").read_text())
                          .get("name") or "") for symbol in wanted[:60]
                 if (out / "stocks" / f"{symbol}.json").exists()}
    except (OSError, ValueError):
        pass
    read = found_none = 0
    spent = 0.0
    for symbol in wanted:
        if read >= RELEASE_READS_A_RUN:
            break
        cik = next((cik_map[c] for c in edgar._cik_candidates(symbol) if c in cik_map), None)
        if not cik:
            continue
        reported = dt.date.fromisoformat(str(recent.get(symbol) or day.isoformat()))
        try:
            where = press_release.find(session, cik, reported, agent)
            text = press_release.fetch(session, where["url"], agent) if where else None
        except (requests.RequestException, ValueError) as exc:
            print(f"  press releases: {symbol}: {type(exc).__name__}")
            continue
        if not text:
            found_none += 1
            continue
        if len(text) > press_release.MAX_CHARS:
            print(f"  press releases: {symbol}: the exhibit is {len(text):,} "
                  f"characters, too long to send whole; skipped.")
            continue
        read += 1
        found = press_release.read(text, symbol, names.get(symbol, ""))
        if not found:
            print(f"  press releases: {symbol}: no read came back.")
            continue
        if reported not in second:
            second[reported] = finnhub.calendar(reported)
        spent += press_release.cost(found.get("usage"), press_release.model())
        found = press_release.checked(
            found, (second[reported].get(symbol) or {}).get("revenue"))
        card = discord.release_embed(symbol, names.get(symbol, ""), found, where)
        print(f"  press releases: {symbol}: {card['title']} | "
              + card["description"].replace("\n", " | ")[:400])
        if not getattr(args, "send", False):
            continue
        try:
            if discord.post("earnings", "", embeds=[card],
                            username="The Tape · first read"):
                releases[symbol] = day.isoformat()
                keep()
        except Exception as exc:                   # noqa: BLE001
            print(f"  press releases: Discord refused {symbol}: {type(exc).__name__}")
    print(f"  press releases: {read} sent to {press_release.model()} for about "
          f"${spent:.3f}, {found_none} with no 8-K exhibit on file yet, "
          f"{len(releases)} first reads on record.")


def _reads_file(path) -> dict[str, str]:
    """The reads the reporters job has posted, from its note. Empty if none."""
    import pathlib
    try:
        return dict(json.loads(pathlib.Path(path).read_text()).get("reads") or {})
    except (OSError, ValueError, TypeError):
        return {}


def _reads_as_filed(args, out, day: dt.date, state_path, today=()) -> None:
    """Post the read of any recent reporter whose 10-Q has now been filed.

    The nightly does this once a day. Half the filings for a day's reports are
    in within a day and most within three, at no particular hour, so asking
    SEC again at each of the day's two runs gets a read out hours sooner. It
    works on the nightly's database, restored read-only: what it fetches is
    used for the post and not kept, and the nightly asks again for itself.
    """
    from catalysts import yf as yfmod
    from data import earnings_read, fundamentals
    from publish import discord

    conn = _conn()
    universe = [row["symbol"] for row in store.universe_rows(conn)]
    if not universe:
        print("  reads as filed: no database here; skipped.")
        return
    reported = yfmod.reported_dates(conn, universe, day + dt.timedelta(days=1))
    recent = {symbol: dates for symbol, dates in reported.items()
              if dates and 0 <= (day - max(dates)).days <= discord.READ_WINDOW_DAYS}
    # The companies named this morning. The database learns that a report
    # happened only at night, and some of them file the 10-Q the same day.
    for symbol in today:
        if symbol in set(universe):
            recent[symbol] = [day] + [d for d in recent.get(symbol, []) if d != day]
    waiting = fundamentals.due(conn, recent, day, again=True)
    _banner(f"Reads as filed — {len(recent)} reported in the last "
            f"{discord.READ_WINDOW_DAYS} days, {len(waiting)} still waiting on a 10-Q")
    if not waiting:
        return
    result = fundamentals.refresh(conn, waiting, budget=len(waiting), first=waiting)
    filed = fundamentals.load(conn)
    reads = earnings_read.build({s: filed.get(s) for s in waiting},
                                {s: recent[s] for s in waiting}, day)
    arrived = [r for r in reads if r.get("covers") is True]
    print(f"  asked SEC about {result.get('asked', 0)}: {len(arrived)} now have the "
          f"quarter they reported")

    posted: dict[str, str] = {}
    try:
        posted = json.loads(store.get_kv(conn, "discord.earnings_posted", "{}") or "{}")
    except ValueError:
        pass
    mine = _reads_file(out / "reporters.json") or _reads_file(state_path or "")
    posted.update(mine)

    names = {row["symbol"]: row["name"] for row in conn.execute(
        "SELECT symbol, name FROM tickers")}
    labels: dict[str, str] = {}
    for path in sorted((out / "screens").glob("*.json")):
        if path.stem == "diff":
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for stage in (payload.get("setups") or {}).values():
            for row in stage:
                if row.get("symbol"):
                    labels.setdefault(row["symbol"], payload.get("name") or "a screen")
    rows = discord.reads_to_post(
        [{**r, "name": names.get(r["symbol"], "")} for r in arrived], labels, day, posted)
    if not rows:
        print("  none of them is new to the room.")
        return
    for row in rows:
        print(f"  [card] {row['symbol']}: {row.get('takeaway')}")
    if not getattr(args, "send", False):
        return
    if discord.post("earnings", "**Earnings reads**: the 10-Q is in",
                    embeds=[discord.read_embed(row, labels) for row in rows],
                    username="The Tape · earnings"):
        mine = discord.remember_reads(mine, rows, day)
        note = json.loads((out / "reporters.json").read_text())
        note["reads"] = mine
        (out / "reporters.json").write_text(json.dumps(note))
        print("  sent to Discord.")


def cmd_rooms(args) -> int:
    """Say which Discord rooms are wired, and with --send post a line to each.

    Never prints a webhook: only whether a room has one and which rooms share
    it. Rooms that share a webhook get one message between them.
    """
    from publish import discord

    purpose = {
        "edition": "the edition room. The nightly read and the Saturday wrap post here.",
        "stop_press": ("the stop press room. During the session, a name through its "
                       "pivot on volume posts here, once a day for each name."),
        "ops": ("the operations room. Failure notices, sources that were short and "
                "the draft for X post here."),
        "earnings": ("the earnings room. The read on each company that has just "
                     "reported posts here after the nightly."),
    }
    only = getattr(args, "room", None)
    by_hook: dict[str, list[str]] = {}
    for room in purpose:
        own = bool(os.environ.get(discord.ROOMS[room], "").strip()
                   and os.environ.get(discord.ROOMS[room]) != os.environ.get(discord.FALLBACK))
        url = discord.hook(room)
        print(f"  {room:<11} {'its own webhook' if own else 'the shared webhook' if url else 'NOT SET'}")
        if url and (not only or room == only):
            by_hook.setdefault(url, []).append(room)
    if not only:
        print(f"  {len(by_hook)} distinct room(s)")
    if not getattr(args, "send", False):
        return 0
    failed = 0
    for rooms in by_hook.values():
        lines = [f"Test from The Tape: this is {purpose[room]}" for room in rooms]
        try:
            discord.post(rooms[0], "\n".join(lines), username="The Tape · test")
            print(f"  posted to {', '.join(rooms)}")
        except Exception as exc:                   # noqa: BLE001
            failed += 1
            print(f"  {', '.join(rooms)}: Discord refused the post ({type(exc).__name__})")
    return 1 if failed else 0


def cmd_wrap(args) -> int:
    """The week's wrap: what broke out and whether it held.

    Reads the published tree and nothing else, so it can run on its own on a
    Saturday without the database.
    """
    from publish import discord

    out = settings.out_dir()
    try:
        meta = json.loads((out / "meta.json").read_text())
        follow = json.loads((out / "breakouts" / "followthrough.json").read_text())
    except (OSError, ValueError) as exc:
        print(f"No published tree to wrap up ({exc}).")
        return 1
    try:
        editions = json.loads((out / "editions" / "index.json").read_text())
    except (OSError, ValueError):
        editions = {}
    message = discord.wrap_message(follow, editions, dt.date.fromisoformat(meta["as_of"]))
    if not message:
        print("Nothing to say about this week.")
        return 0
    _banner(f"The week's wrap — week of {meta['as_of']}")
    print(message)
    if not getattr(args, "send", False):
        _sources_week(meta, send=False)
        return 0
    try:
        if not discord.post("edition", message, username="The Tape · the week"):
            print("\nNo Discord webhook is set; nothing was sent.")
            return 1
    except Exception as exc:                       # noqa: BLE001
        print(f"\nDiscord refused the wrap: {exc}")
        return 1
    print("\nSent to Discord.")
    _sources_week(meta, send=True)
    return 0


def _sources_week(meta: dict, send: bool) -> None:
    """How each source did this week, to the ops room. Its own post, and
    never a reason for the wrap to fail."""
    from publish import discord, health
    try:
        as_of = dt.date.fromisoformat(meta["as_of"])
        monday, friday = discord.week_of(as_of)
        lines = health.week_report(meta.get("sources_history") or [], health.labels(),
                                   monday, friday)
        if not lines:
            print("\nNo source reports on record for this week.")
            return
        text = (f"**Sources, week of {monday.month}/{monday.day}**\n"
                + "\n".join(f"• {line}" for line in lines))
        print("\n" + text)
        if send and discord.post("ops", text[:1900], username="The Tape · sources"):
            print("Sent to the ops room.")
    except Exception as exc:                       # noqa: BLE001
        print(f"\nThe week's source report failed: {type(exc).__name__}: {exc}")


def cmd_gated(args) -> int:
    """Upload the staged gated documents.

    Separate from publish on purpose. The public tree and the gated store fail
    in different ways and should not take each other down: a Supabase outage
    must not stop tonight's session reaching the site, and a schema problem in
    the public tree must not leave subscribers reading last week's gamma.
    """
    from publish import gated as gatedmod
    staged = gatedmod.load()
    if not staged:
        print(f"Nothing staged under {gatedmod.gated_dir()}. Run publish first.")
        return 1

    as_of = max(document.as_of for document in staged)
    report = gatedmod.upload(staged, as_of)
    if report.configured and report.ok:
        # Its own write, unswept, after everything else has landed: the
        # marker claims the whole upload finished, so it cannot ride in the
        # same batches as the documents it vouches for.
        marker = gatedmod.Document(
            gatedmod.UPLOAD_MARKER,
            {"as_of": as_of.isoformat(), "documents": report.written}, as_of)
        done = gatedmod.upload([marker], as_of, sweep=False)
        report.problems.extend(f"completion marker: {p}" for p in done.problems)
    _banner("Gated upload")
    print(f"  {report.render()}")
    if not report.configured:
        # Not a failure: a local run has no service-role key and should not
        # pretend to. It is said out loud rather than passed over in silence,
        # because "uploaded nothing" and "uploaded everything" otherwise look
        # identical from the outside.
        return 0
    return 0 if report.ok else 1


def cmd_fundamentals(args) -> int:
    """Trailing-twelve-month figures from SEC filings, most traded names first.

    A budget a night and a month between refreshes, so the first week fills
    the universe in and every night after that touches only what aged out.
    """
    from catalysts import yf as yfmod
    from data import edgar, fundamentals
    conn = _conn()
    rows = sorted(store.universe_rows(conn), key=lambda r: -(r["adv20"] or 0.0))
    _banner(f"Fundamentals — {len(rows):,} names in the universe")
    # Companies that have just reported go first, every night until the
    # quarter they reported is in the cache.
    today = dt.date.today()
    reporters = fundamentals.due(
        conn, yfmod.reported_dates(conn, [r["symbol"] for r in rows], today), today)
    print(f"  {len(reporters)} recent reporter(s) without their new quarter yet")
    try:
        result = fundamentals.refresh(conn, [r["symbol"] for r in rows],
                                      notice=lambda m: print(m, flush=True),
                                      first=reporters)
    except edgar.EdgarUnavailable as exc:
        print(f"  {exc}")
        return 1
    print(f"  asked {result['asked']}: {result['stored']} with figures, "
          f"{result['empty']} with none in US GAAP, {result.get('refused', 0)} refused; "
          f"{result['remaining']} still to fetch")
    try:
        from publish import health
        refused = int(result.get("refused", 0) or 0)
        health.record(
            conn, "filings", store.last_session(conn),
            (f"Asked about {result['asked']:,} companies: {result['stored']:,} with "
             f"figures, {result['empty']:,} with none in US GAAP, {refused:,} refused."),
            asked=result["asked"], answered=result["asked"] - refused)
    except Exception as exc:                      # noqa: BLE001 - never cost the stage
        print(f"  source report not kept: {type(exc).__name__}")
    return 0


def cmd_all(args) -> int:
    from types import SimpleNamespace
    from data import universe
    conn = _conn()
    funnel = universe.refresh(conn)
    _banner("Universe")
    print(funnel.render())
    return cmd_publish(SimpleNamespace())
