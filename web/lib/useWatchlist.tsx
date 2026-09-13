"use client";

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import { useAuth } from "./auth";
import { client } from "./supabase";

const KEY = "watchlist.v1";
export const MAX_TICKERS = 50;

/**
 * Up to 50 tickers, stored against the account so the list travels between the
 * phone and the desktop rather than living in one browser.
 *
 * The list lives in one provider, not in each star. A screen renders dozens of
 * stars; if each held its own copy it would fetch the list dozens of times on
 * every page load, and starring a ticker in one place would leave the same
 * ticker unstarred everywhere else on the page.
 *
 * Writes go to the server first and only then to the screen, so a star that
 * lights up means the row landed. A failed write leaves the star where it was.
 */
interface WatchlistState {
  signedIn: boolean;
  ready: boolean;
  symbols: string[];
  has: (symbol: string) => boolean;
  toggle: (symbol: string) => void;
  loading: boolean;
  error: string | null;
  full: boolean;
}

const WatchlistContext = createContext<WatchlistState | null>(null);

export function WatchlistProvider({ children }: { children: React.ReactNode }) {
  const { signedIn, user, ready, requireSignUp } = useAuth();
  const [symbols, setSymbols] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Carrying the old local list over is a one-time act per sign-in. React
  // re-runs effects in development, and a second pass would try to insert every
  // ticker again.
  const carriedFor = useRef<string | null>(null);

  useEffect(() => {
    const supabase = client();
    if (!signedIn || !user || !supabase) {
      setSymbols([]);
      return;
    }
    let live = true;
    setLoading(true);

    (async () => {
      const { data, error: readError } = await supabase
        .from("watchlist")
        .select("symbol")
        .order("created_at", { ascending: true });
      if (!live) return;
      if (readError) {
        setError(readError.message);
        setLoading(false);
        return;
      }
      let held = (data ?? []).map((row) => row.symbol as string);

      if (carriedFor.current !== user.id) {
        carriedFor.current = user.id;
        const carried = takeLocal().filter((s) => !held.includes(s));
        const room = carried.slice(0, Math.max(0, MAX_TICKERS - held.length));
        if (room.length) {
          const { error: writeError } = await supabase
            .from("watchlist")
            .insert(room.map((symbol) => ({ user_id: user.id, symbol })));
          if (!writeError) held = [...held, ...room];
        }
        clearLocal();
      }
      if (!live) return;
      setSymbols(held);
      setError(null);
      setLoading(false);
    })();

    return () => { live = false; };
  }, [signedIn, user]);

  const has = useCallback((symbol: string) => symbols.includes(symbol), [symbols]);

  const toggle = useCallback(
    (symbol: string) => {
      if (!signedIn || !user) {
        rememberLocal(symbol);
        requireSignUp("Save this to a watchlist");
        return;
      }
      const supabase = client();
      if (!supabase) return;
      setError(null);

      void (async () => {
        if (symbols.includes(symbol)) {
          const { error: deleteError } = await supabase
            .from("watchlist").delete().eq("symbol", symbol);
          if (deleteError) { setError(deleteError.message); return; }
          setSymbols((held) => held.filter((s) => s !== symbol));
          return;
        }
        if (symbols.length >= MAX_TICKERS) return;
        const { error: insertError } = await supabase
          .from("watchlist").insert({ user_id: user.id, symbol });
        if (insertError) { setError(insertError.message); return; }
        setSymbols((held) => (held.includes(symbol) ? held : [...held, symbol]));
      })();
    },
    [requireSignUp, signedIn, symbols, user],
  );

  const value = useMemo<WatchlistState>(
    () => ({
      signedIn, ready, symbols, has, toggle, loading, error,
      full: symbols.length >= MAX_TICKERS,
    }),
    [error, has, loading, ready, signedIn, symbols, toggle],
  );

  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>;
}

export function useWatchlist(): WatchlistState {
  const context = useContext(WatchlistContext);
  if (!context) throw new Error("useWatchlist must be used inside WatchlistProvider");
  return context;
}

/**
 * Signed out, a tapped star is still a stated intent. Holding it locally means
 * the ticker is waiting on the list after the link is clicked, instead of the
 * tap being thrown away while the sign-up sheet is open.
 */
function rememberLocal(symbol: string) {
  try {
    const held = takeLocal();
    if (held.includes(symbol) || held.length >= MAX_TICKERS) return;
    window.localStorage.setItem(KEY, JSON.stringify([...held, symbol]));
  } catch {
    /* storage unavailable */
  }
}

function takeLocal(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((s) => typeof s === "string") : [];
  } catch {
    return [];
  }
}

function clearLocal() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}
