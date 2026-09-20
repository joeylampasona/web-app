"use client";

import Link from "next/link";
import { useState } from "react";
import { signed } from "@/lib/format";
import type { GroupRow } from "@/lib/types";
import type { HeatRow } from "@/lib/data";
import { PriceChange } from "./PriceChange";

/** The 1-99 score, with a gauge under it.
 *
 * A column of bare numbers has to be read one at a time and compared in your
 * head. The bar makes the ranking visible down the column without moving the
 * number or changing its alignment, which is why it sits underneath rather
 * than behind: a fill behind digits either washes them out or has to be so
 * faint it says nothing.
 *
 * Semi-transparent so it reads as a gauge rather than a second data series,
 * and it never replaces the number — the figure stays exact.
 */
function ScoreGauge({ value }: { value: number | string | null | undefined }) {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : null;
  const share = numeric === null ? 0 : Math.min(Math.max(numeric, 0), 99) / 99;
  return (
    <span className="stack" style={{ gap: 3, minWidth: 34, alignItems: "flex-end" }}>
      <span className="num">{numeric ?? "—"}</span>
      {numeric !== null && (
        <span
          aria-hidden
          style={{
            width: 34, height: 3, borderRadius: "var(--radius-pill)",
            background: "var(--border-stronger)", overflow: "hidden",
            display: "block",
          }}
        >
          <span
            style={{
              display: "block", height: "100%", width: `${share * 100}%`,
              background: "var(--text-secondary)", opacity: 0.75,
              borderRadius: "var(--radius-pill)",
            }}
          />
        </span>
      )}
    </span>
  );
}

export function StrengthTable({
  strong, weak, kind,
}: {
  strong: GroupRow[];
  weak: GroupRow[];
  kind: "industries" | "themes";
}) {
  const [mode, setMode] = useState<"strong" | "weak">("strong");
  const rows = mode === "strong" ? strong : weak;
  return (
    <section className="stack">
      <div className="between">
        <h2>{mode === "strong" ? "Strongest" : "Weakest"} {kind}</h2>
        <div className="row" style={{ gap: 0 }}>
          <button type="button" className="control footnote" aria-pressed={mode === "strong"}
                  style={{ borderRadius: "var(--radius) 0 0 var(--radius)" }}
                  onClick={() => setMode("strong")}>Strong</button>
          <button type="button" className="control footnote" aria-pressed={mode === "weak"}
                  style={{ borderRadius: "0 var(--radius) var(--radius) 0", marginLeft: -1 }}
                  onClick={() => setMode("weak")}>Weak</button>
        </div>
      </div>
      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        {rows.map((row) => (
          <Link key={row.slug} href={`/${kind}/${row.slug}`} className="card between"
                style={{ padding: "var(--pad-md) var(--pad-lg)" }}>
            <span className="grow">
              <span>{row.name}</span>
              <span className="caption dim"> · {row.members} names</span>
            </span>
            <span className="row" style={{ gap: "var(--gap-sm)" }}>
              {row.fresh_breakouts > 0 && (
                <span className="badge badge--gain">
                  <span className="num">{row.fresh_breakouts}</span>&nbsp;fresh
                </span>
              )}
              <span className="badge">
                <span className="num">{row.leaders}</span>&nbsp;leaders
              </span>
              <ScoreGauge value={row.rs_rating} />
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function HeatTable({
  heating, cooling, kind,
}: {
  heating: HeatRow[];
  cooling: HeatRow[];
  kind: "industries" | "themes";
}) {
  const [mode, setMode] = useState<"heating" | "cooling">("heating");
  const rows = mode === "heating" ? heating : cooling;
  return (
    <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
      <div className="between">
        <h2>{mode === "heating" ? "Heating up" : "Cooling off"}</h2>
        <div className="row" style={{ gap: 0 }}>
          <button type="button" className="control footnote" aria-pressed={mode === "heating"}
                  style={{ borderRadius: "var(--radius) 0 0 var(--radius)" }}
                  onClick={() => setMode("heating")}>Heating</button>
          <button type="button" className="control footnote" aria-pressed={mode === "cooling"}
                  style={{ borderRadius: "0 var(--radius) var(--radius) 0", marginLeft: -1 }}
                  onClick={() => setMode("cooling")}>Cooling</button>
        </div>
      </div>
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr><th>Group</th><th>Average RS</th><th>Change, 1 month</th><th>Leaders</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.slug}>
                <td className="text">
                  <Link href={`/${kind}/${row.slug}`}>{row.name}</Link>
                </td>
                <td>{row.avg_member_rs.toFixed(1)}</td>
                <td><PriceChange value={row.delta} digits={1} unit=" pts" /></td>
                <td>{row.leaders}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
