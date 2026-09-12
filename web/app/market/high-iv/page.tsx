import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { Tooltip } from "@/components/Tooltip";
import { copy } from "@/lib/copy";
import { longDate } from "@/lib/format";
import { getHighIV, getMeta, hasData } from "@/lib/data";
import type { IVRow } from "@/lib/types";

function Dots({ filled, total }: { filled: number; total: number }) {
  return (
    <span aria-label={`${filled} of ${total}`} className="num">
      {"●".repeat(filled)}
      <span className="dim">{"○".repeat(Math.max(0, total - filled))}</span>
    </span>
  );
}

export default function HighIVPage() {
  if (!hasData()) return <NoData />;
  const iv = getHighIV();
  if (!iv) return <NoData />;

  const weeks = new Map<string, IVRow[]>();
  for (const row of iv.rows) {
    const list = weeks.get(row.week_of) ?? [];
    list.push(row);
    weeks.set(row.week_of, list);
  }

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>High IV</h1>
      <p className="muted footnote">{iv.copy.header}</p>
      <p className="caption dim">{iv.copy.subhead}</p>

      {[...weeks.entries()].map(([week, rows]) => (
        <section key={week} className="stack" style={{ marginTop: "var(--pad-lg)" }}>
          <div className="eyebrow">Week of {longDate(week)}</div>
          <div className="scroll-x card" style={{ padding: 0 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Ticker</th><th>Event</th><th>Date</th>
                  <th>
                    <span className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                      Richness <Tooltip label="Richness" text={copy("iv.richness")} />
                    </span>
                  </th>
                  <th>
                    <span className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                      Band <Tooltip label="Band" text={copy("iv.band")} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.ticker}-${row.event_date}`}>
                    <td className="text">
                      <Link href={`/stocks/${row.ticker}`} className="mono">{row.ticker}</Link>
                    </td>
                    <td className="text caption">
                      {row.event_label}
                      <span className="dim"> · {row.confirmed}</span>
                    </td>
                    <td className="caption">{longDate(row.event_date)}</td>
                    <td>{row.iv_richness.toFixed(2)}&#215;</td>
                    <td className="text">
                      <span className="row" style={{ gap: "var(--gap-sm)" }}>
                        <Dots filled={row.dots} total={iv.dots} />
                        <span className="caption dim">{iv.band_labels[row.iv_band]}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {iv.rows.length === 0 && (
        <div className="card muted footnote">
          No names qualify right now. A ticker only appears here when it has a dated
          event of its own and listed options against it.
        </div>
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{iv.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
