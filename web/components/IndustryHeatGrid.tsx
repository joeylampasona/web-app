"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { signed } from "@/lib/format";

interface Row {
  slug: string; name: string; members: number; leaders: number;
  fresh_breakouts: number; rs_rating: number | null;
  rs_change_w1: number | null; rs_change_m1: number | null; rs_change_m3: number | null;
}

type SortKey = "rs_rating" | "rs_change_w1" | "rs_change_m1" | "rs_change_m3" | "name";

const COLUMNS: { key: Exclude<SortKey, "name" | "rs_rating">; label: string }[] = [
  { key: "rs_change_w1", label: "1wk" },
  { key: "rs_change_m1", label: "1mo" },
  { key: "rs_change_m3", label: "3mo" },
];

// A change of this many RS points or more gets the strongest shade. Most
// industries move less than this in a month, so the scale is not spent on the
// one outlier and the middle of the table still has colour in it.
const FULL_SHADE = 20;

function shade(delta: number | null): string | undefined {
  if (delta === null || delta === 0) return undefined;
  const strength = Math.min(Math.abs(delta) / FULL_SHADE, 1);
  const pct = Math.round(12 + strength * 38);
  const base = delta > 0 ? "var(--gain)" : "var(--loss)";
  return `color-mix(in srgb, ${base} ${pct}%, transparent)`;
}

/**
 * Every industry, every window, in one table.
 *
 * The map shows one window at a time and only the eighteen largest groups, so
 * the question it cannot answer is the one rotation is about: which groups
 * are improving on every horizon at once, and which are only bouncing. Here
 * each row carries all three, shaded by size, and the filter keeps only the
 * groups gaining on all of them.
 */
export function IndustryHeatGrid({ rows }: { rows: Row[] }) {
  const [sort, setSort] = useState<SortKey>("rs_change_m1");
  const [allUp, setAllUp] = useState(false);

  const shown = useMemo(() => {
    const kept = allUp
      ? rows.filter((r) => COLUMNS.every((c) => (r[c.key] ?? 0) > 0))
      : rows;
    return [...kept].sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      return (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity);
    });
  }, [allUp, rows, sort]);

  const header = (key: SortKey, label: string) => (
    <th key={key}>
      <button type="button" aria-pressed={sort === key}
              onClick={() => setSort(key)}
              style={{ all: "unset", cursor: "pointer",
                       color: sort === key ? "var(--text-primary)" : undefined,
                       fontWeight: sort === key ? 600 : undefined }}>
        {label}{sort === key && key !== "name" ? " ↓" : ""}
      </button>
    </th>
  );

  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="between wrap" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">Every industry, every window</div>
        <button type="button" className="control footnote" aria-pressed={allUp}
                onClick={() => setAllUp((v) => !v)}>
          {allUp ? "Showing: improving on all three" : "Only improving on all three"}
        </button>
      </div>
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              {header("name", "Industry")}
              {header("rs_rating", "RS")}
              {COLUMNS.map((c) => header(c.key, c.label))}
              <th>Leaders</th>
              <th>Fresh</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.slug}>
                <td className="text">
                  <Link href={`/industries/${r.slug}`} style={{ color: "var(--link)" }}>
                    {r.name}
                  </Link>{" "}
                  <span className="caption dim">{r.members}</span>
                </td>
                <td>{r.rs_rating ?? "—"}</td>
                {COLUMNS.map((c) => (
                  <td key={c.key} style={{ background: shade(r[c.key]) }}>
                    {r[c.key] === null ? "—" : signed(r[c.key] as number, 1, "")}
                  </td>
                ))}
                <td>{r.leaders}</td>
                <td>{r.fresh_breakouts || "—"}</td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td className="text dim" colSpan={7}>
                  No industry is improving on all three windows right now.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        Change in each industry&rsquo;s RS rating over the week, month and quarter.
        Shaded by size; {FULL_SHADE} points or more is the darkest. Leaders are
        members rated 80 or above; fresh counts today&rsquo;s breakouts.
      </p>
    </section>
  );
}
