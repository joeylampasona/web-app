"""Industry and theme aggregation. Two parallel classifications, one machinery."""
from __future__ import annotations

from collections.abc import Iterable

from data import classify, settings
from data.market import Market
from patterns.indicators import mean, percentile_ranks
from rankings.rs import Bundle

SPANS = ("w1", "m1", "m3")


def membership(market: Market, kind: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if kind == "industry":
        for symbol, industry in market.industries.items():
            out.setdefault(classify.slugify(industry), []).append(symbol)
    elif kind == "theme":
        for symbol, slugs in market.themes.items():
            if symbol not in market.universe:
                continue
            for slug in slugs:
                out.setdefault(slug, []).append(symbol)
    else:
        raise ValueError(f"unknown group kind {kind!r}")
    return out


def display_name(kind: str, slug: str, market: Market) -> str:
    if kind == "theme":
        return classify.theme_names().get(slug, slug.replace("-", " ").title())
    for symbol, industry in market.industries.items():
        if classify.slugify(industry) == slug:
            return classify.pretty_industry(industry)
    return slug.replace("-", " ").title()


def aggregate(market: Market, bundle: Bundle, kind: str,
              breakout_symbols: Iterable[str] = (),
              min_members: int | None = None) -> list[dict]:
    """One row per group with 10+ members: RS, leaders, fresh breakouts, deltas."""
    breakouts = set(breakout_symbols)
    leader_rs = int(settings.get("rankings.leader_rs", 80))
    if min_members is not None:
        floor = int(min_members)
    elif kind == "theme":
        # A curated theme is allowed to be small. Quantum Computing has about
        # five public names, and that is the point of it being a theme rather
        # than an industry — the industry floor would simply delete it.
        floor = int(settings.get("rankings.min_theme_members", 4))
    else:
        floor = int(settings.get("rankings.min_group_members", 10))

    groups = membership(market, kind)
    raw: dict[str, float] = {}
    kept: dict[str, list[str]] = {}
    for slug, members in groups.items():
        if len(members) < floor:
            continue
        scores = [bundle.now[m] for m in members if isinstance(bundle.now.get(m), int)]
        if not scores:
            continue
        kept[slug] = members
        raw[slug] = mean(scores)

    ranked = percentile_ranks(raw)
    rows: list[dict] = []
    for slug, members in kept.items():
        member_rs = [bundle.now[m] for m in members if isinstance(bundle.now.get(m), int)]
        row = {
            "slug": slug,
            "kind": kind,
            "name": display_name(kind, slug, market),
            "members": len(members),
            "rs_rating": ranked.get(slug),
            "avg_member_rs": round(mean(member_rs), 1),
            "leaders": sum(1 for r in member_rs if r >= leader_rs),
            "fresh_breakouts": sum(1 for m in members if m in breakouts),
            "market_value": round(sum(market.caps.get(m, 0.0) for m in members)),
            "symbols": sorted(members, key=lambda m: -(bundle.now.get(m) or 0)
                              if isinstance(bundle.now.get(m), int) else 1),
        }
        for span in SPANS:
            prior = [getattr(bundle, span)[m] for m in members
                     if isinstance(getattr(bundle, span).get(m), int)]
            row[f"rs_change_{span}"] = (round(mean(member_rs) - mean(prior), 1)
                                        if prior else None)
        rows.append(row)

    rows.sort(key=lambda r: -(r["rs_rating"] or 0))
    return rows


def render_table(rows: list[dict], limit: int = 15) -> str:
    head = f"  {'Group':<34}{'RS':>4}{'Avg':>6}{'Lead':>6}{'Δ1m':>7}{'Members':>9}"
    out = [head, "  " + "─" * (len(head) - 2)]
    for r in rows[:limit]:
        delta = r.get("rs_change_m1")
        out.append(f"  {r['name'][:33]:<34}{r['rs_rating'] or 0:>4}"
                   f"{r['avg_member_rs']:>6.1f}{r['leaders']:>6}"
                   f"{('—' if delta is None else f'{delta:+.1f}'):>7}{r['members']:>9}")
    return "\n".join(out)
