"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
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

/** The four quadrants in one order, read by the legend and the list alike so
 *  they cannot drift apart. */
const QUADRANTS = ["powering_up", "turning_up", "cooling_off", "falling_back"] as const;

/** How many names a quadrant shows before asking. Powering up alone held 679;
 *  sectioning the list was pointless if each section stayed a wall. */
const PREVIEW_ROWS = 25;

/**
 * The viewBox is measured rather than fixed.
 *
 * It used to be a constant 320 units wide, stretched to whatever the container
 * was. On a phone that was about 1:1 and looked right. Once the page widened to
 * 1280 the same box was scaled three and a half times — every label, every dot
 * and every tick blown up with it, so a 10px name rendered at 36px. Nothing was
 * wrong with the drawing; the unit was wrong.
 *
 * One SVG unit is now one CSS pixel, so text is the size it says it is and the
 * extra width buys what extra width should buy: room between the points.
 */
const PAD = 30;
/** The drawn dot, and the invisible disc that catches a finger. A 3px radius is
 *  a 6px target; nothing on a touchscreen hits that. */
const DOT = 3.5;
const HIT = 12;
const BOX = { min: 280, max: 520, ratio: 0.58, step: 20 } as const;
/** Tails and names are for a map a reader can take in whole. A few dozen
 *  industries, yes; two and a half thousand stocks would be a hairball. */
const TAILS_UP_TO = 80;
const NAMES_SHOWN = 16;
const NAME_PX = 6.1;   // an 11px label, per character, near enough to keep names apart

/**
 * Which dots get their name written beside them.
 *
 * The map used to be anonymous: coloured dots, and a name only for the one
 * under the cursor. The names worth printing are the ones at the edges, since
 * those are what a rotation map is read for, so candidates are taken furthest
 * from the centre first and a name is skipped when it would sit on one already
 * placed. Each goes on the outward side of its dot.
 */
function placeNames(points: RotationPoint[], px: (x: number) => number,
                    py: (y: number) => number, yMax: number, W: number, H: number) {
  const ranked = [...points].sort((a, b) =>
    Math.hypot(((b.x as number) - 50) / 49, (b.y as number) / yMax)
    - Math.hypot(((a.x as number) - 50) / 49, (a.y as number) / yMax));
  const placed: { id: string; x: number; y: number; anchor: "start" | "end"; text: string;
                  box: [number, number, number, number] }[] = [];
  for (const point of ranked) {
    if (placed.length >= NAMES_SHOWN) break;
    const text = point.label.length > 24 ? `${point.label.slice(0, 23)}…` : point.label;
    const cx = px(point.x as number);
    const cy = py(point.y as number);
    const width = text.length * NAME_PX;
    const left = cx > W / 2;
    const x0 = left ? cx - 8 - width : cx + 8;
    if (x0 < 2 || x0 + width > W - 2 || cy < PAD + 4 || cy > H - PAD - 2) continue;
    const box: [number, number, number, number] = [x0 - 3, cy - 9, x0 + width + 3, cy + 5];
    if (placed.some((p) => box[0] < p.box[2] && box[2] > p.box[0]
                           && box[1] < p.box[3] && box[3] > p.box[1])) continue;
    placed.push({ id: point.id, x: left ? cx - 8 : cx + 8, y: cy + 3.5,
                  anchor: left ? "end" : "start", text, box });
  }
  return placed;
}

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
  // Hovering reads a point; tapping keeps it. Every dot carried a <title>, which
  // a mouse takes a second to show and a touchscreen never shows at all — so on
  // a phone this was several hundred coloured dots and no way to ask which.
  const [hovered, setHovered] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const group = groups.find((g) => g.key === tab) ?? groups[0];

  const frame = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(320);
  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const apply = () => {
      // Rounded DOWN to a step: to a step so dragging a window does not redraw
      // at every width, and down so the box never exceeds the space it is drawn
      // into — rounding to nearest gave a 360-unit box in 340px of container,
      // which quietly scaled everything by 0.94 again.
      const width = Math.max(240, element.clientWidth);
      setW(Math.floor(width / BOX.step) * BOX.step);
    };
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const H = Math.min(BOX.max, Math.max(BOX.min, Math.round(W * BOX.ratio)));

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

  const reading = points.find((p) => p.id === (hovered ?? pinned)) ?? null;

  const px = (x: number) => PAD + ((x - 1) / 98) * (W - PAD * 2);
  const py = (y: number) => H - PAD - ((y + yMax) / (2 * yMax)) * (H - PAD * 2);
  const tails = points.length <= TAILS_UP_TO;
  const named = tails ? placeNames(points, px, py, yMax, W, H) : [];

  return (
    <div className="stack">
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {groups.map((option) => (
          <button
            key={option.key}
            type="button"
            className="control footnote"
            aria-pressed={option.key === tab}
            onClick={() => { setTab(option.key); setPinned(null); setHovered(null); }}
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
        {QUADRANTS.map((q) => (
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
        <div className="card" style={{ padding: "var(--pad-sm)" }} ref={frame}>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
               aria-label="Strength now against momentum versus a month ago">
            {/* Each quarter of the map in its own faint wash, so a dot's
                colour and the ground it sits on say the same thing. */}
            {([["turning_up", PAD, PAD], ["powering_up", px(50), PAD],
               ["falling_back", PAD, py(0)], ["cooling_off", px(50), py(0)]] as const)
              .map(([q, x, y]) => (
                <rect key={q} x={x} y={y} width={(W - PAD * 2) / 2} height={(H - PAD * 2) / 2}
                      fill={QUADRANT_COLOUR[q]} opacity="0.06" />
              ))}
            <line x1={px(50)} y1={PAD} x2={px(50)} y2={H - PAD}
                  stroke="var(--border-stronger)" strokeWidth="1" />
            <line x1={PAD} y1={py(0)} x2={W - PAD} y2={py(0)}
                  stroke="var(--border-stronger)" strokeWidth="1" />
            {[25, 50, 75].map((tick) => (
              <text key={tick} x={px(tick)} y={H - PAD + 12} textAnchor="middle" fontSize="9"
                    fill="var(--text-muted)" style={{ fontFamily: "var(--font-mono)" }}>
                RS {tick}
              </text>
            ))}
            {[yMax, -yMax].map((tick) => (
              <text key={tick} x={px(50) + 4} y={py(tick) + (tick > 0 ? 9 : -3)} fontSize="9"
                    fill="var(--text-muted)" style={{ fontFamily: "var(--font-mono)" }}>
                {tick > 0 ? "+" : "−"}{Math.abs(Math.round(tick))}
              </text>
            ))}
            <text x={W - PAD} y={PAD - 8} textAnchor="end" fontSize="11"
                  fill="var(--q-powering)">{labels.powering_up}</text>
            <text x={PAD} y={PAD - 8} fontSize="11" fill="var(--q-turning)">
              {labels.turning_up}
            </text>
            <text x={W - PAD} y={H - 8} textAnchor="end" fontSize="11"
                  fill="var(--q-cooling)">{labels.cooling_off}</text>
            <text x={PAD} y={H - 8} fontSize="11" fill="var(--q-falling)">
              {labels.falling_back}
            </text>
            {/* Tapping the background puts the map back to no selection. */}
            <rect x={0} y={0} width={W} height={H} fill="transparent"
                  onClick={() => setPinned(null)} />
            {/* Where each one sat a month ago: the tail starts at the strength
                it had then and ends at the dot. Height is the change itself, so
                a long tail from the left is a group that has climbed. */}
            {tails && points.map((point) => {
              const x = point.x as number;
              const y = point.y as number;
              const from = Math.min(99, Math.max(1, x - y));
              if (Math.abs(px(x) - px(from)) < 6) return null;
              const dim = highlighted.size > 0 && !highlighted.has(point.id);
              return (
                <line key={`tail-${point.id}`} x1={px(from)} y1={py(y)} x2={px(x)} y2={py(y)}
                      stroke={QUADRANT_COLOUR[point.quadrant ?? ""] ?? "var(--text-muted)"}
                      strokeWidth="1.5" opacity={dim ? 0.08 : 0.4}
                      style={{ pointerEvents: "none" }} />
              );
            })}
            {points.map((point) => {
              const dim = highlighted.size > 0 && !highlighted.has(point.id);
              const open = reading?.id === point.id;
              return (
                <g
                  key={point.id}
                  onPointerEnter={() => setHovered(point.id)}
                  onPointerLeave={() => setHovered((v) => (v === point.id ? null : v))}
                  onClick={(event) => {
                    event.stopPropagation();
                    setPinned((v) => (v === point.id ? null : point.id));
                  }}
                  style={{ cursor: "pointer" }}
                >
                  <circle
                    cx={px(point.x as number)}
                    cy={py(point.y as number)}
                    r={HIT}
                    fill="transparent"
                  />
                  <circle
                    cx={px(point.x as number)}
                    cy={py(point.y as number)}
                    r={open || highlighted.has(point.id) ? 5 : DOT}
                    fill={QUADRANT_COLOUR[point.quadrant ?? ""] ?? "var(--text-muted)"}
                    opacity={dim ? 0.18 : 0.85}
                    stroke={open ? "var(--text-primary)" : "none"}
                    strokeWidth={open ? 1.5 : 0}
                    style={{ pointerEvents: "none" }}
                  >
                    <title>{`${point.label} · RS ${point.x} · ${signed(point.y, 0, " pts")}`}</title>
                  </circle>
                </g>
              );
            })}
            {named.filter((n) => n.id !== reading?.id
                                 && (highlighted.size === 0 || highlighted.has(n.id))).map((n) => (
              <text key={`name-${n.id}`} x={n.x} y={n.y} textAnchor={n.anchor} fontSize="11"
                    fill="var(--text-secondary)" stroke="var(--surface-1)" strokeWidth="3"
                    paintOrder="stroke" style={{ pointerEvents: "none" }}>
                {n.text}
              </text>
            ))}
            {/* The name, drawn last so it sits above every dot, and flipped to
                the left of the point when it would otherwise run off the edge. */}
            {reading && (() => {
              const cx = px(reading.x as number);
              const cy = py(reading.y as number);
              const flip = cx > W * 0.6;
              return (
                <text
                  x={flip ? cx - 9 : cx + 9}
                  y={cy - 8}
                  textAnchor={flip ? "end" : "start"}
                  fontSize="12"
                  fill="var(--text-primary)"
                  stroke="var(--surface-1)"
                  strokeWidth="3"
                  paintOrder="stroke"
                  style={{ pointerEvents: "none" }}
                >
                  {reading.label}
                </text>
              );
            })()}
          </svg>
          {/* Below the map rather than floating over it: a box that follows the
              cursor covers the very dots you are comparing, and on a phone it
              would sit under your finger. */}
          <div className="between" style={{ minHeight: 34, gap: "var(--gap-sm)" }}>
            {reading ? (
              <>
                <span className="grow footnote">
                  {group.hrefPrefix ? (
                    <Link href={`${group.hrefPrefix}${reading.id}`}>{reading.label}</Link>
                  ) : reading.label}
                  <span className="caption dim">
                    {" "}· {labels[reading.quadrant ?? ""] ?? "—"}
                  </span>
                </span>
                <span className="num caption">
                  RS {reading.x} · {signed(reading.y, 0, " pts")} on the month
                </span>
              </>
            ) : (
              <span className="caption dim">
                {tails
                  ? "The furthest out are named. Each tail starts at the strength it had a month ago. Point at any dot to name it."
                  : "Point at a dot to name it, or tap one to keep it."}
              </span>
            )}
          </div>
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
        // One flat list of two thousand rows, every one of them repeating its own
        // quadrant in the last column, is not a list anyone can read. The four
        // quadrants are the thing the page is about, so they are the structure:
        // a section each, in the legend's order, and the column that said the
        // same word two thousand times is gone.
        <div className="quadrant-lists">
          {QUADRANTS.map((quadrant) => {
            const rows = [...points]
              .filter((p) => (p.quadrant ?? "") === quadrant)
              .filter((p) => highlighted.size === 0 || highlighted.has(p.id))
              .sort((a, b) => (b.x ?? 0) - (a.x ?? 0));
            // A search is already a narrow answer; capping it would hide the
            // very rows somebody went looking for.
            const searching = highlighted.size > 0;
            const open = searching || expanded.has(quadrant);
            const shown = open ? rows : rows.slice(0, PREVIEW_ROWS);
            // A search that matched one name should not answer with three
            // headings saying it did not match. Empty quadrants still show when
            // nobody is searching, because "nothing is powering up" is itself a
            // reading of the market.
            if (searching && rows.length === 0) return null;
            return (
              <section key={quadrant} className="stack" style={{ gap: "var(--gap-xs)" }}>
                <div className="between">
                  <div className="row" style={{ gap: "var(--gap-sm)" }}>
                    <span aria-hidden style={{
                      width: 8, height: 8, borderRadius: 2,
                      background: QUADRANT_COLOUR[quadrant], flexShrink: 0,
                    }} />
                    <span className="eyebrow" style={{ color: QUADRANT_COLOUR[quadrant] }}>
                      {labels[quadrant]}
                    </span>
                  </div>
                  <span className="caption dim num">{rows.length}</span>
                </div>

                {rows.length === 0 ? (
                  <p className="caption dim" style={{ margin: 0 }}>
                    {searching ? "No match here." : "Nothing in this quadrant."}
                  </p>
                ) : (
                  <>
                    <div className="scroll-x card" style={{ padding: 0 }}>
                      <table className="data">
                        <thead>
                          <tr><th>Name</th><th>RS</th><th>Δ 1m</th></tr>
                        </thead>
                        <tbody>
                          {shown.map((point) => (
                            <tr key={point.id}>
                              <td className="text">
                                {group.hrefPrefix ? (
                                  <Link href={`${group.hrefPrefix}${point.id}`}>{point.label}</Link>
                                ) : (
                                  point.label
                                )}
                              </td>
                              <td>{point.x}</td>
                              <td style={{ color: QUADRANT_COLOUR[quadrant] }}>
                                {signed(point.y, 0, "")}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {rows.length > PREVIEW_ROWS && !searching && (
                      <button
                        type="button"
                        className="control footnote"
                        onClick={() => setExpanded((was) => {
                          const next = new Set(was);
                          if (next.has(quadrant)) next.delete(quadrant);
                          else next.add(quadrant);
                          return next;
                        })}
                      >
                        {open
                          ? `Show the strongest ${PREVIEW_ROWS}`
                          : `Show all ${rows.length}`}
                      </button>
                    )}
                  </>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
