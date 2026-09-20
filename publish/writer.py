"""Writes the out/ tree. Local only — wiring R2 or a CDN is a stop condition."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
from typing import Any

from catalysts import events as ev
from catalysts import iv as ivmod
from catalysts import news as newsmod
from data import classify, settings
from data.market import Market
from patterns import detectors, flags as flagsmod, params as param_module
from patterns import scan, stages
from publish import schema
from rankings import breadth, groups, indexes as index_rows
from rankings import spark
from backtest.settings import OPTIONS, BacktestSettings
from rankings import rotation, rs, seasonals, treemap

VERSION = 1

# How many names the gamma page carries. Deep option books are concentrated in
# a few hundred names, and the tail is mostly one stale expiry.
GAMMA_LEADERBOARD = 60

# How many names the relative-volume page carries.
VOLUME_LEADERBOARD = 120

SEASONAL_COPY = {
    "header": "What each month actually did, year by year. A grid rather than an "
              "average, so you can see how many months are behind every number.",
    "subhead": "Close to close, compounded within the year.",
    "footer": "This is a record of what happened, not a base rate. Real seasonal "
              "work uses decades; this site holds under four years, because that "
              "is what its data tier serves. The average row carries the number of "
              "months behind it for that reason — an average of three Septembers "
              "and an average of eighty are different objects, and only the n "
              "tells them apart. Four observations cannot tell you what the fifth "
              "will do.",
}

INSIDER_COPY = {
    "header": "Open-market purchases and sales by officers, directors and 10% "
              "owners, day by day. Only the decisions — grants, option exercises "
              "and shares withheld to pay tax are left out, because those happen "
              "on a vesting schedule nobody chose the date of.",
    "subhead": "From Form 4, filed within two business days and under penalty of perjury.",
    "footer": "A purchase is somebody spending their own money on their own company, "
              "which is the most interesting thing in this file. It is still not a "
              "recommendation, and insiders are wrong as often as anyone else. "
              "Institutional dark-pool blocks are not shown: there is no free, "
              "automatic source for them, and a number with nothing behind it is "
              "worse than an absence.",
}

# The colour bands. Stated here rather than in the web layer so the thresholds
# the page draws and the thresholds anything else reads can never disagree.
VOLUME_BANDS = [
    {"key": "extreme", "min": 5.0, "label": "5x and above"},
    {"key": "heavy", "min": 3.0, "label": "3 to 5x"},
    {"key": "elevated", "min": 2.0, "label": "2 to 3x"},
    {"key": "above", "min": 1.5, "label": "1.5 to 2x"},
    {"key": "normal", "min": 0.0, "label": "under 1.5x"},
]

VOLUME_COPY = {
    "header": "Each name's volume in the session that just closed, against its own "
              "average over the fifty before it. 3x means three times its normal "
              "day.",
    "subhead": "Measured on the last completed session, not intraday.",
    "footer": "Heavy volume says a lot of shares changed hands. It does not say who "
              "was buying, and a heavy down day looks identical to a heavy up day "
              "in this column — the change beside it is what separates them.",
}

GAMMA_COPY = {
    "header": "Where open interest concentrates option gamma, for the names with "
              "the deepest option books. Bigger numbers mean more optionality "
              "anchored at a strike — not a forecast of anything.",
    "subhead": "Ranked by contracts outstanding, not by the size of the gamma figure.",
    "footer": "Open interest is published once a day and reaches us with a lag, so "
              "these describe the previous session's book. The signed column "
              "assumes market makers are long calls and short puts, which is the "
              "usual convention and is not in the data.",
}

DISCLAIMER = (
    "A screening and market-analytics tool. Not investment advice. We are not a "
    "registered investment adviser. A stock on a screen matches a shape; that is "
    "not a prediction. Prices are end-of-day, not live.")

TRADE_STEPS = [
    {"step": 1, "title": "Buy the breakout", "text": "As it pushes through the pivot.",
     "tone": "gain"},
    {"step": 2, "title": "Set a safety net",
     "text": "An automatic exit if it drops about 8% from where you got in.",
     "tone": "loss"},
    {"step": 3, "title": "Lock in \"no loss\"",
     "text": "Once it is up enough, move that net to where you started.", "tone": "gain"},
    {"step": 4, "title": "Ride the trend", "text": "Raise the net as it climbs.",
     "tone": "gain"},
    {"step": 5, "title": "Step off", "text": "When the trend breaks.", "tone": "flat"},
]
TRADE_STEPS_PREFACE = ("Risk is decided before entry — about 1.5% of capital on any one "
                       "trade.")


def _write(path: pathlib.Path, payload: Any) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=False,
                               default=str), encoding="utf-8")
    return path


# Bars are the whole weight of this tree: as objects they were 24KB a stock and
# 54MB overall, which is not something you commit every weeknight. As rows they
# are under half that, and the web layer expands them back at its own boundary
# so no component knows the difference.
BAR_FORMAT = ["time", "open", "high", "low", "close", "volume"]


def _sma_tail(market: Market, symbol: str, window: int, limit: int) -> list[float | None]:
    """The last `limit` values of one moving average, aligned to the bars.

    None where the average does not exist yet — the line starts where the
    history does, rather than being drawn from a number we do not have.
    """
    from patterns.indicators import sma
    if limit <= 0:
        return []
    bars = market.series.get(symbol) or []
    if len(bars) < window:
        return []
    line = sma([b.close for b in bars], window)[-limit:]
    return [round(v, 2) if v is not None else None for v in line]


def _bars_for(market: Market, symbol: str, limit: int) -> list[list]:
    if limit <= 0:          # [-0:] is the whole list, not none of it
        return []
    return [[b.date.isoformat(), b.open, b.high, b.low, b.close, b.volume]
            for b in (market.series.get(symbol) or [])[-limit:]]


def publish(market: Market, bundle: rs.Bundle, result: scan.ScanResult,
            calendar: ev.Calendar, iv_rows: list, diff_payload: dict,
            backtests: dict[str, dict] | None = None,
            follow: dict | None = None,
            insiders: dict[str, dict] | None = None,
            news: dict[str, list[dict]] | None = None,
            desk: dict[str, list[dict]] | None = None,
            desk_run: dict | None = None,
            releases: list | None = None,
            gamma: dict[str, dict] | None = None,
            insider_recent: list[dict] | None = None,
            forecasts: dict[str, dict] | None = None,
            out: pathlib.Path | None = None) -> list[pathlib.Path]:
    out = out or settings.out_dir()
    written: list[pathlib.Path] = []
    as_of = market.as_of
    breakout_symbols = result.fresh_breakout_symbols()
    theme_names = classify.theme_names()

    # ---- screens ------------------------------------------------------
    for key, setups in result.screens.items():
        spec = param_module.SCREENS[key]
        grouped = {stage: [s.to_json() for s in setups if s.stage == stage]
                   for stage in stages.ORDER}
        written.append(_write(out / "screens" / f"{key}.json", {
            "screen": key,
            "name": spec.name,
            "description": spec.description,
            "as_of": as_of.isoformat(),
            "total": len(setups),
            "stage_counts": {stage: len(rows) for stage, rows in grouped.items()},
            # Per screen, not global: a screen that reads downward says
            # "Fresh breakdowns" and "Falling" where the others say "Fresh
            # breakouts" and "Climbing". Same stage keys underneath, so every
            # count and filter on the site keeps working.
            "direction": detectors.direction_of(key),
            # Whether the follow-through page has anything to say about this
            # screen. It replays history through the base engine, which cannot
            # reconstruct a fitted trendline, so the shape screens are absent
            # from it and must not link to it.
            "has_followthrough": key in param_module.BASE_SCREEN_KEYS,
            "stage_labels": stages.labels_for(detectors.direction_of(key)),
            "stage_help": stages.help_for(detectors.direction_of(key), as_of.year),
            "setups": grouped,
        }))
    written.append(_write(out / "screens" / "diff.json", diff_payload))

    # ---- breakouts by session ----------------------------------------
    # Long screens only: this file is read as "what broke out today" by the
    # home page and the market pages, and a bear flag's fresh bucket is the
    # opposite event.
    fresh = [s for s in result.all_setups()
             if s.stage == stages.FRESH and s.direction != stages.SHORT]
    seen: dict[str, dict] = {}
    for setup in sorted(fresh, key=lambda s: -(s.breakout_metrics.get(
            "breakout_day_gain_pct") or 0)):
        seen.setdefault(setup.symbol, setup.to_json())
    written.append(_write(out / "breakouts" / f"{as_of.isoformat()}.json", {
        "date": as_of.isoformat(),
        "count": len(seen),
        "metric_set": ["breakout_day_gain_pct", "one_day_gain_pct", "now_vs_pivot_pct",
                       "breakout_volume_multiple", "close_in_range", "rs_rating",
                       "price_vs_50ma_pct"],
        "setups": list(seen.values()),
    }))
    _retain_breakouts(out / "breakouts")
    written.append(_write(out / "breakouts" / "index.json", {
        "dates": sorted(p.stem for p in (out / "breakouts").glob("*.json")
                        if _is_session_file(p))[::-1]}))

    # ---- market-wide --------------------------------------------------
    breadth_payload = breadth.compute(market)
    written.append(_write(out / "breadth.json", breadth_payload))
    written.append(_write(out / "rotation.json",
                          rotation.compute(market, bundle, breakout_symbols)))
    written.append(_write(out / "treemap.json",
                          treemap.compute(market, bundle, breakout_symbols)))

    industries = groups.aggregate(market, bundle, "industry", breakout_symbols)
    themes = groups.aggregate(market, bundle, "theme", breakout_symbols)
    written.append(_write(out / "sectors.json", {
        "as_of": as_of.isoformat(),
        "strongest": industries[:12],
        "weakest": list(reversed(industries[-12:])),
        "themes_strongest": themes[:12],
        "themes_weakest": list(reversed(themes[-12:])),
        "heating_cooling": rotation.heating_cooling(industries),
        "themes_heating_cooling": rotation.heating_cooling(themes),
        "sector_etfs": rs.etf_ratings(market),
    }))

    # Recent headlines across every name the site follows, deduplicated from
    # the per-symbol map the catalysts stage already filled. No extra fetch:
    # the news endpoint is queried market-wide once a night regardless.
    written.append(_write(out / "news.json", {
        "as_of": as_of.isoformat(),
        "articles": _news_articles(newsmod.market_wide(news or {}), market, result),
    }))

    # Broad-market indexes and the regime check, for the home page. Both are
    # read straight off bars already in the database, so this adds no requests.
    written.append(_write(out / "indexes.json", {
        "as_of": as_of.isoformat(),
        "benchmark": market.benchmark,
        "regime": index_rows.regime(market),
        "rows": index_rows.rows(market),
    }))

    setups_by_symbol: dict[str, list] = {}
    for setup in result.all_setups():
        setups_by_symbol.setdefault(setup.symbol, []).append(setup)

    for row in industries:
        written.append(_write(out / "industries" / f"{row['slug']}.json",
                              _group_payload(row, setups_by_symbol, market, bundle)))
    for row in themes:
        written.append(_write(out / "themes" / f"{row['slug']}.json",
                              _group_payload(row, setups_by_symbol, market, bundle)))

    # ---- stocks -------------------------------------------------------
    bar_limit = int(settings.get("publish.stocks_bars", 180))
    for symbol in market.universe:
        # Every name in the universe gets its price history, not only the ones
        # currently on a screen. Search reaches all of them, and a page reached
        # by searching for a company and then showing no chart reads as broken —
        # the stock still has a price, it just has no pivot drawn over it. This
        # was the other way round, and it cost about 27MB to put right.
        limit = bar_limit
        written.append(_write(out / "stocks" / f"{symbol}.json",
                              _stock_payload(market, bundle, symbol, setups_by_symbol,
                                             calendar, limit, insiders, news, desk,
                                             gamma, forecasts)))

    # One search index, so the web layer never opens two thousand files to
    # answer a keystroke.
    written.append(_write(out / "search.json", {
        "as_of": as_of.isoformat(),
        "rows": [{
            "symbol": symbol,
            "name": market.refs[symbol].name if symbol in market.refs else symbol,
            "industry": classify.pretty_industry(market.industries.get(symbol, "")),
            "rs_rating": bundle.now.get(symbol),
            "themes": market.themes.get(symbol, []),
            "on_screen": sorted({s.screen for s in setups_by_symbol.get(symbol, [])}),
            # A normalised price shape for list rows that have no room for a
            # chart -- the watchlist and search results. Null when the window
            # is too short or dead flat, so the row can say which.
            "spark": spark.shape(market.closes(symbol)),
            "spark_change_pct": spark.change_pct(market.closes(symbol)),
        } for symbol in market.universe],
    }))

    # ---- catalysts ----------------------------------------------------
    upcoming = sorted((e for rows in calendar.by_ticker.values() for e in rows
                       if e.date >= as_of), key=lambda e: (e.date, e.ticker))
    written.append(_write(out / "catalysts" / "upcoming.json", {
        "as_of": as_of.isoformat(),
        "count": len(upcoming),
        "owned": sum(1 for e in upcoming if not e.readthrough),
        "readthrough": sum(1 for e in upcoming if e.readthrough),
        "events": [e.to_json(as_of) for e in upcoming],
        "type_labels": ev.TYPE_LABELS,
    }))
    # Handed in from the cache the catalysts stage fills, like news and insiders:
    # publish never reaches the network. The file is written either way, so the
    # page can tell "not switched on" from "nothing scheduled".
    from catalysts import fomc as fomcmod, releases as rel
    release_rows = releases or []
    fomc_status = fomcmod.status(as_of)
    written.append(_write(out / "catalysts" / "releases.json", {
        "as_of": as_of.isoformat(),
        "configured": rel.configured(),
        "count": len(release_rows),
        "source": "Federal Reserve Bank of St. Louis (FRED)",
        "releases": [r.to_json(as_of) for r in release_rows],
        # Hand-kept, so it carries its own expiry — see catalysts/fomc.
        "fomc": {
            **fomc_status,
            "meetings": [m.to_json(as_of) for m in fomcmod.meetings(as_of)],
        },
    }))
    written.append(_write(out / "catalysts" / "high_iv.json", {
        "as_of": as_of.isoformat(),
        "copy": ivmod.COPY,
        "band_labels": ivmod.BAND_LABELS,
        "dots": settings.get("iv.dots", 5),
        "rows": [r.to_json() for r in iv_rows],
    }))

    # ---- seasonals ----------------------------------------------------
    #
    # The benchmark and the sector ETFs, because a month-by-month grid is a
    # market-level reading and these are the eleven slices the rest of the site
    # already ranks. Individual stocks are not here: with under four years of
    # history a single company's "March" is one or two observations, and a grid
    # of those would look like a finding.
    season_symbols = [settings.get("universe.benchmark", "SPY"),
                      *(settings.get("rankings.sector_etfs", []) or [])]
    season_rows = []
    for symbol in season_symbols:
        bars = market.series.get(symbol) or []
        grid = seasonals.build(
            symbol,
            market.refs[symbol].name if symbol in market.refs else symbol,
            bars)
        if grid is not None:
            season_rows.append(grid.to_json())
    written.append(_write(out / "market" / "seasonals.json", {
        "as_of": as_of.isoformat(),
        "copy": SEASONAL_COPY,
        "symbols": season_rows,
    }))

    # ---- insider decisions, by day ------------------------------------
    #
    # Open-market buys and sells only. The grants, option exercises and
    # tax-withholding sales are stored and shown on the stock page, where there
    # is room to explain that they happen on a vesting schedule nobody chose.
    # In a scannable grid they would be most of the rows and none of the signal.
    #
    # The dark-pool half of this request has no free, automatic source. FINRA's
    # ATS data is weekly and delayed by weeks, and inventing a "block" from
    # daily bars would be a number with nothing behind it.
    insider_days: dict[str, dict] = {}
    for row in (insider_recent or []):
        day = insider_days.setdefault(row["traded_at"], {
            "date": row["traded_at"], "buys": 0, "sells": 0,
            "buy_value": 0.0, "sell_value": 0.0, "rows": [],
        })
        value = float(row.get("value") or 0.0)
        if row["code"] == "P":
            day["buys"] += 1
            day["buy_value"] += value
        else:
            day["sells"] += 1
            day["sell_value"] += value
        day["rows"].append({
            **row,
            "name": (market.refs[row["symbol"]].name
                     if row["symbol"] in market.refs else row["symbol"]),
        })
    for day in insider_days.values():
        day["buy_value"] = round(day["buy_value"], 2)
        day["sell_value"] = round(day["sell_value"], 2)
        # Biggest first inside a day: a $4m purchase and a $9,000 one are not
        # the same event and the order should not be an accident of filing.
        day["rows"].sort(key=lambda r: -(r.get("value") or 0.0))
    written.append(_write(out / "market" / "insiders.json", {
        "as_of": as_of.isoformat(),
        "copy": INSIDER_COPY,
        "days": sorted(insider_days.values(), key=lambda d: d["date"], reverse=True),
    }))

    # ---- relative volume, across the whole universe -------------------
    #
    # Not limited to names on a screen. "Which stocks are unusually active
    # today" is a question about the market, and answering it from the ~800
    # names that happen to be in a base would answer a different one.
    volume_rows = []
    for symbol in market.universe:
        bars = market.series.get(symbol) or []
        if len(bars) < 30:
            continue
        rvol = detectors.relative_volume(bars)
        if rvol is None:
            continue
        last, prev = bars[-1], bars[-2]
        volume_rows.append({
            "symbol": symbol,
            "name": (market.refs[symbol].name if symbol in market.refs else symbol),
            "industry": classify.pretty_industry(
                market.industries.get(symbol, "Unclassified")),
            "rvol": round(rvol, 2),
            "volume": last.volume,
            "close": round(last.close, 2),
            "change_pct": (round(100.0 * (last.close / prev.close - 1.0), 2)
                           if prev.close else None),
            "close_in_range": round(flagsmod.close_in_range(last), 2),
            "market_cap": market.caps.get(symbol),
            "rs_rating": bundle.now.get(symbol),
        })
    volume_rows.sort(key=lambda row: -row["rvol"])
    written.append(_write(out / "market" / "volume.json", {
        "as_of": as_of.isoformat(),
        "count": len(volume_rows),
        "bands": VOLUME_BANDS,
        "copy": VOLUME_COPY,
        "rows": volume_rows[:VOLUME_LEADERBOARD],
    }))

    # ---- gamma, where the option book is deepest ----------------------
    #
    # Ranked by open interest rather than by the size of the gamma number.
    # Dollar gamma scales with price and with contract count, so ranking on it
    # would mostly sort the list by share price and put every expensive stock
    # at the top regardless of how many contracts were actually open. Open
    # interest is the thing being asked for — where the option book is deep.
    gamma_rows = []
    for symbol, payload in (gamma or {}).items():
        if not payload or not payload.get("levels"):
            continue
        levels = payload["levels"]
        peak = max(levels, key=lambda level: level["concentration"])
        gamma_rows.append({
            "symbol": symbol,
            "name": (market.refs[symbol].name if symbol in market.refs else symbol),
            "market_cap": market.caps.get(symbol),
            "spot": payload["spot"],
            "open_interest": payload["open_interest"],
            "expiries": payload["expiries"],
            "total_concentration": payload["total_concentration"],
            "total_net": payload["total_net"],
            "flip": payload["flip"],
            "stale": payload.get("stale", False),
            # The single strike carrying the most gamma, and where it sits
            # relative to spot. That pair is the whole reading at a glance.
            "peak_strike": peak["strike"],
            "peak_concentration": peak["concentration"],
            "peak_vs_spot_pct": (round(100.0 * (peak["strike"] / payload["spot"] - 1.0), 2)
                                 if payload["spot"] else None),
            "levels": levels,
        })
    gamma_rows.sort(key=lambda row: -(row["open_interest"] or 0))
    written.append(_write(out / "market" / "gamma.json", {
        "as_of": as_of.isoformat(),
        "count": len(gamma_rows),
        "rows": gamma_rows[:GAMMA_LEADERBOARD],
        "copy": GAMMA_COPY,
    }))

    # ---- learn --------------------------------------------------------
    for key, spec in param_module.SCREENS.items():
        written.append(_write(out / "learn" / f"{key}.json", {
            "screen": key,
            "name": spec.name,
            "shape": spec.shape,
            "description": spec.description,
            "concepts": [c.__dict__ for c in spec.concepts],
            "funnel": param_module.funnel_steps(key),
            "funnel_preface": "Every number below is a dial you can move in Filters.",
            "params": [p.to_json() for p in spec.params],
            "trade_steps": TRADE_STEPS,
            "trade_steps_preface": TRADE_STEPS_PREFACE,
        }))

    # ---- backtest presets ---------------------------------------------
    written.append(_write(out / "backtest" / "options.json", {
        "options": OPTIONS,
        "defaults": BacktestSettings.defaults().to_json(),
        "years": sorted({d.year for d in market.calendar}),
    }))
    for key, payload in (backtests or {}).items():
        written.append(_write(out / "backtest" / "presets" / f"{key}.json", payload))
    if backtests:
        # The settings of every preset, not just its hash. A custom run on a host
        # without Python has to know whether the combination it was asked for has
        # already been computed, and it cannot recompute this hash to find out —
        # that would be a second implementation of the key, in another language,
        # free to drift. Matching on the settings themselves cannot drift.
        written.append(_write(out / "backtest" / "presets" / "index.json",
                              {"default_by_screen": {
                                  s: BacktestSettings.parse({"screen": s}).hash()
                                  for s in param_module.BASE_SCREEN_KEYS},
                               "as_of": market.as_of.isoformat() if market.as_of else None,
                               "presets": {key: payload.get("settings", {})
                                           for key, payload in backtests.items()}}))

    # ---- what happened to the breakouts we showed ---------------------
    if follow:
        written.append(_write(out / "breakouts" / "followthrough.json", follow))

    # ---- meta ---------------------------------------------------------
    provider = settings.get("data.provider", "polygon")
    meta = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "provider": provider,
        "data_source": "synthetic_demo" if provider == "synthetic" else "live",
        "data_source_note": (
            "Prices on this build are a deterministic fixture, not real market data. "
            "Tickers and company names are invented." if provider == "synthetic" else ""),
        "universe_count": len(market.universe),
        "survivorship_safe": bool(settings.get("backtest.survivorship_safe", False)),
        # Which of the desk's scanners worked. An empty signal set means
        # nothing at all if the scanner that produces it failed.
        "desk_run": desk_run,
        # The one hand-kept list on the site, and how much runway it has left.
        # Carried in meta so the nightly's own summary can shout about it: a
        # list that runs out quietly is indistinguishable from a quiet calendar.
        "fomc": {"stale": fomc_status["stale"],
                 "runway_days": fomc_status["runway_days"],
                 "listed": fomc_status["listed"],
                 "message": fomc_status["message"]},
        "benchmark": market.benchmark,
        "market_wide_breakouts": int(next(
            (c["value"] for c in breadth_payload.get("cards", [])
             if c["key"] == "breakouts"), 0)),
        "screens": [{"key": k, "name": param_module.SCREENS[k].name,
                     "total": len(v), "stages": result.counts(k)}
                    for k, v in result.screens.items()],
        "themes": _theme_index(market, theme_names),
        "disclaimer": DISCLAIMER,
    }
    problems = schema.validate(meta)
    meta["schema_valid"] = not problems
    if problems:
        meta["schema_problems"] = problems
    written.append(_write(out / "meta.json", meta))
    return written


def _is_session_file(path: pathlib.Path) -> bool:
    """A dated breakout file, not a neighbour that happens to share the folder.

    Both the index and the retention sweep used to take every *.json in
    breakouts/ except index.json. followthrough.json lives there too, so it was
    listed as a DATE: getBreakoutDates()[0] returned "followthrough", the
    search page read breakouts/followthrough.json looking for setups, found a
    file with none, and showed "Nothing broke out in the last session" on every
    build since follow-through started writing there. It also counted toward
    the retention limit, quietly costing one real session.
    """
    stem = path.stem
    if len(stem) != 10 or stem[4] != "-" or stem[7] != "-":
        return False
    try:
        dt.date.fromisoformat(stem)
    except ValueError:
        return False
    return True


def _retain_breakouts(folder: pathlib.Path) -> None:
    keep = int(settings.get("publish.breakouts_retained", 30))
    files = sorted(p for p in folder.glob("*.json") if _is_session_file(p))
    for path in files[:-keep] if len(files) > keep else []:
        path.unlink()


def _group_payload(row: dict, setups_by_symbol: dict, market: Market,
                   bundle: rs.Bundle) -> dict:
    members = []
    for symbol in row["symbols"]:
        rating = bundle.now.get(symbol)
        members.append({
            "symbol": symbol,
            "name": market.refs[symbol].name if symbol in market.refs else symbol,
            "rs_rating": rating,
            "rs_change_m1": bundle.change(symbol, "m1"),
            "market_cap": market.caps.get(symbol),
            "industry": market.industries.get(symbol),
            "themes": market.themes.get(symbol, []),
            "screens": sorted({s.screen for s in setups_by_symbol.get(symbol, [])}),
            "stage": next((s.stage for s in setups_by_symbol.get(symbol, [])), None),
        })
    payload = dict(row)
    payload["members_detail"] = members
    return payload


# How far down the market-cap ranking still counts as a name most readers
# recognise. Not a hardcoded list of tickers: that would need maintaining and
# would be wrong within a quarter.
NEWS_LARGE_CAP_RANK = 25


def _structure_check(market: Market, bundle: rs.Bundle, symbol: str) -> list[dict] | None:
    """Why a stock is on no screen, measured rather than described.

    The page used to say "no base, so no pivot to draw", which is true for some
    of these names and wrong for the rest — plenty have a perfectly good base
    that is two weeks short, or sit 30% under a pivot that is really there.
    Those are different situations and a reader watching the name wants to know
    which one they are in.

    Measured against the VCP defaults, named on the page as the reference,
    because the alternative is running five screens' worth of thresholds and
    printing a matrix nobody reads.
    """
    from patterns import bases                     # noqa: PLC0415

    bars = market.series.get(symbol) or []
    if len(bars) < 30:
        return None
    params = param_module.Params("vcp")
    structure = bases.find(
        bars, int(params.base_lookback_weeks) * 5,
        float(params.swing_threshold_pct),
        min_base_sessions=int(params.min_base_weeks) * 5)

    rows: list[dict] = []

    def add(label: str, met: bool | None, detail: str) -> None:
        rows.append({"label": label, "met": met, "detail": detail})

    if structure is None:
        add("A base has formed", False,
            f"No pause of {params.min_base_weeks} weeks or more inside the last "
            f"{params.base_lookback_weeks} weeks.")
        # The rest cannot be judged without one, and reporting them as failures
        # would be inventing four more verdicts out of one absence.
        add("Long enough to count", None, "Needs a base first.")
        add("Shallow enough", None, "Needs a base first.")
        add("Close to its pivot", None, "Needs a base first.")
    else:
        weeks = structure.weeks
        depth = structure.depth_pct
        close = bars[-1].close
        gap = 100.0 * (close / structure.pivot - 1.0) if structure.pivot else None
        add("A base has formed", True,
            f"{weeks:.1f} weeks, from {structure.low:,.2f} to "
            f"{structure.pivot:,.2f}.")
        add("Long enough to count", weeks >= float(params.min_base_weeks),
            f"{weeks:.1f} weeks against {params.min_base_weeks} needed.")
        add("Shallow enough", depth <= float(params.max_base_depth_pct),
            f"{depth:.1f}% deep against {params.max_base_depth_pct}% allowed.")
        if gap is None:
            add("Close to its pivot", None, "No pivot to measure against.")
        else:
            add("Close to its pivot", gap >= -float(params.max_from_pivot_pct),
                f"{gap:+.1f}% from the pivot; listed down to "
                f"-{params.max_from_pivot_pct}%.")

    rating = bundle.now.get(symbol)
    if isinstance(rating, int):
        add("Relative strength", rating >= int(params.min_rs),
            f"RS {rating} against {params.min_rs} needed.")
    else:
        add("Relative strength", None, "Not ranked yet — too little history.")
    return rows


def _theme_index(market: Market, theme_names: dict[str, str]) -> list[dict]:
    """Every theme, with how many names are in it and how many are holding up.

    Participation is the share of the theme's members trading above their own
    50-day line. It is a blunt measure and a deliberately plain one: "eleven of
    sixteen are above their 50-day" is checkable from the same bars the rest of
    the site uses, where anything cleverer would need a weighting nobody could
    verify from the page.
    """
    from patterns.indicators import sma            # noqa: PLC0415 - as elsewhere here

    closes_by_symbol = market.series
    members: dict[str, list[str]] = {}
    for symbol in market.universe:
        for slug in market.themes.get(symbol, []):
            members.setdefault(slug, []).append(symbol)

    out: list[dict] = []
    for slug, name in sorted(theme_names.items()):
        names = members.get(slug, [])
        above = 0
        judged = 0
        for symbol in names:
            bars = closes_by_symbol.get(symbol) or []
            if len(bars) < 50:
                continue
            line = sma([b.close for b in bars], 50)[-1]
            if not line:
                continue
            judged += 1
            if bars[-1].close > line:
                above += 1
        out.append({
            "slug": slug,
            "name": name,
            "members": len(names),
            # Judged rather than members: a name without fifty sessions has no
            # 50-day line, and counting it as "below" would be a claim about a
            # line that does not exist.
            "judged": judged,
            "above_50ma": above,
            "participation_pct": (round(100.0 * above / judged, 1)
                                  if judged else None),
        })
    return out

def _news_articles(articles: list[dict], market: Market,
                   result: scan.ScanResult) -> list[dict]:
    """Headlines, with the context the site already knows about their tickers.

    Three additions, all of them facts this site holds anyway:

      kind          analysis, a law firm's wire, or the company's own release
      status        per ticker: setting up, broke down, or neither
      prominent     the article names one of the largest companies we track

    None of this ranks or scores the articles. The order stays the order they
    were published, which remains the only ordering here that is a fact.
    """
    live = {stages.FORMING, stages.FRESH, stages.CLIMBING}
    setting_up: set[str] = set()
    failing: set[str] = set()
    for setup in result.all_setups():
        if setup.direction == stages.SHORT:
            # A short setup resolving is a breakdown; it belongs with failing
            # rather than with names that are setting up to rise.
            if setup.stage in live:
                failing.add(setup.symbol)
            continue
        if setup.stage in live:
            setting_up.add(setup.symbol)
        elif setup.stage == stages.PLAYED_OUT:
            failing.add(setup.symbol)
        if "failed_poke" in (setup.flags or []):
            failing.add(setup.symbol)
    # A name doing both is setting up: the live structure is the current state
    # and the played-out one is history.
    failing -= setting_up

    ranked = sorted(market.caps.items(), key=lambda kv: -(kv[1] or 0.0))
    prominent = {symbol for symbol, _ in ranked[:NEWS_LARGE_CAP_RANK]}

    out: list[dict] = []
    for article in articles:
        tickers = article.get("tickers") or []
        out.append({
            **article,
            "kind": newsmod.classify_headline(article.get("title", "")),
            "status": {t: ("setting_up" if t in setting_up
                           else "failing" if t in failing else None)
                       for t in tickers},
            "prominent": any(t in prominent for t in tickers),
        })
    return out

def _stock_payload(market: Market, bundle: rs.Bundle, symbol: str,
                   setups_by_symbol: dict, calendar: ev.Calendar, bar_limit: int,
                   insiders: dict[str, dict] | None = None,
                   news: dict[str, list[dict]] | None = None,
                   desk: dict[str, list[dict]] | None = None,
                   gamma: dict[str, dict] | None = None,
                   forecasts: dict[str, dict] | None = None) -> dict:
    ref = market.refs.get(symbol)
    setups = setups_by_symbol.get(symbol, [])
    primary = setups[0] if setups else None
    industry = market.industries.get(symbol, "Unclassified")
    themes = market.themes.get(symbol, [])

    def peer_rows(candidates: list[str]) -> list[dict]:
        rows = []
        for peer in candidates:
            if peer == symbol:
                continue
            rating = bundle.now.get(peer)
            rows.append({"symbol": peer,
                         "name": market.refs[peer].name if peer in market.refs else peer,
                         "rs_rating": rating})
        rows.sort(key=lambda r: -(r["rs_rating"] if isinstance(r["rs_rating"], int) else -1))
        return rows[:8]

    same_industry = [s for s in market.universe if market.industries.get(s) == industry]
    same_theme = [s for s in market.universe
                  if set(market.themes.get(s, [])) & set(themes)] if themes else []

    events = calendar.sorted_for(symbol)
    return {
        "symbol": symbol,
        "name": ref.name if ref else symbol,
        "industry": classify.pretty_industry(industry),
        "industry_slug": classify.slugify(industry),
        "themes": themes,
        "list_date": ref.list_date.isoformat() if ref and ref.list_date else None,
        "as_of": market.as_of.isoformat(),
        "rs_rating": bundle.now.get(symbol),
        "rs_change_m1": bundle.change(symbol, "m1"),
        "market_cap": market.caps.get(symbol),
        "quadrant": (primary.quadrant if primary else
                     rotation.quadrant_for(bundle.now.get(symbol)
                                           if isinstance(bundle.now.get(symbol), int) else None,
                                           bundle.change(symbol, "m1"))),
        "bars_format": BAR_FORMAT,
        "bars": _bars_for(market, symbol, bar_limit),
        # Only the 200. The 9, 21 and 50 need at most fifty prior bars, and the
        # hundred and eighty we ship contain them, so the browser derives those
        # three itself. Publishing all four would add about 11MB to every
        # nightly for three lines that can be worked out from data already here.
        "sma200": _sma_tail(market, symbol, 200, bar_limit),
        "setups": [s.to_json() for s in setups],
        "primary_setup": primary.to_json() if primary else None,
        "base_history": primary.base_history if primary else [],
        "catalyst_roadmap": [e.to_json(market.as_of) for e in events],
        "insiders": (insiders or {}).get(symbol),
        # Where open interest concentrates gamma. Absent for any name with
        # no listed options, which is most of the universe, and absent
        # rather than zeroed so the page can tell the two apart.
        "gamma": (gamma or {}).get(symbol),
        # Analyst price targets and estimates. Somebody else's opinion, not a
        # reading of ours, which is why it is labelled as such on the page.
        "forecast": (forecasts or {}).get(symbol),
        # Only for names on no screen: what is and is not in place. A stock
        # already on one has its own card saying the same thing better.
        "structure_check": (None if setups
                            else _structure_check(market, bundle, symbol)),
        "news": (news or {}).get(symbol) or [],
        "desk_signals": (desk or {}).get(symbol) or [],
        "peers": {"industry": peer_rows(same_industry), "theme": peer_rows(same_theme)},
    }
