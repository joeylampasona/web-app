import { CalendarPanel } from "@/components/CalendarPanel";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { getMeta, getUpcoming, hasData } from "@/lib/data";

export default function CalendarPage() {
  if (!hasData()) return <NoData />;
  const upcoming = getUpcoming();
  if (!upcoming) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · what is dated</div>
      <h1>The calendar</h1>
      <p className="muted footnote">
        Earnings, ex-dividend dates and splits for the names this site follows,
        grouped by the day they fall on. These are the same events that badge a
        stock&rsquo;s own page.
      </p>
      <p className="caption dim">
        Most earnings dates are projections from a company&rsquo;s own reporting
        history rather than a date it has announced, and each row says which it
        is. A date is a date, not a view about what the number will be.
      </p>
      <CalendarPanel file={upcoming} />
      <MarketCTA />
    </div>
  );
}
