"use client";

import Link from "next/link";
import { useState } from "react";
import type { OptionsVolume } from "@/lib/types";
import { CarriedOver, shortDay } from "./CarriedOver";
import { THIN_BOOK, UNUSUAL_RULE, contract, share } from "./OptionsVolume";

const PREVIEW = 20;

const CARRIED = "This chain was read on an earlier night. The source did not "
  + "answer for it on this run.";

/**
 * Where the day's option trading was large against what was already open.
 *
 * Ranked by volume as a share of open interest, not by volume. By volume the
 * page would be the same six companies every night, the ones whose options
 * always trade the most, and would say nothing about today. The share is
 * what moves when a name's options are busier than its book.
 *
 * A floor on contracts traded keeps a thin book off the top: two hundred
 * contracts against an open interest of three hundred is a large share of
 * nothing. The floor is stated on the page.
 */
export function OptionsVolumeBoard({
  rows, total, read,
}: {
  rows: OptionsVolume[];
  /** Every name that traded enough to be ranked. */
  total: number;
  /** Every name whose chain was read. */
  read?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, PREVIEW);
  const hidden = rows.length - visible.length;
  const top = Math.max(...rows.map((r) => r.volume_oi ?? 0), 0.01);
  const thin = rows.filter((r) => r.oi_source !== "occ").length;
  const carried = rows.filter((r) => r.stale).length;

  return (
    <>
      <p className="caption dim" style={{ marginTop: "var(--gap-md)" }}>
        {read != null && read > 0 && `${read.toLocaleString()} chains read · `}
        {total.toLocaleString()} traded enough to rank
        {total > rows.length && ` · showing the top ${rows.length}`}
      </p>

      {thin > 0 && (
        <p className="footnote book-note" style={{ margin: "var(--gap-sm) 0 0" }}>
          <CarriedOver>Partial book</CarriedOver>{" "}
          {thin === rows.length ? "Every row here was" : `${thin} of these rows were`}{" "}
          measured against one source&rsquo;s own open interest, because the
          clearing house&rsquo;s figures were unavailable. That book is
          shorter, so the share on those rows is overstated.
        </p>
      )}
      {carried > 0 && (
        <p className="caption dim" style={{ margin: "var(--gap-xs) 0 0" }}>
          <CarriedOver /> marks a chain read on an earlier night and kept,
          because the source did not answer for that name on this run.
        </p>
      )}

      <div className="scroll-x scroll-tall card" style={{ padding: 0, marginTop: "var(--gap-sm)" }}>
        <table className="data">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Traded</th>
              <th>Of open interest</th>
              <th>Puts per call</th>
              <th>Busiest contract</th>
              <th>Unusual</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const busiest = row.top[0];
              return (
                <tr key={row.symbol}>
                  <td className="text" style={{ whiteSpace: "nowrap" }}>
                    <Link href={`/stocks/${row.symbol}`} className="mono">{row.symbol}</Link>
                    {row.oi_source !== "occ" && (
                      <>{" "}<CarriedOver title={THIN_BOOK}>Partial book</CarriedOver></>
                    )}
                    {row.stale && (
                      <>{" "}<CarriedOver title={CARRIED}>
                        {shortDay(row.as_of) ? `Read ${shortDay(row.as_of)}` : "Carried over"}
                      </CarriedOver></>
                    )}
                  </td>
                  <td className="num">{row.volume.toLocaleString()}</td>
                  <td>
                    <span className="row" style={{ gap: "var(--gap-xs)", alignItems: "center",
                                                   justifyContent: "flex-end" }}>
                      <span
                        aria-hidden
                        style={{
                          width: 34, height: 4, borderRadius: "var(--radius-pill)",
                          background: "var(--border-stronger)", overflow: "hidden",
                          flexShrink: 0, display: "block",
                        }}
                      >
                        <span style={{
                          display: "block", height: "100%",
                          width: `${Math.max(((row.volume_oi ?? 0) / top) * 100, 2)}%`,
                          background: "var(--screen-highs)", opacity: 0.85,
                        }} />
                      </span>
                      <span className="num">{share(row.volume_oi)}</span>
                    </span>
                  </td>
                  <td className="num">{row.put_call == null ? "—" : row.put_call.toFixed(2)}</td>
                  <td className="text caption" style={{ whiteSpace: "nowrap" }}>
                    {busiest ? (
                      <>
                        {contract(busiest)}{" "}
                        <span className="num dim">
                          {busiest.volume.toLocaleString()}
                          {busiest.multiple != null && ` · ${busiest.multiple.toFixed(1)}×`}
                        </span>
                      </>
                    ) : "—"}
                  </td>
                  <td className="num caption" title={UNUSUAL_RULE}>
                    {row.unusual > 0 ? row.unusual : <span className="dim">0</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hidden > 0 && (
        <button
          type="button"
          className="control footnote"
          onClick={() => setExpanded(true)}
          style={{ marginTop: "var(--gap-sm)" }}
        >
          Show {hidden} more
        </button>
      )}
    </>
  );
}
