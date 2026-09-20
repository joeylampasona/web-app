import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { HomeCalendar } from "@/components/HomeCalendar";
import { HomeNews } from "@/components/HomeNews";
import { HomeRead } from "@/components/HomeRead";
import { HomeStrongest, type StrongestStock } from "@/components/HomeStrongest";
import { HomeWatchlist } from "@/components/HomeWatchlist";
import { TickerLink } from "@/components/StockDrawer";
import type { WatchRow } from "@/components/WatchlistPanel";
import {
  getAllScreens, getBreadth, getDiff, getIndexes, getMeta, getNews, getReleases,
  getSearchIndex, getSectors, getUpcoming, hasData,
} from "@/lib/data";
import { shortDate } from "@/lib/format";
import { readMarket } from "@/lib/marketRead";
import { screenClass } from "@/lib/screenColour";
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
  const indexes = getIndexes();
  const read = readMarket(breadth?.cards, indexes?.regime);
  const diff = getDiff();
  const upcoming = getUpcoming();
  const releases = getReleases();
  const news = getNews();

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
  // The strongest industry and theme are the head of a list the pipeline has
  // already ranked; the strongest stock is not published as such, so it is
  // picked here from the search index and given the stage it holds in the
  // screens. A rating without a stage beside it reads as a tip.
  const sectors = getSectors();
  const searchRows = getSearchIndex();
  const rankedStocks = searchRows.filter(
    (row): row is typeof row & { rs_rating: number } => typeof row.rs_rating === "number",
  );
  const best = rankedStocks.length
    ? rankedStocks.reduce((top, row) => (row.rs_rating > top.rs_rating ? row : top))
    : null;

  const watchRows: WatchRow[] = searchRows.map((row) => ({
    symbol: row.symbol,
    name: row.name,
    rs_rating: row.rs_rating,
    stage: stages.get(row.symbol)?.stage ?? null,
    earnings_within_7d: (stages.get(row.symbol)?.days ?? 99) <= 7,
    days_until_earnings: stages.get(row.symbol)?.days ?? null,
    spark: row.spark ?? null,
    spark_change_pct: row.spark_change_pct ?? null,
  }));

  const strongestStock: StrongestStock | null = best
    ? { symbol: best.symbol, name: best.name, rs_rating: best.rs_rating,
        stage: stages.get(best.symbol)?.stage ?? null }
    : null;

  return (
    <div className="page stack" style={{ gap: "var(--gap-xl)" }}>
      <DataBanner meta={meta} />

      <div>
        {/* The session used to be an eyebrow here. The hero chip carries it
            now, and printing the same date twice, eight pixels apart, reads
            as a mistake rather than as emphasis. */}
        <h1 style={{ marginBottom: "var(--gap-xs)" }}>Today</h1>
        <p className="muted footnote" style={{ margin: 0, maxWidth: "62ch" }}>
          Everything below is measured at the last settled session, across{" "}
          {meta?.universe_count ?? "—"} liquid US names.
        </p>
      </div>

      <HomeRead read={read} indexes={indexes?.rows ?? []}
                session={`${shortDate(meta?.as_of)} close`} />

      <HomeStrongest
        industry={sectors?.strongest?.[0] ?? null}
        theme={sectors?.themes_strongest?.[0] ?? null}
        stock={strongestStock}
      />

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

      <HomeNews articles={news?.articles ?? []} />

      {upcoming && (
        <HomeCalendar
          events={upcoming.events}
          releases={releases?.releases ?? []}
          fomc={releases?.fomc?.meetings ?? []}
          asOf={meta?.as_of ?? null}
        />
      )}

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <h2 style={{ fontSize: "var(--size-h3)", margin: 0 }}>The screens</h2>
        <div className="grid-auto">
          {(meta?.screens ?? []).map((screen) => (
            <Link
              key={screen.key}
              href={`/screens/${screen.key}`}
              className="card stack"
              style={{ gap: "var(--gap-xs)", textDecoration: "none" }}
            >
              <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
                <span className="row" style={{ gap: "var(--gap-sm)", alignItems: "center",
                                               minWidth: 0 }}>
                  <span className={`screen-dot ${screenClass(screen.key)}`} aria-hidden />
                  <span style={{ fontWeight: 500 }}>{screen.name}</span>
                </span>
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

      <HomeDisclaimer />
    </div>
  );
}

/** The short version, where everybody lands. The full text lives at /legal.
 *
 * It sits at the bottom of the home page rather than behind a tab because a
 * disclaimer nobody passes is a disclaimer nobody reads. Three things only:
 * what this is not, what a screen result is not, and where the numbers come
 * from — each the subject of a full section on /legal, which this links to
 * rather than replaces.
 */
function HomeDisclaimer() {
  return (
    <section
      className="stack"
      style={{
        gap: "var(--gap-sm)",
        marginTop: "var(--gap-lg)",
        paddingTop: "var(--pad-lg)",
        borderTop: "1px solid var(--border)",
      }}
    >
      <div className="eyebrow">Before you act on any of this</div>
      <p className="footnote muted" style={{ margin: 0 }}>
        {SITE_NAME} is a screening tool, not an investment adviser. Nothing here
        is advice, nothing here accounts for your circumstances, and there is no
        order-placing code in it.
      </p>
      <p className="footnote muted" style={{ margin: 0 }}>
        A stock on a screen matches a <em>shape</em>. That is not a prediction
        that the shape resolves upward, or at all. Prices are end-of-day, not
        live, and can be wrong, late or missing — verify anything that matters
        against your broker.
      </p>
      <p className="footnote muted" style={{ margin: 0 }}>
        Trading carries risk, including losing more than you put in. Past
        performance does not indicate future results.{" "}
        <Link href="/legal" style={{ color: "var(--link)", textDecoration: "underline" }}>
          Read the full disclaimer
        </Link>
        .
      </p>
    </section>
  );
}
