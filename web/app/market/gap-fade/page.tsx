import type { Metadata } from "next";
import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { PriceChange } from "@/components/PriceChange";
import { getGapFade, getMeta, hasData } from "@/lib/data";
import { compactMoney, longDate } from "@/lib/format";
import { SITE_NAME } from "@/lib/copy";
import type { FadeReading, GapFadeFile, GapFadeRow } from "@/lib/types";

export const metadata: Metadata = {
  title: `Gap fade watch — ${SITE_NAME}`,
  description: "Liquid stocks that gapped with no filing and no results behind the move, "
               + "and what such gaps have done since.",
};

/**
 * The Market Desk's fade watch, as the desk publishes it.
 *
 * A gap with nothing behind it tends to give some of itself back; that is the
 * claim, and the desk's own record is printed under each side so a reader can
 * see how well it has held lately. Never a buy or sell list: the desk calls it
 * context and never scores it, and so does this page.
 */
function recordSentence(way: "up" | "down", h3?: FadeReading | null,
                        h20?: FadeReading | null): string {
  const slice = way === "up" ? "gapped up" : "gapped down";
  if (!h3 && !h20) return `No matured readings yet for names that ${slice} without news.`;
  const lead = h3 ?? h20!;
  if (lead.thin) {
    return `Too few readings yet to say what names that ${slice} without news have `
         + `done since (${lead.n} so far).`;
  }
  const verb = (x: number) => (x >= 0 ? "outrun" : "trailed");
  const by = (x: number) => `${Math.abs(x).toFixed(1)}%`;
  const short = h3 && h3.x != null && !h3.thin ? h3.x : null;
  const long = h20 && h20.x != null && !h20.thin ? h20.x : null;
  let body: string;
  if (short != null && long != null) {
    body = verb(short) === verb(long)
      ? `${verb(short)} other liquid names by ${by(short)} over 3 sessions and ${by(long)} over 20`
      : `${verb(short)} other liquid names by ${by(short)} over 3 sessions and `
        + `${verb(long)} them by ${by(long)} over 20`;
  } else if (short != null || long != null) {
    const x = (short ?? long)!;
    body = `${verb(x)} other liquid names by ${by(x)} over ${short != null ? 3 : 20} sessions`;
  } else {
    return `Too few readings yet to say what names that ${slice} without news have done since.`;
  }
  const tail = lead.neg != null ? `; below zero on ${Math.round(lead.neg)}% of nights` : "";
  return `Over the last 90 days, names that ${slice} without news have ${body}, `
       + `on ${lead.n} gaps across ${lead.nights} nights${tail}.`;
}

function Side({ title, rows, total, way, file }: {
  title: string; rows: GapFadeRow[]; total: number; way: "up" | "down"; file: GapFadeFile;
}) {
  const record = file.record?.[way];
  return (
    <section className="stack" style={{ marginTop: "var(--pad-lg)" }}>
      <h2>{title}</h2>
      <p className="caption dim">{recordSentence(way, record?.h3, record?.h20)}</p>
      {rows.length === 0 ? (
        <div className="card muted footnote">None tonight.</div>
      ) : (
        <div className="scroll-x card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr><th>Symbol</th><th>Company</th><th>Gap</th><th>Daily dollar volume</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.ticker}>
                  <td className="text mono">
                    {row.in_universe
                      ? <Link href={`/stocks/${encodeURIComponent(row.ticker)}`}>{row.ticker}</Link>
                      : row.ticker}
                  </td>
                  <td className="text">{row.name}</td>
                  <td><PriceChange value={row.gap} digits={1} badge /></td>
                  <td>{compactMoney(row.dollar_vol)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {total > rows.length && (
        <p className="caption dim">and {total - rows.length} smaller.</p>
      )}
    </section>
  );
}

export default function GapFadePage() {
  if (!hasData()) return <NoData />;
  const file = getGapFade();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · options and flows</div>
      <h1>Gap fade watch</h1>
      <p className="muted footnote">
        Liquid stocks that opened well away from the last close with no filing
        that day and no results in the four days before. A gap with nothing
        behind it has tended to give some of itself back. This is context, not
        a list of trades.
      </p>
      {!file ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          The Market Desk sent no fade watch on its last run. It sends one on
          nights when a liquid name gapped without news.
        </div>
      ) : (
        <>
          <p className="caption dim">
            From the Market Desk&apos;s run of {longDate(file.read_on)}
            {file.floor ? `, names trading ${compactMoney(file.floor)} a day or more` : ""}.
            {file.stale && " This is an older run: the desk has not sent a newer one."}
          </p>
          <Side title="Gapped up" rows={file.up} total={file.n_up} way="up" file={file} />
          <Side title="Gapped down" rows={file.down} total={file.n_down} way="down" file={file} />
          <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>
            The record compares each gap with other liquid names over the same
            sessions, one reading a night, and is the desk&apos;s, not this
            site&apos;s. A name in the list that this site does not follow is
            shown without a link.
          </p>
        </>
      )}
      <MarketCTA />
    </div>
  );
}
