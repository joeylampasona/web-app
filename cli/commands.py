"""One function per subcommand. Each prints something a human can read."""
from __future__ import annotations

import datetime as dt

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

    calendar = ev.build(market, population, adapter)
    ev.attach(calendar, result.all_setups())

    # Form 4s for the names on a screen. Filings never change once filed, so
    # this only ever fetches ones we have not read; the first run is the slow
    # one and every run after it is nearly free.
    from data import insiders
    from data.edgar import EdgarUnavailable
    try:
        def insider_progress(done: int, total: int, added: int) -> None:
            print(f"  → insider filings {done:,}/{total:,} — {added:,} new", flush=True)

        print(f"  → Reading insider filings for {len(population):,} names. "
              f"The first run takes a while; later ones read only what is new.",
              flush=True)
        added = insiders.fetch(conn, population, progress=insider_progress)
        print(f"  → {added:,} new Form 4 filings read.", flush=True)
    except EdgarUnavailable as exc:
        # A missing industry is a worse page; missing insider data is a missing
        # section. Neither is worth failing a nightly run over.
        print(f"  → Insider filings skipped: {exc}", flush=True)

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
    rows = ivmod.compute(calendar, population, names, adapter)
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


def _pipeline(conn, with_backtests: bool = True):
    """The nightly sequence, shared by `publish` and `all`."""
    from backtest import engine, metrics
    from backtest.settings import BacktestSettings
    from catalysts import events as ev, iv as ivmod
    from data.adapters import get_adapter
    from data.market import load
    from patterns import followthrough, scan
    from patterns.params import SCREEN_KEYS
    from rankings import rs

    market = load(conn, include_all=True)
    bundle = rs.Bundle(market)
    result = scan.run(market, bundle)
    changes = scan.diff(conn, result)
    adapter = get_adapter()

    population = sorted({s.symbol for s in result.all_setups()})
    calendar = ev.build(market, population, adapter)
    ev.attach(calendar, result.all_setups())
    names = {s: (market.refs[s].name if s in market.refs else s) for s in population}
    iv_rows = ivmod.compute(calendar, population, names, adapter)

    backtests: dict[str, dict] = {}
    follow: dict = {}
    # Read from the cache the catalysts stage fills; publish never fetches.
    # Fetching is limited to names on a screen, because each one costs SEC
    # requests. Reading is not: a name that has left a screen still has the
    # filings we already read, and its page should still show them.
    from catalysts import news as news_mod
    from data import insiders as insiders_mod
    insider_rows = insiders_mod.summary(conn, market.universe)
    news_rows = news_mod.by_symbol(conn, market.universe)
    if with_backtests:
        earnings = {s: e.date for s in market.universe
                    if (e := calendar.next_earnings(s)) is not None}
        # Four backtests over years of prices, and nothing to show for the best
        # part of a minute. Silence that long is indistinguishable from a hang,
        # so say what is happening and tick as each one lands.
        print(f"  → Replaying {len(SCREEN_KEYS)} default backtests over "
              f"{len(market.calendar):,} sessions. A minute or so.", flush=True)
        timeline = engine.rs_timeline(market)      # computed once, reused per screen
        for index, screen in enumerate(SCREEN_KEYS, 1):
            config = BacktestSettings.parse({"screen": screen})
            run_out = engine.run(market, config, earnings, timeline)
            summary = metrics.summarise(run_out)
            backtests[config.hash()] = summary
            print(f"    {index}/{len(SCREEN_KEYS)}  {screen} — "
                  f"{len(summary.get('trades', []))} trades", flush=True)
        print("  → Checking what happened to recent breakouts.", flush=True)
        follow = followthrough.compute(market, timeline)
        for key, row in follow["screens"].items():
            print(f"    {key} — {row['settled']} settled, {row['up']} up, "
                  f"{row['failed_fast']} failed fast", flush=True)
    return (market, bundle, result, changes, calendar, iv_rows, backtests,
            follow, insider_rows, news_rows)


def cmd_publish(args) -> int:
    from publish import schema, writer
    conn = _conn()
    run = store.start_run(conn, "publish")
    (market, bundle, result, changes, calendar, iv_rows, backtests,
     follow, insider_rows, news_rows) = _pipeline(conn)
    written = writer.publish(market, bundle, result, calendar, iv_rows, changes, backtests,
                             follow=follow, insiders=insider_rows,
                             news=news_rows)

    out = settings.out_dir()
    _banner(f"Published — {len(written)} files under {out}")
    tree = {}
    for path in written:
        rel = path.relative_to(out)
        key = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        tree[key] = tree.get(key, 0) + 1
    for key in sorted(tree):
        print(f"  {key:<16}{tree[key]:>5} file(s)")

    import json
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
    store.finish_run(conn, run, "ok" if not problems else "failed", f"{len(written)} files")
    return 0 if not problems else 1


def cmd_all(args) -> int:
    from types import SimpleNamespace
    from data import universe
    conn = _conn()
    funnel = universe.refresh(conn)
    _banner("Universe")
    print(funnel.render())
    return cmd_publish(SimpleNamespace())
