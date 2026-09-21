"""One function per subcommand. Each prints something a human can read."""
from __future__ import annotations

import datetime as dt

import json

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
    calendar = ev.build(market, market.universe, adapter, desk_earnings=desk_dates,
                        conn=conn, notice=lambda m: print(f"  → {m}", flush=True))
    ev.attach(calendar, result.all_setups())

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
    from catalysts import forecast as forecastmod
    forecastmod.fetch(conn, market.universe, limit=400,
                      notice=lambda m: print(f"  → {m}", flush=True),
                      priority=market.caps)

    from catalysts import gamma as gammamod
    gamma_profiles: dict = {}
    iv_stats: dict = {}
    rows = ivmod.compute(calendar, population, names, adapter,
                         gamma_out=gamma_profiles, stats=iv_stats)
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

    def absorb(payload: dict, public: bool) -> None:
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

    ordered = sorted(distance, key=lambda s: (distance[s], s))
    _banner(f"Quotes — {len(ordered):,} names on a screen, nearest pivot first")
    payload = quotesmod.collect(ordered, notice=lambda m: print(f"  → {m}", flush=True))

    quotes = payload.get("quotes") or {}
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

    # A file of nothing is worse than no file: the page would show a delayed
    # price section that is permanently empty and say nothing about why.
    return 0 if (payload["count"] or locked) else 1


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

    written = writer.publish(market, bundle, result, calendar, iv_rows, changes, backtests,
                             follow=follow, insiders=insider_rows,
                             news=news_rows, desk=desk_rows, desk_run=desk_run,
                             releases=release_rows, gamma=gamma_rows,
                             insider_recent=insider_recent,
                             forecasts=forecast_rows,
                             lost_leaders=lost_leaders,
                             lost_leader_reasons=lost_reasons)

    out = settings.out_dir()
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
    _banner("Gated upload")
    print(f"  {report.render()}")
    if not report.configured:
        # Not a failure: a local run has no service-role key and should not
        # pretend to. It is said out loud rather than passed over in silence,
        # because "uploaded nothing" and "uploaded everything" otherwise look
        # identical from the outside.
        return 0
    return 0 if report.ok else 1


def cmd_all(args) -> int:
    from types import SimpleNamespace
    from data import universe
    conn = _conn()
    funnel = universe.refresh(conn)
    _banner("Universe")
    print(funnel.render())
    return cmd_publish(SimpleNamespace())
