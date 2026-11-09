"use client";

import { useEffect, useMemo, useState } from "react";
import type { MarketHeadline } from "./types";

/**
 * The nightly's headlines with anything the hourly run found since laid on
 * top, newest first, each article once.
 *
 * One fetch per page view, shared by every caller on the page. Until it
 * resolves, and whenever it fails, the nightly's list is returned unchanged,
 * so nothing renders differently for a reader the hourly run never reached.
 */
let pending: Promise<MarketHeadline[]> | null = null;

function load(): Promise<MarketHeadline[]> {
  if (!pending) {
    pending = fetch("/api/news")
      .then((r) => (r.ok ? r.json() : { articles: [] }))
      .then((body) => (Array.isArray(body?.articles) ? body.articles as MarketHeadline[] : []))
      .catch(() => []);
  }
  return pending;
}

export function useLiveNews<T extends { url: string; published_at: string }>(
  nightly: T[], symbol?: string,
): (T | MarketHeadline)[] {
  const [live, setLive] = useState<MarketHeadline[]>([]);
  useEffect(() => {
    let alive = true;
    load().then((rows) => { if (alive) setLive(rows); });
    return () => { alive = false; };
  }, []);
  return useMemo(() => {
    const extra = symbol
      ? live.filter((a) => a.tickers?.includes(symbol.toUpperCase()))
      : live;
    if (!extra.length) return nightly;
    const seen = new Set(nightly.map((a) => a.url));
    const fresh = extra.filter((a) => !seen.has(a.url));
    return [...fresh, ...nightly].sort((a, b) =>
      (b.published_at || "").localeCompare(a.published_at || ""));
  }, [live, nightly, symbol]);
}
