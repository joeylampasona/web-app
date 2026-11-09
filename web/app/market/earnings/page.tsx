import { DataBanner, NoData } from "@/components/DataBanner";
import { EarningsPricedTable } from "@/components/EarningsPricedTable";
import { EarningsReads } from "@/components/EarningsReads";
import { MarketCTA } from "@/components/MarketCTA";
import { getEarnings, getMeta, hasData } from "@/lib/data";

export default function EarningsPage() {
  if (!hasData()) return <NoData />;
  const file = getEarnings();
  if (!file) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · reporting season</div>
      <h1>Earnings</h1>

      <section className="stack" style={{ marginTop: "var(--pad-lg)" }}>
        <div className="section-head">
          <h2>Priced against realised</h2>
          <p className="footnote muted" style={{ margin: 0 }}>
            For every name reporting this week, the move the options chain
            prices (the at-the-money straddle at the first expiry after the
            report) beside what the name actually did on its last reports. A
            ratio well above one reads rich, well below reads cheap. After the
            report the actual move settles and the tally keeps score of how often
            the priced move held. From Market Desk; an options reading, not a
            call on the stock.
          </p>
        </div>
        {file.priced ? <EarningsPricedTable priced={file.priced} /> : (
          <p className="muted footnote" style={{ margin: 0 }}>
            Market Desk has not sent its priced moves yet.
          </p>
        )}
      </section>

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <div className="section-head">
          <h2>Earnings reads · the quarter as filed</h2>
          <p className="footnote muted" style={{ margin: 0 }}>
            For every company that reported in the last {file.read_days} days,
            the latest quarter from its 10-Q or 10-K beside the quarter before and
            the same quarter a year earlier: revenue and its change, gross margin
            and its move in points, operating and net income, operating and free
            cash flow, the share count against a year ago, cash and debt. Read by
            Market Desk&rsquo;s fixed rules; nothing here reads the press release.
          </p>
        </div>
        {file.reads.length + file.more.length > 0 ? <EarningsReads file={file} /> : (
          <p className="muted footnote" style={{ margin: 0 }}>
            No reads yet. Each company&rsquo;s quarters are fetched from SEC over the
            nights after it reports.
          </p>
        )}
      </section>
      <MarketCTA />
    </div>
  );
}
