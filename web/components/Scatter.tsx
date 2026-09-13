"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { copy } from "@/lib/copy";
import { signed } from "@/lib/format";
import type { RotationPoint } from "@/lib/types";
import { Tooltip } from "./Tooltip";

const QUADRANT_COLOUR: Record<string, string> = {
  powering_up: "var(--q-powering)",
  turning_up: "var(--q-turning)",
  cooling_off: "var(--q-cooling)",
  falling_back: "var(--q-falling)",
};

const W = 320;
const H = 300;
const PAD = 26;

export function Scatter({
  groups, labels,
}: {
  groups: {
    key: string; label: string;
    points: RotationPoint[]; counts: Record<string, number>;
    hrefPrefix?: string;
  }[];
  labels: Record<string, string>;
}) {
  const [tab, setTab] = useState(groups[0]?.key ?? "");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"map" | "list">("map");
  const group = groups.find((g) => g.key === tab) ?? groups[0];

  const { points, yMax } = useMemo(() => {
    const rows = group.points.filter((p) => p.x !== null && p.y !== null);
    const bound = Math.max(10, ...rows.map((p) => Math.abs(p.y ?? 0)));
    return { points: rows, yMax: bound };
  }, [group]);

  const matches = query.trim().length > 0
    ? points.filter((p) =>
        p.label.toLowerCase().includes(query.toLowerCase()) ||
        p.name.toLowerCase().includes(query.toLowerCase()))
    : [];
  const highlighted = new Set(matches.map((m) => m.id));

  const px = (x: number) => PAD + ((x - 1) / 98) * (W - PAD * 2);
  const py = (y: number) => H - PAD - ((y + yMax) / (2 * yMax)) * (H - PAD * 2);

  return (
    <div className="stack">
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {groups.map((option) => (
          <button
            key={option.key}
            type="button"
            className="control footnote"
            aria-pressed={option.key === tab}
            onClick={() => setTab(option.key)}
          >
            {option.label}
          </button>
        ))}
        <span className="grow" />
        <div className="row" style={{ gap: 0 }}>
          <button type="button" className="control footnote" aria-pressed={mode === "map"}
                  style={{ borderRadius: "var(--radius) 0 0 var(--radius)" }}
                  onClick={() => setMode("map")}>Map</button>
          <button type="button" className="control footnote" aria-pressed={mode === "list"}
                  style={{ borderRadius: "0 var(--radius) var(--radius) 0", marginLeft: -1 }}
                  onClick={() => setMode("list")}>List</button>
        </div>
      </div>

      <input
        className="control"
        style={{ width: "100%", background: "var(--surface-2)", justifyContent: "flex-start" }}
        placeholder="Find on the map"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Find on the map"
      />

      <div className="grid-2" style={{ gap: "var(--gap-sm)" }}>
        {(["powering_up", "turning_up", "cooling_off", "falling_back"] as const).map((q) => (
          <div key={q} className="row footnote" style={{ gap: "var(--gap-sm)" }}>
            <span aria-hidden style={{
              width: 8, height: 8, borderRadius: 2, background: QUADRANT_COLOUR[q],
            }} />
            <span className="grow">{labels[q]}</span>
            <span className="num">{group.counts[q] ?? 0}</span>
          </div>
        ))}
      </div>

      {mode === "map" ? (
        <div className="card" style={{ padding: "var(--pad-sm)" }}>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
               aria-label="Strength now against momentum versus a month ago">
            <line x1={px(50)} y1={PAD} x2={px(50)} y2={H - PAD}
                  stroke="var(--chart-grid)" strokeWidth="1" />
            <line x1={PAD} y1={py(0)} x2={W - PAD} y2={py(0)}
                  stroke="var(--chart-grid)" strokeWidth="1" />
            <text x={W - PAD} y={PAD - 8} textAnchor="end" fontSize="9"
                  fill="var(--q-powering)">{labels.powering_up}</text>
            <text x={PAD} y={PAD - 8} fontSize="9" fill="var(--q-turning)">
              {labels.turning_up}
            </text>
            <text x={W - PAD} y={H - 8} textAnchor="end" fontSize="9"
                  fill="var(--q-cooling)">{labels.cooling_off}</text>
            <text x={PAD} y={H - 8} fontSize="9" fill="var(--q-falling)">
              {labels.falling_back}
            </text>
            {points.map((point) => {
              const dim = highlighted.size > 0 && !highlighted.has(point.id);
              return (
                <circle
                  key={point.id}
                  cx={px(point.x as number)}
                  cy={py(point.y as number)}
                  r={highlighted.has(point.id) ? 5 : 3}
                  fill={QUADRANT_COLOUR[point.quadrant ?? ""] ?? "var(--text-muted)"}
                  opacity={dim ? 0.18 : 0.85}
                >
                  <title>{`${point.label} · RS ${point.x} · ${signed(point.y, 0, " pts")}`}</title>
                </circle>
              );
            })}
          </svg>
          <div className="row footnote dim" style={{ justifyContent: "space-between" }}>
            <span className="row" style={{ gap: "var(--gap-xs)" }}>
              Strength now <Tooltip label="Strength now" text={copy("rotation.x")} />
            </span>
            <span className="row" style={{ gap: "var(--gap-xs)" }}>
              Momentum <Tooltip label="Momentum" text={copy("rotation.y")} />
            </span>
          </div>
        </div>
      ) : (
        <div className="scroll-x card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr><th>Name</th><th>RS</th><th>Δ 1m</th><th>Quadrant</th></tr>
            </thead>
            <tbody>
              {[...points]
                .sort((a, b) => (b.x ?? 0) - (a.x ?? 0))
                .filter((p) => highlighted.size === 0 || highlighted.has(p.id))
                .map((point) => (
                  <tr key={point.id}>
                    <td className="text">
                      {group.hrefPrefix ? (
                        <Link href={`${group.hrefPrefix}${point.id}`}>{point.label}</Link>
                      ) : (
                        point.label
                      )}
                    </td>
                    <td>{point.x}</td>
                    <td style={{ color: QUADRANT_COLOUR[point.quadrant ?? ""] }}>
                      {signed(point.y, 0, "")}
                    </td>
                    <td className="text caption">{labels[point.quadrant ?? ""] ?? "—"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
