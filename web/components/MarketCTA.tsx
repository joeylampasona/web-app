import Link from "next/link";

/** Repeats at the bottom of every Market destination. */
export function MarketCTA() {
  return (
    <Link
      href="/watchlist"
      className="card between"
      style={{ marginTop: "var(--pad-xl)", minHeight: "var(--h-control)" }}
    >
      <span>Where do your stocks sit on this map?</span>
      <span className="dim">Build your watchlist →</span>
    </Link>
  );
}
