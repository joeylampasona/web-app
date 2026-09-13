"use client";

import { AuthGate } from "./AuthGate";
import { StageBadge } from "./Badges";
import { TickerLink } from "./StockDrawer";
import { useWatchlist, MAX_TICKERS } from "@/lib/useWatchlist";
import { rsText } from "@/lib/format";

export interface WatchRow {
  symbol: string; name: string; rs_rating: number | string;
  stage: string | null; earnings_within_7d: boolean;
  days_until_earnings: number | null;
}

export function WatchlistPanel({ rows }: { rows: WatchRow[] }) {
  const { signedIn, ready, symbols, loading, error } = useWatchlist();

  if (!ready) return null;

  if (!signedIn) {
    return (
      <AuthGate
        reason="Keep a watchlist"
        blurb={`Up to ${MAX_TICKERS} tickers, with the average RS of the list, how many
                of them are leaders, and anything with a dated event inside a week
                pinned to the top.`}
      />
    );
  }

  if (loading) {
    return <p className="muted footnote">Fetching your list.</p>;
  }

  const held = rows.filter((row) => symbols.includes(row.symbol));
  const ranked = held.filter((row) => typeof row.rs_rating === "number") as
    (WatchRow & { rs_rating: number })[];
  const average = ranked.length
    ? ranked.reduce((sum, row) => sum + row.rs_rating, 0) / ranked.length
    : null;
  const leaders = ranked.filter((row) => row.rs_rating >= 80).length;
  const soon = held.filter((row) => row.earnings_within_7d);
  const rest = held.filter((row) => !row.earnings_within_7d);

  return (
    <div className="stack">
      {error && (
        <p className="footnote" style={{ color: "var(--warn)" }}>
          Your list could not be read just now: {error}
        </p>
      )}
      <div className="grid-2">
        <div className="card">
          <div className="footnote muted">Average RS</div>
          <div className="num" style={{ fontSize: "var(--size-h2)" }}>
            {average === null ? "—" : average.toFixed(0)}
          </div>
        </div>
        <div className="card">
          <div className="footnote muted">Leaders</div>
          <div className="num" style={{ fontSize: "var(--size-h2)" }}>{leaders}</div>
        </div>
      </div>
      {soon.length > 0 && (
        <section>
          <div className="eyebrow">Dated event inside a week</div>
          {soon.map((row) => <Row key={row.symbol} row={row} />)}
        </section>
      )}
      <section>
        <div className="eyebrow">Holdings</div>
        {rest.map((row) => <Row key={row.symbol} row={row} />)}
        {held.length === 0 && (
          <p className="muted footnote">Nothing saved yet. Tap the star on any card.</p>
        )}
      </section>
    </div>
  );
}

function Row({ row }: { row: WatchRow }) {
  return (
    <TickerLink symbol={row.symbol} className="card between"
                style={{ padding: "var(--pad-md) var(--pad-lg)", width: "100%",
                         marginBottom: "var(--gap-sm)" }}>
      <span className="grow">
        <span className="mono">{row.symbol}</span> <span>{row.name}</span>
      </span>
      <span className="row" style={{ gap: "var(--gap-sm)" }}>
        {row.stage && <StageBadge stage={row.stage} />}
        <span className="num dim">{rsText(row.rs_rating)}</span>
      </span>
    </TickerLink>
  );
}
