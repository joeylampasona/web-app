import Link from "next/link";
import type { EarningsFile, PricedRow } from "@/lib/types";

/**
 * Priced against realised, from Market Desk's options read.
 *
 * For every name reporting this week, the move the chain prices (the
 * at-the-money straddle at the first expiry after the report) beside what the
 * name did on its last reports. The ratio is the read: well above one and the
 * premium is rich, well below and it is cheap. After the report the actual
 * move settles, and the tally says how often the priced move held. An options
 * reading scored on its own terms, not a call on the stock.
 */
function day(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC",
  });
}

function f1(v: number | null | undefined, suffix = "%"): string {
  return v == null ? "—" : `${v.toFixed(1)}${suffix}`;
}

function Read({ row, rich }: { row: PricedRow; rich: number }) {
  if (row.ratio == null) {
    return <span className="dim">{(row.hist_n ?? 0) < 3 ? "too few prints" : "—"}</span>;
  }
  if (row.ratio >= rich) return <span className="loss" style={{ fontWeight: 600 }}>rich</span>;
  if (row.ratio <= 1 / rich) return <span className="gain" style={{ fontWeight: 600 }}>cheap</span>;
  return <span className="dim">fair</span>;
}

export function EarningsPricedTable({ priced }: { priced: NonNullable<EarningsFile["priced"]> }) {
  const t = priced.tally;
  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      {t.n ? (
        <div className="row wrap footnote muted" style={{ gap: "var(--gap-lg)" }}>
          <span>settled prints <strong className="num" style={{ color: "var(--text-primary)" }}>{t.n}</strong></span>
          {t.inside_pct != null && (
            <span>priced move held <strong className="num" style={{ color: "var(--text-primary)" }}>{t.inside_pct}%</strong> of the time</span>
          )}
          {t.mean_ratio != null && (
            <span>realised / priced, mean <strong className="num" style={{ color: "var(--text-primary)" }}>{t.mean_ratio.toFixed(2)}</strong></span>
          )}
        </div>
      ) : null}

      {priced.upcoming.length > 0 ? (
        <div className="scroll-x scroll-tall card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Ticker</th><th className="text">Reports</th><th className="text">Expiry</th>
                <th>Priced move</th><th>Last prints avg</th><th>N</th><th>Ratio</th>
                <th className="text">Read</th>
              </tr>
            </thead>
            <tbody>
              {priced.upcoming.map((row) => (
                <tr key={`${row.ticker}-${row.report_date}`}>
                  <td className="text mono">
                    <Link href={`/stocks/${row.ticker}`}>{row.ticker}</Link>
                  </td>
                  <td className="text">
                    {day(row.report_date)} {row.hour && <span className="dim">{row.hour}</span>}
                  </td>
                  <td className="text dim">{day(row.expiry)}</td>
                  <td className="num" style={{ fontWeight: 600 }}>
                    {row.implied_pct == null ? "—" : `±${row.implied_pct.toFixed(1)}%`}
                  </td>
                  <td className="num">{f1(row.hist_avg_pct)}</td>
                  <td className="num dim">{row.hist_n ?? 0}</td>
                  <td className="num">{row.ratio == null ? "—" : row.ratio.toFixed(2)}</td>
                  <td className="text"><Read row={row} rich={priced.rich} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted footnote" style={{ margin: 0 }}>
          No reporters with a priced move this week yet.
        </p>
      )}

      {priced.settled.length > 0 && (
        <details>
          <summary className="footnote" style={{ cursor: "pointer" }}>
            Recently settled: {priced.settled.length} report{priced.settled.length === 1 ? "" : "s"}, priced against what happened
          </summary>
          <div className="scroll-x scroll-tall card" style={{ padding: 0, marginTop: "var(--gap-sm)" }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Ticker</th><th className="text">Reported</th><th>Priced</th>
                  <th>Moved</th><th>Moved / priced</th><th className="text">Held?</th>
                  <th>EPS surprise</th>
                </tr>
              </thead>
              <tbody>
                {priced.settled.map((row) => (
                  <tr key={`${row.ticker}-${row.report_date}`}>
                    <td className="text mono">
                      <Link href={`/stocks/${row.ticker}`}>{row.ticker}</Link>
                    </td>
                    <td className="text">{day(row.report_date)}</td>
                    <td className="num">{row.implied_pct == null ? "—" : `±${row.implied_pct.toFixed(1)}%`}</td>
                    <td className={`num ${row.realised_pct == null ? "" : row.realised_pct > 0 ? "gain" : row.realised_pct < 0 ? "loss" : ""}`}>
                      {row.realised_pct == null ? "—" : `${row.realised_pct > 0 ? "+" : ""}${row.realised_pct.toFixed(1)}%`}
                    </td>
                    <td className="num">{row.realised_ratio == null ? "—" : row.realised_ratio.toFixed(2)}</td>
                    <td className="text">{row.inside == null ? "—" : row.inside ? "inside" : <strong>outside</strong>}</td>
                    <td className="num">{row.surprise_pct == null ? "—" : `${row.surprise_pct > 0 ? "+" : ""}${row.surprise_pct.toFixed(1)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
