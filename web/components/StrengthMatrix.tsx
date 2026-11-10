import Link from "next/link";
import type { Radar, RadarGroup } from "@/lib/types";

/**
 * The strength matrix: every group against the S&P 500, as a grid.
 *
 * A row per group, a column per window, strongest at six months first. Each
 * cell prints its number and is tinted by it, green ahead and orange behind,
 * so rotation shows as a pattern: a group green on the right and orange on
 * the left is a leader losing ground, the reverse is one turning up. The
 * number is always printed; the tint is a second channel, never the only one.
 */
const WINDOWS: [keyof RadarGroup["now"], string][] = [
  ["rs21", "1M"], ["rs42", "2M"], ["rs63", "3M"], ["rs126", "6M"], ["rs252", "12M"],
];
/** The tint reaches full strength at this many percent. */
const FULL_AT = 30;
const TREND = { full: "ALIGNED", partial: "PARTLY", none: "–" } as const;

function Cell({ v }: { v: number | null }) {
  if (v == null) return <span className="matrix-cell dim">—</span>;
  const alpha = 0.06 + 0.44 * Math.min(1, Math.abs(v) / FULL_AT);
  return (
    <span className="matrix-cell"
          style={{ background: `rgba(var(${v >= 0 ? "--heat-up" : "--heat-down"}), ${alpha.toFixed(2)})` }}>
      {v > 0 ? "+" : v < 0 ? "−" : ""}{Math.abs(Math.round(v))}
    </span>
  );
}

function Rows({ groups }: { groups: RadarGroup[] }) {
  return (
    <div>
      <div className="matrix-row head">
        <span>GROUP</span>
        {WINDOWS.map(([, label]) => <span key={label}>{label}</span>)}
        <span>TREND</span>
      </div>
      {groups.map((g) => (
        <div key={g.symbol} className="matrix-row" title={`${g.label} (${g.symbol}) against SPY`}>
          <span className="matrix-name">{g.label}</span>
          {WINDOWS.map(([key]) => <Cell key={key} v={g.now[key] as number | null} />)}
          <span className="matrix-trend" data-state={g.aligned ?? "none"}>
            {g.aligned ? TREND[g.aligned] : "–"}
          </span>
        </div>
      ))}
    </div>
  );
}

export function StrengthMatrix({ radar, edges }: {
  radar: Radar;
  /** Show only this many from each end, with a link to the rest. */
  edges?: number;
}) {
  const all = radar.groups;
  const trimmed = edges != null && all.length > edges * 2;
  const left = trimmed ? all.slice(0, edges) : all.slice(0, Math.ceil(all.length / 2));
  const right = trimmed ? all.slice(-edges!) : all.slice(Math.ceil(all.length / 2));
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="matrix-cols">
        <Rows groups={left} />
        <Rows groups={right} />
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        Percent against the S&amp;P 500 over each window, strongest at six
        months first.
        {(radar.unreadable?.length ?? 0) > 0 && (
          <> Left out, because the price history holds a bad bar:{" "}
            {radar.unreadable!.map((u) => u.label).join(", ")}.</>
        )}
        {trimmed && (
          <> The {edges} strongest and {edges} weakest of {all.length} groups.{" "}
            <Link href="/market/radar" style={{ textDecoration: "underline" }}>The full matrix</Link>
          </>
        )}
      </p>
    </div>
  );
}
