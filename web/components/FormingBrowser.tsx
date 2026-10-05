"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Locked } from "@/components/Locked";
import { SetupChart } from "@/components/SetupChart";
import { compactMoney, isRanked, price, rsText } from "@/lib/format";
import { useLazyBars } from "@/lib/useBars";
import { useGated } from "@/lib/useGated";
import { useQuotesMap, useQuotesMeta } from "@/lib/useQuotes";
import type { FormingFile, FormingRow, FormingSummary } from "@/lib/types";

/**
 * Every base forming on any screen, in one list.
 *
 * One row per stock, with every screen it is forming on: agreement between
 * screens is information, and listing the stock once per screen would hide it
 * as repetition. The row's figures are its nearest reading.
 *
 * Breakouts and breakdowns are separate lists. A rising wedge "forming" is a
 * stock setting up to fall; in a list of breakout candidates it would read as
 * the opposite of what it is.
 *
 * The distance to the pivot uses the intraday price when the sweep has one,
 * and says so, so the list reorders as names close in on their lines.
 */
type SortKey = "near" | "screens" | "rs" | "cap" | "base" | "symbol";
const SORTS: { key: SortKey; label: string }[] = [
  { key: "near", label: "Closest to pivot" },
  { key: "screens", label: "Most screens" },
  { key: "rs", label: "RS rating" },
  { key: "cap", label: "Market cap" },
  { key: "base", label: "Base length" },
  { key: "symbol", label: "Ticker" },
];
const WITHIN = [0, 2, 5, 10];
const MIN_RS = [0, 70, 80, 90];
const EARNINGS_WARN_DAYS = 14;
const CHARTS_UP_FRONT = 20;

type Live = FormingRow & { gap: number | null; live: boolean };

function pct(v: number | null): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`;
}

function EarningsFlag({ row }: { row: FormingRow }) {
  const d = row.days_until_earnings;
  if (d == null || d < 0 || d > EARNINGS_WARN_DAYS) return null;
  return (
    <span className="badge badge--warn" title={`Reports ${row.next_earnings_date}`}>
      Earnings {d === 0 ? "today" : `in ${d}d`}
    </span>
  );
}

function RowChart({ row }: { row: FormingRow }) {
  const lazy = useLazyBars(row.symbol, true);
  return (
    <div ref={lazy.ref} style={{ minHeight: 180 }}>
      {lazy.bars ? (
        <SetupChart bars={lazy.bars} pivot={row.pivot} contractions={[]}
                    breakoutDate={null} flags={[]} symbol={`forming-${row.symbol}`}
                    height={180} />
      ) : (
        <p className="caption dim" style={{ margin: 0 }}>Loading the chart…</p>
      )}
    </div>
  );
}

function Counts({ summary, direction }: { summary: FormingSummary; direction: string }) {
  const rows = Object.entries(summary.screens)
    .filter(([, s]) => s.direction === direction && s.count > 0)
    .sort((a, b) => b[1].count - a[1].count);
  return (
    <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
      {rows.map(([key, s]) => (
        <Link key={key} href={`/screens/${key}`} className="badge">
          {s.name} · {s.count}
        </Link>
      ))}
    </div>
  );
}

export function FormingList({ file }: { file: FormingFile }) {
  const quotes = useQuotesMap();
  const meta = useQuotesMeta();
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [sort, setSort] = useState<SortKey>("near");
  const [query, setQuery] = useState("");
  const [within, setWithin] = useState(0);
  const [minRs, setMinRs] = useState(0);
  const [screens, setScreens] = useState<string[]>([]);
  const [industry, setIndustry] = useState("");
  const [view, setView] = useState<"table" | "charts">("table");
  const [open, setOpen] = useState<string | null>(null);

  const inDirection = useMemo(
    () => file.rows.filter((r) => r.direction === direction), [file.rows, direction]);

  const industries = useMemo(() => {
    const n = new Map<string, number>();
    for (const r of inDirection) if (r.industry) n.set(r.industry, (n.get(r.industry) ?? 0) + 1);
    return [...n.entries()].sort((a, b) => b[1] - a[1]);
  }, [inDirection]);

  const screenKeys = useMemo(() => Object.entries(file.screens)
    .filter(([, s]) => s.direction === direction && s.count > 0)
    .sort((a, b) => b[1].count - a[1].count), [file.screens, direction]);

  const rows: Live[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    const live = inDirection.map((r) => {
      const quote = quotes[r.symbol];
      return quote && r.pivot
        ? { ...r, gap: 100 * (quote.last / r.pivot - 1), live: true }
        : { ...r, gap: r.now_vs_pivot_pct, live: false };
    });
    const kept = live.filter((r) =>
      (!q || r.symbol.toLowerCase().includes(q) || (r.name ?? "").toLowerCase().includes(q)
        || (r.industry ?? "").toLowerCase().includes(q))
      && (!within || (r.gap != null && Math.abs(r.gap) <= within))
      && (!minRs || (isRanked(r.rs_rating) && r.rs_rating >= minRs))
      && (screens.length === 0 || r.screens.some((s) => screens.includes(s.screen)))
      && (!industry || r.industry === industry));
    const key = (r: Live): number | string => {
      switch (sort) {
        case "near": return r.gap == null ? Infinity : Math.abs(r.gap);
        case "screens": return -r.screens.length;
        case "rs": return isRanked(r.rs_rating) ? -r.rs_rating : Infinity;
        case "cap": return r.market_cap ? -r.market_cap : Infinity;
        case "base": return r.base_weeks == null ? Infinity : -r.base_weeks;
        default: return r.symbol;
      }
    };
    return kept.sort((a, b) => {
      const x = key(a), y = key(b);
      if (typeof x === "string") return x.localeCompare(String(y));
      return (x as number) - (y as number)
        || (a.gap == null ? 1 : Math.abs(a.gap)) - (b.gap == null ? 1 : Math.abs(b.gap));
    });
  }, [inDirection, quotes, query, within, minRs, screens, industry, sort]);

  const liveCount = rows.filter((r) => r.live).length;

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="row wrap" style={{ gap: 0 }}>
        {(["long", "short"] as const).map((d, i) => (
          <button key={d} type="button" className="control" aria-pressed={direction === d}
                  onClick={() => { setDirection(d); setScreens([]); setIndustry(""); }}
                  style={{ borderRadius: i === 0 ? "var(--radius) 0 0 var(--radius)"
                                                  : "0 var(--radius) var(--radius) 0",
                           marginLeft: i === 0 ? 0 : -1 }}>
            {d === "long" ? `Breakouts setting up · ${file.stocks.long}`
                          : `Breakdowns setting up · ${file.stocks.short}`}
          </button>
        ))}
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        <input type="search" className="control" placeholder="Search ticker, company, industry"
               value={query} onChange={(e) => setQuery(e.target.value)}
               aria-label="Search the forming list"
               style={{ flex: "1 1 180px", maxWidth: 280, background: "var(--surface-2)" }} />
        <select className="control" value={sort} aria-label="Sort by"
                onChange={(e) => setSort(e.target.value as SortKey)}
                style={{ background: "var(--surface-2)" }}>
          {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <select className="control" value={within} aria-label="How close to the pivot"
                onChange={(e) => setWithin(Number(e.target.value))}
                style={{ background: "var(--surface-2)" }}>
          {WITHIN.map((w) => <option key={w} value={w}>{w ? `Within ${w}% of pivot` : "Any distance"}</option>)}
        </select>
        <select className="control" value={minRs} aria-label="Minimum RS rating"
                onChange={(e) => setMinRs(Number(e.target.value))}
                style={{ background: "var(--surface-2)" }}>
          {MIN_RS.map((v) => <option key={v} value={v}>{v ? `RS ${v}+` : "Any RS"}</option>)}
        </select>
        <select className="control" value={industry} aria-label="Industry"
                onChange={(e) => setIndustry(e.target.value)}
                style={{ background: "var(--surface-2)", maxWidth: 240 }}>
          <option value="">Every industry</option>
          {industries.map(([name, n]) => <option key={name} value={name}>{name} · {n}</option>)}
        </select>
        <div className="row" style={{ gap: 0 }}>
          {(["table", "charts"] as const).map((v, i) => (
            <button key={v} type="button" className="control" aria-pressed={view === v}
                    onClick={() => setView(v)}
                    style={{ borderRadius: i === 0 ? "var(--radius) 0 0 var(--radius)"
                                                    : "0 var(--radius) var(--radius) 0",
                             marginLeft: i === 0 ? 0 : -1 }}>
              {v === "table" ? "Table" : "Charts"}
            </button>
          ))}
        </div>
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
        {screenKeys.map(([key, s]) => {
          const on = screens.includes(key);
          return (
            <button key={key} type="button" className="badge" aria-pressed={on}
                    onClick={() => setScreens(on ? screens.filter((k) => k !== key) : [...screens, key])}
                    style={{ cursor: "pointer", outline: on ? "1px solid var(--brand-ink)" : undefined }}>
              {s.name} · {s.count}
            </button>
          );
        })}
        {screens.length > 0 && (
          <button type="button" className="caption dim" onClick={() => setScreens([])}
                  style={{ background: "none", border: 0, cursor: "pointer" }}>
            clear
          </button>
        )}
      </div>

      <p className="caption dim" style={{ margin: 0 }}>
        {rows.length.toLocaleString("en-US")} of {inDirection.length.toLocaleString("en-US")} stocks.
        {liveCount > 0
          ? ` Distance to pivot uses intraday prices for ${liveCount} of them (delayed, read at ${
              meta.fetchedAt ? new Date(meta.fetchedAt).toLocaleTimeString("en-US",
                { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }) + " ET" : "the last sweep"
            }); the rest use the last close.`
          : " Distance to pivot is from the last close."}
      </p>

      {rows.length === 0 ? (
        <div className="card muted footnote">Nothing forming matches these filters.</div>
      ) : view === "charts" ? (
        <div className="grid-auto">
          {rows.slice(0, CHARTS_UP_FRONT).map((r) => (
            <div key={`${r.symbol}-${r.direction}`} className="card stack" style={{ gap: "var(--gap-xs)" }}>
              <div className="between">
                <Link href={`/stocks/${r.symbol}`} className="mono" style={{ color: "var(--link)" }}>
                  {r.symbol}
                </Link>
                <span className="caption">{pct(r.gap)}{r.live ? " · live" : ""}</span>
              </div>
              <div className="caption dim">{r.screens.map((s) => s.name).join(" · ")}</div>
              <RowChart row={r} />
            </div>
          ))}
          {rows.length > CHARTS_UP_FRONT && (
            <p className="caption dim">
              The first {CHARTS_UP_FRONT} as charts. The rest are in the table view.
            </p>
          )}
        </div>
      ) : (
        <div className="scroll-x card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Ticker</th><th>Screens</th><th>vs pivot</th><th>Pivot</th>
                <th>RS</th><th>Mkt cap</th><th>Base</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const id = `${r.symbol}-${r.direction}`;
                const expanded = open === id;
                return [
                  <tr key={id} onClick={() => setOpen(expanded ? null : id)}
                      style={{ cursor: "pointer" }} aria-expanded={expanded}>
                    <td className="text">
                      <Link href={`/stocks/${r.symbol}`} onClick={(e) => e.stopPropagation()}>
                        <span className="mono" style={{ color: "var(--link)" }}>{r.symbol}</span>{" "}
                        <span className="dim caption">{r.name}</span>
                      </Link>
                    </td>
                    <td className="text caption">
                      {r.screens.map((s) => s.name).join(" · ")}
                      {r.screens.length > 1 && <span className="dim"> ({r.screens.length})</span>}
                    </td>
                    <td>
                      {pct(r.gap)}
                      {r.live && <span className="caption dim"> live</span>}
                    </td>
                    <td>{price(r.pivot)}</td>
                    <td>{rsText(r.rs_rating)}</td>
                    <td>{r.market_cap ? compactMoney(r.market_cap) : "—"}</td>
                    <td>{r.base_weeks != null ? `${r.base_weeks.toFixed(1)}w` : "—"}</td>
                    <td className="text"><EarningsFlag row={r} /></td>
                  </tr>,
                  expanded ? (
                    <tr key={`${id}-chart`}>
                      <td colSpan={8} className="text"><RowChart row={r} /></td>
                    </tr>
                  ) : null,
                ];
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        Tap a row for its chart. Earnings flagged when the report is within {EARNINGS_WARN_DAYS} days:
        a base that breaks out into a report can gap either way before the move is confirmed.
      </p>
    </div>
  );
}

export function FormingAll({ summary }: { summary: FormingSummary }) {
  const full = useGated<FormingFile>(summary.gated ? "forming/all.json" : null);

  if (full.state === "ready" && full.data?.rows) return <FormingList file={full.data} />;

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <p className="footnote" style={{ margin: 0 }}>
        <strong>{summary.stocks.long.toLocaleString("en-US")}</strong> stocks are forming a base
        to break out of, and {summary.stocks.short.toLocaleString("en-US")} a pattern to break down from.
      </p>
      <Counts summary={summary} direction="long" />
      {full.state === "loading" ? (
        <p className="caption dim" style={{ margin: 0 }}>Checking your subscription…</p>
      ) : (
        <Locked what="Every forming base in one list — sortable, searchable, with live distance to the pivot —">
          {full.state === "error" && (
            <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
              The subscription check did not answer ({full.detail}).
            </p>
          )}
        </Locked>
      )}
    </div>
  );
}
