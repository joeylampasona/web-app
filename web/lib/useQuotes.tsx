"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

/** One delayed price. `change_pct` is null when there is no previous close to
 *  compare against — which is not the same as unchanged. */
export interface Quote {
  last: number;
  prev_close: number | null;
  change_pct: number | null;
  at: string | null;
}

interface QuoteSet {
  quotes: Record<string, Quote>;
  fetched_at: string | null;
  /** Until the first fetch resolves, "no quote for this symbol" and "no
   *  quotes yet" are different things, and a page that shows a stale-looking
   *  dash for one second on every load reads as broken. */
  ready: boolean;
}

const EMPTY: QuoteSet = { quotes: {}, fetched_at: null, ready: false };
const QuotesContext = createContext<QuoteSet>(EMPTY);

// The producer publishes every fifteen minutes; polling faster cannot return
// anything newer. Half that, so a page open across a publish picks it up
// without the reader reloading.
const POLL_MS = 7 * 60 * 1000;

export function QuotesProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<QuoteSet>(EMPTY);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const response = await fetch("/api/quotes");
        if (!response.ok) throw new Error(String(response.status));
        const body = await response.json();
        if (!alive) return;
        setState({
          quotes: body.quotes ?? {},
          fetched_at: body.fetched_at ?? null,
          ready: true,
        });
      } catch {
        // Ready with nothing: the pages fall back to the closing figures,
        // which is exactly what they showed before quotes existed.
        if (alive) setState((prev) => ({ ...prev, ready: true }));
      }
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return <QuotesContext.Provider value={state}>{children}</QuotesContext.Provider>;
}

/** The delayed quote for one symbol, or null. */
export function useQuote(symbol: string | null | undefined): Quote | null {
  const set = useContext(QuotesContext);
  return useMemo(() => {
    if (!symbol || !set.ready) return null;
    return set.quotes[symbol.toUpperCase()] ?? null;
  }, [set, symbol]);
}

export function useQuotesMeta() {
  const { fetched_at, ready, quotes } = useContext(QuotesContext);
  return { fetchedAt: fetched_at, ready, count: Object.keys(quotes).length };
}

/**
 * Where price sits against a pivot, using the delayed quote when there is one.
 *
 * Returns the published end-of-day figure otherwise. The two are never blended
 * and the caller is told which it got, because "3.2% above the pivot at
 * Friday's close" and "3.2% above it twenty minutes ago" are different claims
 * and the page has to be able to say which one it is making.
 */
export function useGapToPivot(
  symbol: string | null | undefined,
  pivot: number | null | undefined,
  publishedGapPct: number | null | undefined,
): { pct: number | null; delayed: boolean; at: string | null } {
  const quote = useQuote(symbol);
  if (quote && pivot && pivot > 0) {
    return {
      pct: 100 * (quote.last / pivot - 1),
      delayed: true,
      at: quote.at,
    };
  }
  return { pct: publishedGapPct ?? null, delayed: false, at: null };
}
