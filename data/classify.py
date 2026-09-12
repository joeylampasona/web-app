"""Two parallel classifications per ticker: standard industry, and themes.

Industry drives breadth and the treemap. Themes are how US retail navigates,
and a ticker may sit in several of them — or in none, which is common.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable

from data import settings


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
