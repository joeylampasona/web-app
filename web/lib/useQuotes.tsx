"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "./auth";
import { client } from "./supabase";

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
  /** When the live half was read, and which symbols it covers. Separate from
   *  `fetched_at`, which is when the scheduled sweep ran — usually hours
   *  earlier. One timestamp over two different readings would date every
   *  number to the freshest one. */
  live_at: string | null;
  live_symbols: string[];
  /** Until the first fetch resolves, "no quote for this symbol" and "no
   *  quotes yet" are different things, and a page that shows a stale-looking
   *  dash for one second on every load reads as broken. */
  ready: boolean;
}

const EMPTY: QuoteSet = {
  quotes: {}, fetched_at: null, live_at: null, live_symbols: [], ready: false,
};
const QuotesContext = createContext<QuoteSet>(EMPTY);

// The producer publishes every fifteen minutes; polling faster cannot return
// anything newer. Half that, so a page open across a publish picks it up
// without the reader reloading.
const POLL_MS = 7 * 60 * 1000;

export function QuotesProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<QuoteSet>(EMPTY);
  const { signedIn, ready: authReady } = useAuth();

  useEffect(() => {
    let alive = true;

    /** The names a subscriber can see on a screen and a free reader cannot.
     *  Fetched separately because they are published separately — the public
     *  file carries the free sample's prices and nothing else, so without this
     *  the paid half of every screen would be the only rows on the page with
     *  no live price beside them. */
    const paid = async (): Promise<Record<string, Quote>> => {
      const supabase = client();
      if (!supabase || !signedIn) return {};
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return {};
      const response = await fetch("/api/gated?path=market%2Fquotes.json", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!response.ok) return {};
      const body = await response.json();
      return (body?.payload?.quotes ?? {}) as Record<string, Quote>;
    };

    const load = async () => {
      try {
        const response = await fetch("/api/quotes");
        if (!response.ok) throw new Error(String(response.status));
        const body = await response.json();
        // Not Promise.all: a failure here must not lose the public quotes,
        // which are the ones every reader gets.
        const extra = await paid().catch(() => ({}));
        if (!alive) return;
        setState({
          quotes: { ...(body.quotes ?? {}), ...extra },
          fetched_at: body.fetched_at ?? null,
          live_at: body.live_at ?? null,
          live_symbols: body.live_symbols ?? [],
          ready: true,
        });
      } catch {
        // Ready with nothing: the pages fall back to the closing figures,
        // which is exactly what they showed before quotes existed.
        if (alive) setState((prev) => ({ ...prev, ready: true }));
      }
    };
    if (!authReady) return;
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [signedIn, authReady]);

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
  const { fetched_at, live_at, live_symbols, ready, quotes } =
    useContext(QuotesContext);
  return {
    fetchedAt: fetched_at,
    liveAt: live_at,
    liveSymbols: live_symbols,
    ready,
    count: Object.keys(quotes).length,
  };
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
