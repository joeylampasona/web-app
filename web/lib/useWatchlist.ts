"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./auth";

const KEY = "watchlist.v1";
export const MAX_TICKERS = 50;

/**
 * Up to 50 tickers. Storage is local for now; when the auth provider is chosen
 * this moves behind the same seam as `useAuth`, and the list travels with the
 * account rather than the browser.
 */
export function useWatchlist() {
  const { signedIn, requireSignUp } = useAuth();
  const [symbols, setSymbols] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) setSymbols(JSON.parse(raw) as string[]);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const persist = useCallback((next: string[]) => {
    setSymbols(next);
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  }, []);

  const has = useCallback((symbol: string) => symbols.includes(symbol), [symbols]);

  const toggle = useCallback(
    (symbol: string) => {
      if (!signedIn) {
        requireSignUp("Save this to a watchlist");
        return;
      }
      if (symbols.includes(symbol)) {
        persist(symbols.filter((s) => s !== symbol));
      } else if (symbols.length < MAX_TICKERS) {
        persist([...symbols, symbol]);
      }
    },
    [persist, requireSignUp, signedIn, symbols],
  );

  return { signedIn, symbols, has, toggle, full: symbols.length >= MAX_TICKERS };
}
