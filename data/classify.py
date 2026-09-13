"""Two parallel classifications per ticker: standard industry, and themes.

Industry drives breadth and the treemap. Themes are how US retail navigates,
and a ticker may sit in several of them — or in none, which is common.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable

from data import settings


# SEC publishes raw SIC descriptions, which read like the government forms they
# came from. These are display-only: the slug is still derived from the raw
# label, so the map can change without rebuilding anything.
_INDUSTRY_OVERRIDES = {
    "biological products, (no diagnostic substances)": "Biotechnology",
    "deep sea foreign transportation of freight": "Shipping",
    "crude petroleum & natural gas": "Oil & Gas Production",
    "gold and silver ores": "Gold & Silver Mining",
    "semiconductors & related devices": "Semiconductors",
    "services-computer programming, data processing, etc.": "Software & Data Services",
    "services-prepackaged software": "Software",
    "services-medical laboratories": "Medical Laboratories",
    "industrial instruments for measurement, display and control":
        "Industrial Instruments",
    "security brokers, dealers & flotation companies": "Brokers & Dealers",
    "state commercial banks": "Commercial Banks",
    "national commercial banks": "Commercial Banks",
    "electric & other services combined": "Utilities",
    "electric services": "Electric Utilities",
    "blank checks": "Blank Cheque Companies",
    "wholesale-drugs, proprietaries & druggists' sundries": "Drug Wholesalers",
    "retail-eating & drinking places": "Restaurants",
    "retail-variety stores": "Variety Stores",
    "real estate investment trusts": "REITs",
    "surgical & medical instruments & apparatus": "Medical Instruments",
    "in vitro & in vivo diagnostic substances": "Diagnostics",
    "computer storage devices": "Storage Devices",
    "printed circuit boards": "Circuit Boards",
}

_TRIM = (", nec", " nec", ", etc.", ", etc")


def pretty_industry(raw: str) -> str:
    """A readable version of an SIC description. Display only."""
    text = (raw or "").strip()
    if not text:
        return "Unclassified"
    override = _INDUSTRY_OVERRIDES.get(text.lower())
    if override:
        return override
    text = re.sub(r"^services-", "", text, flags=re.I)
    text = re.sub(r"\s*\([^)]*\)", "", text)          # drop parenthetical asides
    lowered = text.lower()
    for suffix in _TRIM:
        if lowered.endswith(suffix):
            text = text[: len(text) - len(suffix)]
            break
    text = re.sub(r"\s+and\s+", " & ", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,-")
    return text or "Unclassified"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "unclassified"


def themes_for_ticker(symbol: str, industry: str, market_cap: float | None) -> list[str]:
    industry_l = (industry or "").lower()
    hits: list[str] = []
    for theme in settings.themes():
        members = {m.upper() for m in theme.get("members", []) or []}
        if symbol.upper() in members:
            hits.append(theme["slug"])
            continue
        if any(frag.lower() in industry_l for frag in theme.get("industry_match", []) or []):
            hits.append(theme["slug"])
            continue
        floor = theme.get("min_market_cap")
        if floor and market_cap and market_cap >= float(floor):
            hits.append(theme["slug"])
    return hits


def theme_names() -> dict[str, str]:
    return {t["slug"]: t["name"] for t in settings.themes()}


def write_theme_members(conn: sqlite3.Connection,
                        rows: Iterable[tuple[str, str, float | None]]) -> int:
    """rows is (symbol, industry, market_cap)."""
    conn.execute("DELETE FROM theme_members")
    payload: list[tuple[str, str]] = []
    for symbol, industry, cap in rows:
        for slug in themes_for_ticker(symbol, industry, cap):
            payload.append((symbol, slug))
    conn.executemany(
        "INSERT OR IGNORE INTO theme_members(symbol, theme_slug) VALUES (?,?)", payload)
    conn.commit()
    return len(payload)
