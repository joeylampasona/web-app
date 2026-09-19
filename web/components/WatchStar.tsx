"use client";

import { useWatchlist, MAX_TICKERS } from "@/lib/useWatchlist";

/**
 * Add or remove a ticker.
 *
 * Signed out it remembers the choice locally and sends the reader to sign-up,
 * so the tap is not lost on the way.
 *
 * `withLabel` puts a word beside the glyph. A bare star next to a company name
 * is a thing you notice once you already know it is there; on the page someone
 * reached by looking a company up, the control should say what it does. Lists
 * keep the bare glyph because a word on every row is noise.
 */
export function WatchStar({
  symbol, withLabel = false,
}: {
  symbol: string;
  withLabel?: boolean;
}) {
  const { signedIn, has, toggle, symbols, ready } = useWatchlist();
  const active = has(symbol);
  const full = signedIn && !active && symbols.length >= MAX_TICKERS;

  const label = !signedIn ? "Watch"
              : active ? "Watching"
              : full ? "List full"
              : "Watch";

  return (
    <button
      type="button"
      onClick={() => toggle(symbol)}
      aria-pressed={active}
      disabled={full}
      title={full ? `Your watchlist holds the maximum of ${MAX_TICKERS} tickers.` : undefined}
      aria-label={
        signedIn
          ? full
            ? `Watchlist full — remove one of your ${MAX_TICKERS} tickers first`
            : `${active ? "Remove" : "Add"} ${symbol} ${active ? "from" : "to"} your watchlist`
          : `Sign up to add ${symbol} to a watchlist`
      }
      className={withLabel ? "control footnote" : undefined}
      style={
        withLabel
          ? { display: "inline-flex", alignItems: "center", gap: "var(--gap-xs)",
              color: active ? "var(--brand-ink)" : undefined,
              opacity: full ? 0.6 : undefined,
              cursor: full ? "not-allowed" : "pointer" }
          : { background: "none", border: "none", padding: 2, lineHeight: 1,
              color: active ? "var(--brand-ink)" : "var(--text-muted)",
              opacity: full ? 0.5 : undefined,
              cursor: full ? "not-allowed" : "pointer" }
      }
    >
      <span aria-hidden>{active ? "★" : "☆"}</span>
      {withLabel && ready && <span>{label}</span>}
    </button>
  );
}
