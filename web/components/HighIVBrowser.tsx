"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { copy } from "@/lib/copy";
import { longDate, shortDate } from "@/lib/format";
import type { IVRow } from "@/lib/types";
import { Tooltip } from "./Tooltip";

/** Rows shown per week before the reader asks for the rest. */
const PREVIEW = 10;

function Dots({ filled, total }: { filled: number; total: number }) {
  return (
    <span aria-label={`${filled} of ${total}`} className="num">
      {"●".repeat(filled)}
      <span className="dim">{"○".repeat(Math.max(0, total - filled))}</span>
    </span>
  );
}

/**
 * The High IV table, by week.
 *
 * The weeks used to arrive in the order the highest-IV row for each happened to
 * appear — compute() sorts by richness, the page grouped into a Map, and a Map
 * keeps insertion order. Thirteen weeks came out starting at October 19th,
 * then November 9th, then September 21st. Sorting the keys is the whole fix;
 * the rows inside a week stay ranked by richness, which is what the page is for.
 *
 * The rest is length. Every week rendered every row, so a page covering a
 * quarter ran to hundreds of rows with no way to reach the one you wanted.
 * Now: a week picker, and ten rows a week until you ask for more.
 */
export function HighIVBrowser({
  rows, dots, bandLabels,
}: {
  rows: IVRow[];
  dots: number;
  bandLabels: Record<string, string>;
}) {
  const [week, setWeek] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const weeks = useMemo(() => {
    const grouped = new Map<string, IVRow[]>();
    for (const row of rows) {
      const list = grouped.get(row.week_of) ?? [];
      list.push(row);
      grouped.set(row.week_of, list);
    }
    // Chronological. This is the bug the page shipped with.
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [rows]);

  const shown = week ? weeks.filter(([key]) => key === week) : weeks;

  return (
    <>
      <div
        className="scroll-x"
        style={{ marginTop: "var(--gap-md)", marginBottom: "var(--gap-sm)" }}
      >
        <div className="row" style={{ gap: "var(--gap-xs)", paddingBottom: 4 }}>
          <button
            type="button"
            className="control caption"
            aria-pressed={week === null}
            onClick={() => setWeek(null)}
            style={{ whiteSpace: "nowrap" }}
          >
            All weeks
          </button>
          {weeks.map(([key, list]) => (
            <button
              key={key}
              type="button"
              className="control caption"
              aria-pressed={week === key}
              onClick={() => setWeek(week === key ? null : key)}
              style={{ whiteSpace: "nowrap" }}
            >
              {shortDate(key)}{" "}
              <span className="dim num">{list.length}</span>
            </button>
          ))}
        </div>
      </div>

      {shown.map(([key, list]) => {
        // A week you picked deliberately is a week you want to see all of.
        const open = week === key || expanded[key];
        const visible = open ? list : list.slice(0, PREVIEW);
        const hidden = list.length - visible.length;
        return (
          <section key={key} className="stack" style={{ marginTop: "var(--pad-lg)" }}>
            <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
              <div className="eyebrow" style={{ margin: 0 }}>Week of {longDate(key)}</div>
              <span className="caption dim num">{list.length}</span>
            </div>
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
                  {visible.map((row) => (
                    <tr key={`${row.ticker}-${row.event_date}`}>
                      <td className="text">
                        <Link href={`/stocks/${row.ticker}`} className="mono">{row.ticker}</Link>
                      </td>
                      <td className="text caption">
                        {row.event_label}
                        <span className="dim"> · {row.confirmed}</span>
                      </td>
                      {/* The table already scrolls sideways; letting the date
                          wrap instead turned every row three lines tall, which
                          is most of why this page read as endless. */}
                      <td className="caption" style={{ whiteSpace: "nowrap" }}>
                        {longDate(row.event_date)}
                      </td>
                      <td>{row.iv_richness.toFixed(2)}&#215;</td>
                      <td className="text">
                        <span className="row" style={{ gap: "var(--gap-sm)" }}>
                          <Dots filled={row.dots} total={dots} />
                          <span className="caption dim">{bandLabels[row.iv_band]}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {hidden > 0 && (
              <button
                type="button"
                className="control footnote"
                onClick={() => setExpanded((prev) => ({ ...prev, [key]: true }))}
                style={{ alignSelf: "flex-start" }}
              >
                Show {hidden} more
              </button>
            )}
            {open && !week && list.length > PREVIEW && (
              <button
                type="button"
                className="control footnote"
                onClick={() => setExpanded((prev) => ({ ...prev, [key]: false }))}
                style={{ alignSelf: "flex-start" }}
              >
                Show fewer
              </button>
            )}
          </section>
        );
      })}
    </>
  );
}
