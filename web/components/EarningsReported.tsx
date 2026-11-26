"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PriceChange } from "@/components/PriceChange";
import {
  clock, dayWord, headlineMoney,
  type ReportedRow, type ReportersPayload, type SettledRow,
} from "@/lib/reporters";

/**
 * Who reported, how the price took it, and how that held up.
 *
 * The nightly cannot carry this: a company reports at seven in the morning or
 * five past four and the page was built at two. So this section is read in
 * the browser from the reporters job's note, which is rewritten before the
 * open and after the close, and it is current between editions.
 *
 * Two tables. The first is the reaction as it was read: a delayed quote
 * outside the regular session, the reported figure against its estimate, and
 * the move the options had priced beside it, because six per cent is a shrug
 * against twelve and a shock against three. The second is the same reaction
 * after a full session, close to close, which is the one that counts.
 *
 * Nothing renders until the note arrives, and nothing at all when it is
 * empty, so a quiet day leaves no heading over an empty box.
 */
const SETTLED_SHOWN = 12;

function Ticker({ symbol, name, hasPage }: { symbol: string; name: string | null; hasPage: boolean }) {
  return (
    <>
      {hasPage
        ? <Link href={`/stocks/${symbol}`} className="mono" style={{ fontWeight: 600 }}>{symbol}</Link>
        : <span className="mono" style={{ fontWeight: 600 }}
                title="Outside the universe this site follows, so it has no page here.">{symbol}</span>}
      {name && <>{" "}<span className="dim caption">{name}</span></>}
    </>
  );
}

function surprise(value: number | null) {
  if (value == null) return null;
  return <>{" "}<PriceChange value={value} digits={1} /></>;
}

function Eps({ row }: { row: ReportedRow }) {
  if (row.eps == null) {
    return <span className="dim">{row.estimate != null
      ? `not in yet · ${row.estimate.toFixed(2)} expected` : "not in yet"}</span>;
  }
  return (
    <>
      <span style={{ fontWeight: 600 }}>{row.eps.toFixed(2)}</span>
      {row.estimate != null && <span className="dim"> vs {row.estimate.toFixed(2)}</span>}
      {surprise(row.surprise_pct)}
    </>
  );
}

function Revenue({ row }: { row: ReportedRow }) {
  if (row.revenue == null) return <span className="dim">—</span>;
  return (
    <>
      <span style={{ fontWeight: 600 }}>{headlineMoney(row.revenue)}</span>
      {row.revenue_estimate != null && (
        <span className="dim"> vs {headlineMoney(row.revenue_estimate)}</span>
      )}
      {row.revenue_estimate != null && surprise(row.revenue_surprise_pct)}
    </>
  );
}

function Priced({ implied }: { implied: number | null }) {
  return implied == null
    ? <span className="dim">—</span>
    : <span className="num">±{implied.toFixed(1)}%</span>;
}

function Reported({ data }: { data: ReportersPayload }) {
  const word = dayWord(data.date, data.today);
  const reads = [...new Set(data.rows.map((r) => clock(r.read_at)).filter(Boolean))];
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <h3 style={{ margin: 0 }}>
        Reported {word}
        <span className="caption dim" style={{ fontWeight: 400 }}>
          {" "}· {data.rows.length} named{reads.length > 0 && `, prices read ${reads.join(" and ")} ET`}
        </span>
      </h3>
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>Ticker</th><th>Move</th><th className="text">When</th>
              <th>Options priced</th><th>EPS vs expected</th><th>Revenue vs expected</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={`${row.symbol}-${row.run}`}>
                <td className="text"><Ticker symbol={row.symbol} name={row.name} hasPage={row.has_page} /></td>
                <td>{row.move == null ? <span className="dim">no quote</span>
                  : <PriceChange value={row.move} digits={1} />}</td>
                <td className="text dim">{row.when ?? "—"}</td>
                <td><Priced implied={row.implied} /></td>
                <td className="num" style={{ whiteSpace: "nowrap" }}><Eps row={row} /></td>
                <td className="num" style={{ whiteSpace: "nowrap" }}><Revenue row={row} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
        Prices are delayed by fifteen to twenty minutes and were read once, at the
        time shown: before the bell and after it they are quotes in thin trading,
        not the session&rsquo;s move. Figures against estimates are as first
        published and can be revised. The companies named are the largest and
        most followed of the day&rsquo;s reporters, not all of them.
      </p>
    </div>
  );
}

function Settled({ rows }: { rows: SettledRow[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, SETTLED_SHOWN);
  const judged = rows.filter((r) => r.inside !== null);
  const held = judged.filter((r) => r.inside).length;
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <h3 style={{ margin: 0 }}>
        How they settled
        {judged.length > 0 && (
          <span className="caption dim" style={{ fontWeight: 400 }}>
            {" "}· the priced move held on {held} of {judged.length}
          </span>
        )}
      </h3>
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>Ticker</th><th className="text">Reported</th><th>Session, close to close</th>
              <th>First quote</th><th>Options priced</th><th className="text">Against it</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={`${row.symbol}-${row.reported}`}>
                <td className="text"><Ticker symbol={row.symbol} name={row.name} hasPage={row.has_page} /></td>
                <td className="text dim" style={{ whiteSpace: "nowrap" }}>
                  {row.reported ? new Date(`${row.reported}T12:00:00Z`).toLocaleDateString("en-US",
                    { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" }) : "—"}
                  {row.when && <> · {row.when}</>}
                </td>
                <td style={{ fontWeight: 600 }}><PriceChange value={row.session_move} digits={1} /></td>
                <td>{row.first_move == null ? <span className="dim">—</span>
                  : <PriceChange value={row.first_move} digits={1} className="dim" />}</td>
                <td><Priced implied={row.implied} /></td>
                <td className="text">
                  {row.inside === null ? <span className="dim">no priced move</span>
                    : row.inside ? <span className="dim">inside</span>
                    : <span style={{ fontWeight: 600 }}>outside</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > SETTLED_SHOWN && (
        <div>
          <button type="button" className="control" onClick={() => setAll((v) => !v)}>
            {all ? "Show fewer" : `Show all ${rows.length}`}
          </button>
        </div>
      )}
      <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
        A report before the bell settles in that day&rsquo;s session, one after it in
        the next day&rsquo;s. The first quote is the figure the reaction line gave
        at the time. Inside means the session&rsquo;s move was no larger than the
        options had priced, either way.
      </p>
    </div>
  );
}

export function EarningsReported() {
  const [data, setData] = useState<ReportersPayload | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/reporters")
      .then((response) => (response.ok ? response.json() : null))
      .then((body: ReportersPayload | null) => {
        if (alive && body && Array.isArray(body.rows) && Array.isArray(body.settled)) setData(body);
      })
      .catch(() => { /* The page is whole without this section. */ });
    return () => { alive = false; };
  }, []);

  if (!data || (data.rows.length === 0 && data.settled.length === 0)) return null;

  return (
    <section className="stack" style={{ marginTop: "var(--pad-lg)" }}>
      <div className="section-head">
        <h2>Reported</h2>
        <p className="footnote muted" style={{ margin: 0 }}>
          Who has reported, how the price took it when the figures landed, and
          how that held up over a full session. Read twice a day, before the
          open and after the close, so it is newer than the rest of this page.
          The move is set beside what the options had priced: six per cent is
          a shrug against twelve and a shock against three.
        </p>
      </div>
      {data.rows.length > 0 && <Reported data={data} />}
      {data.settled.length > 0 && <Settled rows={data.settled} />}
    </section>
  );
}
