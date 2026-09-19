import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { HomeCalendar } from "@/components/HomeCalendar";
import { HomeRead } from "@/components/HomeRead";
import { HomeWatchlist } from "@/components/HomeWatchlist";
import { TickerLink } from "@/components/StockDrawer";
import type { WatchRow } from "@/components/WatchlistPanel";
import {
  getAllScreens, getBreadth, getDiff, getMeta, getReleases, getSearchIndex,
  getUpcoming, hasData,
} from "@/lib/data";
import { longDate } from "@/lib/format";
import { readMarket } from "@/lib/marketRead";
import { SITE_NAME } from "@/lib/copy";

/**
 * Home.
 *
 * This used to redirect to the VCP screen, which answered a question nobody
 * arriving had yet. The question a daily reader actually has is "should I be
 * doing anything today, and what?", so the page is ordered by how directly
 * each part answers it: the market's condition, what moved, what is dated, then
 * the screens.
 *
 * Every number here is read from files the nightly run already writes. Nothing
 * on this page asked the pipeline for anything new.
 */

export const metadata = {
  title: `${SITE_NAME} — today`,
  description:
    "Whether the tape is paying for breakouts, what cleared a pivot, and what is dated in the week ahead.",
};

function Stat({
  value, label, note, href,
}: {
  value: string; label: string; note?: string; href?: string;
}) {
  const body = (
    <>
      <div className="footnote muted">{label}</div>
      <div className="num" style={{ fontSize: "var(--size-h2)", lineHeight: 1.2 }}>{value}</div>
      {note && <div className="caption dim">{note}</div>}
    </>
  );
  if (!href) return <div className="card stack" style={{ gap: "var(--gap-xs)" }}>{body}</div>;
  return (
    <Link href={href} className="card stack" style={{ gap: "var(--gap-xs)", textDecoration: "none" }}>
      {body}
    </Link>
  );
}

export default function Home() {
  if (!hasData()) return <NoData />;

  const meta = getMeta();
  const breadth = getBreadth();
  const read = readMarket(breadth?.cards);
  const diff = getDiff();
  const upcoming = getUpcoming();
  const releases = getReleases();

  const cards = breadth?.cards ?? [];
  const value = (key: string) => cards.find((c) => c.key === key)?.value ?? null;
  const brokeOut = value("breakouts");
  const failedPokes = value("failed_pokes");

  // Names that entered a screen's breakout stage on this run, across all six.
  // Deliberately separate from the market-wide count above it: the market can
  // have a busy day while nothing in these screens moves at all, and conflating
  // the two would overstate what the site actually found.
  const screenBreakouts = [
    ...new Set(
      Object.values(diff?.screens ?? {}).flatMap((s) => s.broke_out_today),
    ),
  ].sort();

  const freshInScreens = (meta?.screens ?? []).reduce(
    (sum, screen) => sum + (screen.stages.fresh_breakout ?? 0), 0,
  );

  // The watchlist strip is a client component, but the rows it filters are
  // static, so they are assembled here once rather than fetched in the browser.
  const stages = new Map<string, { stage: string; days: number | null }>();
  for (const file of getAllScreens()) {
    for (const setups of Object.values(file.setups)) {
      for (const setup of setups) {
        if (!stages.has(setup.symbol)) {
          stages.set(setup.symbol, {
            stage: setup.stage,
            days: setup.catalysts?.days_until_earnings ?? null,
          });
        }
      }
    }
  }
  const watchRows: WatchRow[] = getSearchIndex().map((row) => ({
    symbol: row.symbol,
    name: row.name,
    rs_rating: row.rs_rating,
    stage: stages.get(row.symbol)?.stage ?? null,
    earnings_within_7d: (stages.get(row.symbol)?.days ?? 99) <= 7,
    days_until_earnings: stages.get(row.symbol)?.days ?? null,
  }));

  return (
    <div className="page stack" style={{ gap: "var(--gap-xl)" }}>
      <DataBanner meta={meta} />

      <div>
        <div className="eyebrow">{longDate(meta?.as_of)} close</div>
        <h1 style={{ marginBottom: "var(--gap-xs)" }}>Today</h1>
        <p className="muted footnote" style={{ margin: 0, maxWidth: "62ch" }}>
          Everything below is measured at the last settled session, across{" "}
          {meta?.universe_count ?? "—"} liquid US names.
        </p>
      </div>

      <HomeRead read={read} />

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
          <h2 style={{ fontSize: "var(--size-h3)", margin: 0 }}>What moved</h2>
          <Link href="/market/breakouts" className="footnote"
                style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
            Every breakout
          </Link>
        </div>
        <div className="grid-auto">
          <Stat
            value={brokeOut === null ? "—" : brokeOut.toFixed(0)}
            label="Cleared a pivot"
            note="Anywhere in the universe"
            href="/market/breakouts"
          />
          <Stat
            value={failedPokes === null ? "—" : failedPokes.toFixed(0)}
            label="Tested one and fell back"
            note="The cost of being early"
            href="/market/breadth"
          />
          <Stat
            value={String(freshInScreens)}
            label="Fresh breakouts in the screens"
            note="Still inside the buy window"
            href="/screens"
          />
        </div>
        <p className="footnote muted" style={{ margin: 0 }}>
          {screenBreakouts.length === 0 ? (
            <>Nothing new broke out of these six screens on this run.</>
          ) : (
            <>
              New out of the screens:{" "}
              {screenBreakouts.map((symbol, index) => (
                <span key={symbol}>
                  <TickerLink symbol={symbol} className="mono">{symbol}</TickerLink>
                  {index < screenBreakouts.length - 1 ? ", " : ""}
                </span>
              ))}
            </>
          )}
        </p>
      </section>

      <HomeWatchlist rows={watchRows} />

      {upcoming && (
        <HomeCalendar
          events={upcoming.events}
          releases={releases?.releases ?? []}
          fomc={releases?.fomc?.meetings ?? []}
          asOf={meta?.as_of ?? null}
        />
      )}

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
          <h2 style={{ fontSize: "var(--size-h3)", margin: 0 }}>The screens</h2>
          <Link href="/learn" className="footnote"
                style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
            How they work
          </Link>
        </div>
        <div className="grid-auto">
          {(meta?.screens ?? []).map((screen) => (
            <Link
              key={screen.key}
              href={`/screens/${screen.key}`}
              className="card stack"
              style={{ gap: "var(--gap-xs)", textDecoration: "none" }}
            >
              <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
                <span style={{ fontWeight: 500 }}>{screen.name}</span>
                <span className="num footnote">{screen.total}</span>
              </div>
              <div className="caption dim">
                {screen.stages.forming ?? 0} forming ·{" "}
                {screen.stages.fresh_breakout ?? 0} fresh ·{" "}
                {screen.stages.climbing ?? 0} climbing
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
