import Link from "next/link";
import { Sparkline } from "./Sparkline";
import type { Alignment, Radar, RadarGroup, RadarReading } from "@/lib/types";

/**
 * The Market Strength Radar: price ratios, read over five windows.
 *
 * Every number is the percent change of one fund's price against another's
 * over that many sessions: growth against the market, small caps against
 * growth and the market, equal weight against cap weight, and every sector
 * and group fund against the S&P 500. "Aligned" is the ratio's own trend:
 * its 21-day average above its 63-day, the 42 above the 126, the 63 above the
 * 126. The label for the week is one of five fixed rules with the readings
 * that produced it. Measured, not forecast.
 */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function toneOf(v: number | null | undefined): string | undefined {
  if (v == null || v === 0) return undefined;
  return v > 0 ? "var(--gain)" : "var(--loss)";
}

const ALIGN_LABEL: Record<Alignment, string> = {
  full: "Fully aligned", partial: "Partly aligned", none: "Not aligned",
};

export function AlignChip({ state }: { state: Alignment | null | undefined }) {
  if (!state) return <span className="caption dim">—</span>;
  const cls = state === "full" ? "badge badge--gain" : state === "none" ? "badge badge--loss" : "badge";
  return (
    <span className={cls} title="The ratio's 21-day average above its 63-day, 42 above 126, 63 above 126: all three is fully aligned, one or two partly, none not aligned.">
      {ALIGN_LABEL[state]}
    </span>
  );
}

function day(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC",
  });
}

/** Rebased-to-100 ratio, stretched to the 0-100 box the sparkline draws. */
function shape(points: number[]): number[] {
  if (points.length < 2) return [];
  const lo = Math.min(...points), hi = Math.max(...points);
  if (hi === lo) return points.map(() => 50);
  return points.map((p) => ((p - lo) / (hi - lo)) * 100);
}

function Cell({ r, w }: { r: RadarReading; w: number }) {
  const v = r[`rs${w}` as keyof RadarReading] as number | null;
  return <td className="num" style={{ color: toneOf(v) }}>{pct(v)}</td>;
}

export function RadarRead({ radar, compact = false, front = null }: {
  radar: Radar; compact?: boolean;
  /** Stocks on the front line tonight, from the leadership layers. */
  front?: number | null;
}) {
  const read = radar.read;
  if (compact) {
    return (
      <p className="caption dim" style={{ margin: 0 }}>
        Strength radar: <Link href="/market/radar">{read.label}</Link>,{" "}
        {read.full_share}% of groups fully aligned against the S&amp;P 500
        {front != null && (
          <> · <Link href="/market/leadership">{front.toLocaleString("en-US")} stocks on the front line</Link></>
        )}.
      </p>
    );
  }
  return (
    <div className="grid-2">
      <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
        <div className="footnote muted">The week to {day(radar.to)}</div>
        <div className="num" style={{ fontSize: "var(--size-h2)" }}>{read.label}</div>
        <p className="caption dim" style={{ margin: 0 }}>{read.sub}</p>
        <ul className="caption" style={{ margin: 0, paddingLeft: "1.1em" }}>
          {read.reasons.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>
      <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
        <div className="footnote muted">What would change it</div>
        <ul className="caption" style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
          {radar.watch.map((w) => (
            <li key={w.q} className="between" style={{ gap: "var(--gap-sm)" }}>
              <span>
                <span aria-hidden style={{ color: w.met ? "var(--gain)" : undefined }}>
                  {w.met ? "✓" : "□"}
                </span>{" "}
                {w.q}
                <span className="visually-hidden">{w.met ? " (met)" : " (not met)"}</span>
              </span>
              <span className="num dim">{w.now}</span>
            </li>
          ))}
        </ul>
        <p className="caption dim" style={{ margin: 0 }}>
          Thresholds beside their current readings. The label comes from fixed
          rules, not a forecast: broad advance, narrow growth leadership,
          selective rotation, deterioration or mixed.
        </p>
      </div>
    </div>
  );
}

export function RadarPairs({ radar }: { radar: Radar }) {
  return (
    <div className="scroll-x card" style={{ padding: 0 }}>
      <table className="data">
        <thead>
          <tr>
            <th className="text">Relationship</th><th>Three months</th>
            <th>1m</th><th>2m</th><th>3m</th><th>6m</th><th>12m</th>
            <th>6m a week ago</th><th className="text">Trend</th>
          </tr>
        </thead>
        <tbody>
          {radar.pairs.map((p) => (
            <tr key={`${p.a}/${p.b}`}>
              <td className="text">
                {p.label}
                <div className="caption dim mono">{p.a} / {p.b}</div>
              </td>
              <td><Sparkline points={shape(p.spark)} changePct={p.now.rs63} width={88}
                             label={`${p.a} against ${p.b} over three months`} /></td>
              {radar.windows.map((w) => <Cell key={w} r={p.now} w={w} />)}
              <td className="num dim">{pct(p.start?.rs126)}</td>
              <td className="text"><AlignChip state={p.aligned} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RadarBreadth({ radar }: { radar: Radar }) {
  if (!radar.breadth.length) return null;
  return (
    <div className="scroll-x card" style={{ padding: 0 }}>
      <table className="data">
        <thead>
          <tr>
            <th className="text">Session</th><th>Fully aligned</th><th>Partly</th>
            <th>Not</th><th>Ahead 1m</th><th>Ahead 3m</th><th>Ahead 6m</th>
          </tr>
        </thead>
        <tbody>
          {radar.breadth.map((b) => (
            <tr key={b.date}>
              <td className="text">{day(b.date)}</td>
              <td className="num">{b.full}</td>
              <td className="num">{b.partial}</td>
              <td className="num">{b.none}</td>
              <td className="num">{b.pos21}</td>
              <td className="num">{b.pos63}</td>
              <td className="num">{b.pos126}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const MAP: { key: keyof Radar["map"]; title: string; note: string }[] = [
  { key: "leaders", title: "Leading", note: "Fully aligned, ahead over six months and the last month, not slipping on the week." },
  { key: "cooling", title: "Strong but cooling", note: "Ahead over six months, but behind over the last month or losing ground on the week." },
  { key: "improving", title: "Improving most", note: "The biggest gains in six-month strength this week." },
  { key: "weakest", title: "Weakest", note: "Furthest behind the S&P 500 over six months." },
  { key: "fell", title: "Lost most", note: "The biggest losses in six-month strength this week." },
];

export function RadarMap({ radar }: { radar: Radar }) {
  const by = new Map(radar.groups.map((g) => [g.symbol, g]));
  return (
    <div className="grid-auto">
      {MAP.map(({ key, title, note }) => {
        const rows = radar.map[key].map((s) => by.get(s)).filter(Boolean) as RadarGroup[];
        return (
          <div key={key} className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">{title}</div>
            {rows.length ? rows.map((g) => (
              <div key={g.symbol} className="between caption">
                <span>{g.label} <span className="dim mono">{g.symbol}</span></span>
                <span className="num" style={{ color: toneOf(g.now.rs126) }}>
                  {pct(g.now.rs126)}
                  {g.chg126 != null && (
                    <span className="dim"> ({g.chg126 > 0 ? "+" : ""}{g.chg126.toFixed(1)})</span>
                  )}
                </span>
              </div>
            )) : <div className="caption dim">None this week</div>}
            <p className="caption dim" style={{ margin: 0 }}>{note}</p>
          </div>
        );
      })}
    </div>
  );
}

export function RadarGroups({ radar }: { radar: Radar }) {
  return (
    <div className="scroll-x scroll-tall card" style={{ padding: 0 }}>
      <table className="data">
        <thead>
          <tr>
            <th className="text">Group</th><th>1m</th><th>2m</th><th>3m</th><th>6m</th>
            <th>12m</th><th>6m on the week</th><th className="text">Trend</th>
          </tr>
        </thead>
        <tbody>
          {radar.groups.map((g) => (
            <tr key={g.symbol}>
              <td className="text">
                {g.label} <span className="caption dim mono">{g.symbol}</span>
                {g.kind === "sector" && <span className="caption dim"> · sector</span>}
              </td>
              {radar.windows.map((w) => <Cell key={w} r={g.now} w={w} />)}
              <td className="num" style={{ color: toneOf(g.chg126) }}>
                {g.chg126 == null ? "—" : `${g.chg126 > 0 ? "+" : ""}${g.chg126.toFixed(1)}`}
              </td>
              <td className="text">
                <AlignChip state={g.aligned} />
                {g.aligned_start && g.aligned !== g.aligned_start && (
                  <span className="caption dim"> was {ALIGN_LABEL[g.aligned_start].toLowerCase()}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
