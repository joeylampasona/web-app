"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useWatchlist } from "@/lib/useWatchlist";
import { isRanked } from "@/lib/format";
import { StageBadge } from "./Badges";
import { TickerLink } from "./StockDrawer";
import type { WatchRow } from "./WatchlistPanel";

/**
 * The watchlist, as a strip on the home page rather than a wall.
 *
 * Signed out this is one line, not a locked panel. Most people arriving here
 * have no account, and a home page that is half "sign up to see this" is a
 * worse greeting than the screen we used to dump them on. The offer is made
 * once, quietly, and the rest of the page carries on being useful.
 *
 * Signed in, the only thing promoted is a dated event inside a week. That is
 * the one piece of watchlist news that is actually urgent — being caught by an
 * earnings date on a position is a specific, avoidable mistake — and everything
 * else is a tap away on the watchlist page.
 */

const SOON_DAYS = 7;

export function HomeWatchlist({ rows }: { rows: WatchRow[] }) {
  const { ready: authReady } = useAuth();
  const { signedIn, ready, symbols, loading } = useWatchlist();

  // Until the stored session has been read, neither answer is true. Flashing
  // the sign-up offer at someone who is already signed in reads as a fault.
  if (!authReady || !ready) return null;

  if (!signedIn) {
    return (
      // The eyebrow is here for the same reason the signed-in version has one:
      // without it this line sits under "What moved" and reads as its last
      // sentence rather than as a section of its own.
      <section className="stack" style={{ gap: "var(--gap-xs)" }}>
        <div className="eyebrow">Watchlist</div>
        <p className="footnote muted" style={{ margin: 0, maxWidth: "62ch" }}>
          <Link href="/signin?reason=Keep%20a%20watchlist&next=%2F" style={{ textDecoration: "underline" }}>
            Keep a watchlist
          </Link>{" "}
          and this is where anything dated inside a week on your names would show up.
          No password, just a code.
        </p>
      </section>
    );
  }

  if (loading) return <p className="muted footnote" style={{ margin: 0 }}>Fetching your list.</p>;

  const held = rows.filter((row) => symbols.includes(row.symbol));

  if (held.length === 0) {
    return (
      <p className="footnote muted" style={{ margin: 0 }}>
        Your watchlist is empty. Star a ticker anywhere on the site and it lands here.
      </p>
    );
  }

  const ranked = held.filter((row) => isRanked(row.rs_rating)) as (WatchRow & { rs_rating: number })[];
  const average = ranked.length
    ? ranked.reduce((sum, row) => sum + row.rs_rating, 0) / ranked.length
    : null;
  const soon = held
    .filter((row) => row.days_until_earnings !== null && row.days_until_earnings <= SOON_DAYS)
    .sort((a, b) => (a.days_until_earnings ?? 0) - (b.days_until_earnings ?? 0));

  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
        <div>
          <div className="eyebrow">Your watchlist</div>
          <h2 style={{ fontSize: "var(--size-h3)", margin: "var(--gap-xs) 0 0 0" }}>
            {held.length} {held.length === 1 ? "name" : "names"}
            {average !== null && (
              <span className="muted" style={{ fontWeight: 400 }}>
                {" "}· average RS {average.toFixed(0)}
              </span>
            )}
          </h2>
        </div>
        <Link href="/watchlist" className="footnote"
              style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
          Open the list
        </Link>
      </div>

      {soon.length === 0 ? (
        <p className="footnote muted" style={{ margin: 0 }}>
          Nothing on your list reports inside {SOON_DAYS} days.
        </p>
      ) : (
        <div className="card stack" style={{ gap: "var(--gap-xs)", borderColor: "var(--warn-border)" }}>
          <div className="footnote" style={{ color: "var(--warn)" }}>
            Reporting inside {SOON_DAYS} days
          </div>
          {soon.map((row) => (
            <div key={row.symbol} className="row between" style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
              <span className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline", minWidth: 0 }}>
                <TickerLink symbol={row.symbol} className="mono">{row.symbol}</TickerLink>
                <span className="caption dim" style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {row.name}
                </span>
                {row.stage && <StageBadge stage={row.stage} />}
              </span>
              <span className="footnote mono" style={{ flexShrink: 0 }}>
                {row.days_until_earnings === 0
                  ? "that session"
                  : `${row.days_until_earnings}d`}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
