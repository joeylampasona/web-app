import { CalendarPanel, type CalendarNames } from "@/components/CalendarPanel";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { getMeta, getReleases, getSearchIndex, getUpcoming, hasData } from "@/lib/data";

export default function CalendarPage() {
  if (!hasData()) return <NoData />;
  const upcoming = getUpcoming();
  if (!upcoming) return <NoData />;
  const releases = getReleases();
  // Only the names with an event, so the page carries what it draws.
  const dated = new Set(upcoming.events.map((e) => e.ticker));
  const names: CalendarNames = {};
  for (const row of getSearchIndex()) {
    if (!dated.has(row.symbol)) continue;
    names[row.symbol] = [typeof row.rs_rating === "number" ? row.rs_rating : null,
                         row.on_screen?.length ?? 0];
  }

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · what is dated</div>
      <h1>The calendar</h1>
      <p className="muted footnote">
        Earnings, ex-dividend dates and splits for the names this site follows,
        plus the economic data releases scheduled for the same days. A week at
        a time, a column per day, strongest names first.
      </p>
      <p className="caption dim">
        Most earnings dates are projections from a company&rsquo;s own reporting
        history rather than a date it has announced: a dashed chip is an
        estimate, a solid one is confirmed. A date is a date, not a view about what the number will be.
      </p>
      <CalendarPanel file={upcoming} releases={releases} names={names} />
      <MarketCTA />
    </div>
  );
}
