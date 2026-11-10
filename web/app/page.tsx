import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { HomeNews } from "@/components/HomeNews";
import { HomeRead } from "@/components/HomeRead";
import { HomeStrongest, type StrongestStock } from "@/components/HomeStrongest";
import { HomeWatchlist } from "@/components/HomeWatchlist";
import { TickerLink } from "@/components/StockDrawer";
import type { WatchRow } from "@/components/WatchlistPanel";
import {
  getAllScreens, getBreadth, getMarketContext, getDiff, getIndexes, getLeadership, getMeta,
  getNews, getRadar, getReleases,
  getSearchIndex, getSectors, getUpcoming, hasData,
} from "@/lib/data";
import { shortDate } from "@/lib/format";
import { readMarket } from "@/lib/marketRead";
import { MarketContext } from "@/components/MarketContext";
import { LayerBar } from "@/components/Leadership";
import { ScreensScale } from "@/components/ScreensScale";
import { StrengthMatrix } from "@/components/StrengthMatrix";
import { WeekAhead } from "@/components/WeekAhead";
import { SITE_NAME } from "@/lib/copy";

/**
 * Home.
 *
 * This used to redirect to the VCP screen, which answered a question nobody
 * arriving had yet. The question a daily reader actually has is "should I be
 * doing anything today, and what?", so the page is ordered by how directly
 * each part answers it: the market's condition, where strength sits, what is
 * dated, then the screens.
 *
 * Every number here is read from files the nightly run already writes. Nothing
 * on this page asked the pipeline for anything new.
 */

export const metadata = {
  title: `${SITE_NAME} — today`,
  description:
    "Whether the tape is paying for breakouts, what cleared a pivot, and what is dated in the week ahead.",
};

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
  const radar = getRadar();
  const layers = getLeadership();
  const context = getMarketContext();

  const cards = breadth?.cards ?? [];

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

  // The last twenty sessions of each check's own number, for the meter.
  const seriesOf = (key: string) =>
    (cards.find((c) => c.key === key)?.series ?? []).map((point) => point.value);
  const series: Record<string, number[]> = {
    breakouts: seriesOf("breakouts"),
    above_50ma: seriesOf("above_50ma"),
    confirmed_uptrend: seriesOf("confirmed_uptrend"),
  };
  const priced = context?.earnings_priced;

  return (
    <div className="page stack" style={{ gap: "var(--pad-xl)" }}>
      <DataBanner meta={meta} />

      <div className="stack" style={{ gap: "var(--gap-sm)", paddingTop: "var(--pad-md)" }}>
        <HomeRead read={read} session={`${shortDate(meta?.as_of)} close`}
                  series={series} radar={radar} />
        <MarketContext file={context} compact />
      </div>

      {layers?.counts && (
        <section className="home-section stack" style={{ gap: "var(--gap-lg)" }}>
          <div className="ruled-head">
            <h2>{layers.n.toLocaleString("en-US")} stocks, each against its own industry</h2>
            <span className="kicker">Change on the week in brackets</span>
          </div>
          <LayerBar s={layers} />
        </section>
      )}

      <section className="home-section home-split">
        {radar && (
          <div className="wide stack" style={{ gap: "var(--gap-lg)" }}>
            <div className="ruled-head">
              <h2>The strength matrix</h2>
              <span className="kicker">Groups against the S&amp;P 500</span>
            </div>
            <StrengthMatrix radar={radar} edges={10} />
          </div>
        )}
        {upcoming && (
          <div className="narrow stack" style={{ gap: "var(--gap-lg)" }}>
            <div className="ruled-head">
              <h2>The week ahead</h2>
              <span className="kicker">Reports per day</span>
            </div>
            <WeekAhead
              events={upcoming.events}
              releases={releases?.releases ?? []}
              fomc={releases?.fomc?.meetings ?? []}
              pricedHeld={priced?.n && priced.inside_pct != null
                ? { n: priced.n, inside_pct: priced.inside_pct } : null}
            />
          </div>
        )}
      </section>

      <section className="home-section stack" style={{ gap: "var(--gap-lg)" }}>
        <div className="ruled-head">
          <h2>The screens, on one scale</h2>
          <Link href="/market/breakouts" className="footnote"
                style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
            Every breakout
          </Link>
        </div>
        <ScreensScale screens={meta?.screens ?? []} />
        <p className="footnote muted" style={{ margin: 0 }}>
          {freshInScreens} fresh breakouts are still inside the buy window.{" "}
          {screenBreakouts.length === 0 ? (
            <>Nothing new broke out of the screens on this run.</>
          ) : (
            <>
              New on this run:{" "}
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

      <div className="home-section">
        <HomeStrongest
          industry={sectors?.strongest?.[0] ?? null}
          theme={sectors?.themes_strongest?.[0] ?? null}
          stock={strongestStock}
        />
      </div>

      <HomeWatchlist rows={watchRows} />

      <div className="home-section">
        <HomeNews articles={news?.articles ?? []} />
      </div>

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
