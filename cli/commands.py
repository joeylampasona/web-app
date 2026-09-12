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
    from data import universe
    conn = _conn()
    run = store.start_run(conn, "universe")
    try:
        if args.refresh:
            def progress(day: dt.date, count: int) -> None:
                if count:
                    print(f"  {day}  {count:,} bars")
            funnel = universe.refresh(conn, progress=progress)
        else:
            funnel = universe.build(conn)
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
        print("\n  Nothing survived. Run with --refresh first.")
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
