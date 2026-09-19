"use client";

import { useWatchlist } from "@/lib/useWatchlist";

/** Auth-gated. Signed out, this points at the sign-up CTA instead of saving. */
export function WatchStar({ symbol }: { symbol: string }) {
  const { signedIn, has, toggle } = useWatchlist();
  const active = has(symbol);
  return (
    <button
      type="button"
      onClick={() => toggle(symbol)}
      aria-pressed={active}
      aria-label={
        signedIn
          ? `${active ? "Remove" : "Add"} ${symbol} ${active ? "from" : "to"} your watchlist`
          : `Sign up to add ${symbol} to a watchlist`
      }
      style={{
        background: "none", border: "none", cursor: "pointer", padding: 2,
        color: active ? "var(--brand-ink)" : "var(--text-muted)", lineHeight: 1,
      }}
    >
      {active ? "★" : "☆"}
    </button>
  );
}
