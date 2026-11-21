import "server-only";
import fs from "node:fs";
import path from "node:path";
import { ImageResponse } from "next/og";
import type { ReactNode } from "react";
import { SITE_NAME } from "@/lib/copy";
import { paperToken as ink } from "@/lib/ogTokens";

/**
 * The share cards, drawn on the server.
 *
 * A card drawn in the reader's browser exists only for the reader who pressed
 * the button. A pasted link showed the same supplied banner whatever page it
 * pointed at, and nothing outside a browser (the nightly's own message, for
 * one) could have a card at all. These are the same cards as addresses: one
 * layout, a headline under the highlighter, up to four figures and one
 * drawing, filled in differently by each page.
 *
 * Set in the site's own faces, read from files beside the code. The page
 * loads them from a font service, which an image renderer cannot do.
 */
export const CARD = { width: 1200, height: 630 } as const;

const DISPLAY = "Plex Condensed";
const SANS = "Plex Sans";
const MONO = "Plex Mono";

type Face = { name: string; data: Buffer; weight: 400 | 600 | 700; style: "normal" };
let faces: Face[] | null = null;

function fonts(): Face[] {
  if (faces) return faces;
  // Each path written out in full so the build's file tracing sees it.
  const file = (name: string) => fs.readFileSync(name);
  faces = [
    { name: DISPLAY, weight: 700, style: "normal",
      data: file(path.join(process.cwd(), "assets", "fonts", "PlexSansCondensed-Bold.ttf")) },
    { name: SANS, weight: 400, style: "normal",
      data: file(path.join(process.cwd(), "assets", "fonts", "PlexSans-Regular.ttf")) },
    { name: SANS, weight: 600, style: "normal",
      data: file(path.join(process.cwd(), "assets", "fonts", "PlexSans-SemiBold.ttf")) },
    { name: MONO, weight: 400, style: "normal",
      data: file(path.join(process.cwd(), "assets", "fonts", "PlexMono-Regular.ttf")) },
    { name: MONO, weight: 600, style: "normal",
      data: file(path.join(process.cwd(), "assets", "fonts", "PlexMono-SemiBold.ttf")) },
  ];
  return faces;
}

export interface CardCell {
  label: string;
  value: string;
  /** A word under the figure: "In gear", "+4 on the week". */
  note?: string | null;
  tone?: 1 | 0 | -1 | null;
  /** Set under the highlighter: the one cell the card is about. */
  marked?: boolean;
}

export interface CardBar { label: string; value: number; marked?: boolean }

export interface FigureCard {
  /** Right of the masthead: "FRIDAY CLOSE · NOV 20, 2026". */
  dateline: string;
  kicker: string;
  /** The headline in three parts; the middle one sits under the highlighter. */
  lead?: string;
  marked: string;
  tail?: string;
  sub?: string | null;
  cells?: CardCell[];
  /** A bar a day, or a bar a screen: the count is printed over each. */
  bars?: CardBar[];
  /** One character a ranked stock, strongest first (3 above both lines, 0
   *  under both), or failing that the healthy share of each tenth. */
  ticks?: string | null;
  tenths?: number[] | null;
  /** A drawing set to the right of the headline, already an element. */
  art?: ReactNode;
  /** The page this card is for, as printed in the foot: "/market/breadth". */
  path: string;
}

/** A sentence cut to fit a line count the renderer cannot enforce itself. */
export function clip(text: string | null | undefined, max: number): string {
  const clean = (text ?? "").replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), max - 24))}…`;
}

/** "FRIDAY CLOSE · NOV 20, 2026" from an ISO session date. */
export function closeLine(asOf: string | null | undefined): string {
  if (!asOf) return "";
  const day = new Date(`${asOf}T12:00:00Z`);
  if (Number.isNaN(day.getTime())) return "";
  const weekday = day.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" });
  const date = day.toLocaleDateString("en-US",
    { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  return `${weekday} close · ${date}`.toUpperCase();
}

/**
 * The largest size at which the headline still fits on one line.
 *
 * The renderer will not shrink text to fit, and a headline that wraps leaves
 * its highlighted word alone on a line of its own. The condensed bold face
 * runs a little under half its size a character, so the room is divided by
 * the length and kept inside the sizes the layout was drawn for.
 */
function headlineSize(text: string, narrow: boolean): number {
  const budget = narrow ? 1600 : 2150;
  return Math.max(44, Math.min(104, Math.floor(budget / Math.max(1, text.length))));
}

function Strip({ ticks, tenths }: { ticks?: string | null; tenths?: number[] | null }) {
  if (ticks && ticks.length > 0) {
    // Sampled down: four hundred hairlines at this width are a grey band.
    const want = 150;
    const step = Math.max(1, ticks.length / want);
    const sample: string[] = [];
    for (let i = 0; i < ticks.length && sample.length < want; i += step) {
      sample.push(ticks[Math.floor(i)]);
    }
    const shade: Record<string, string> = {
      "3": ink("text-primary"), "2": ink("border-stronger"),
      "1": ink("border-stronger"), "0": ink("border"),
    };
    return (
      <div style={{ display: "flex", width: "100%", height: 34, gap: 2 }}>
        {sample.map((tick, i) => (
          <div key={i} style={{ flex: 1, height: tick === "3" ? 34 : tick === "0" ? 12 : 22,
                                alignSelf: "flex-end", background: shade[tick] ?? ink("border") }} />
        ))}
      </div>
    );
  }
  if (tenths && tenths.length > 0) {
    return (
      <div style={{ display: "flex", width: "100%", height: 34, gap: 4 }}>
        {tenths.map((share, i) => (
          <div key={i} style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: MONO, fontSize: 14, fontWeight: 600,
            border: `1.5px solid ${ink("rule")}`,
            background: share >= 50 ? ink("text-primary") : ink("surface-0"),
            color: share >= 50 ? ink("surface-0") : ink("text-primary"),
          }}>
            {`${Math.round(share)}`}
          </div>
        ))}
      </div>
    );
  }
  return null;
}

function Cells({ cells }: { cells: CardCell[] }) {
  const toneColour = (tone: CardCell["tone"]) =>
    tone === 1 ? ink("gain") : tone === -1 ? ink("loss") : ink("text-muted");
  return (
    <div style={{ display: "flex", width: "100%", border: `2px solid ${ink("rule")}` }}>
      {cells.slice(0, 4).map((cell, i) => (
        <div key={cell.label} style={{
          flex: 1, display: "flex", flexDirection: "column", padding: "12px 16px 12px",
          borderLeft: i === 0 ? "none" : `1.5px solid ${ink("rule")}`,
          background: cell.marked ? ink("brand") : "transparent",
        }}>
          <div style={{ fontFamily: MONO, fontSize: 13, letterSpacing: 1.2,
                        color: cell.marked ? ink("on-brand") : ink("text-muted") }}>
            {clip(cell.label, 30).toUpperCase()}
          </div>
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 46, lineHeight: 1.1,
                        color: ink("text-primary") }}>
            {cell.value}
          </div>
          {cell.note ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8,
                          fontFamily: SANS, fontSize: 16, lineHeight: 1.25,
                          color: cell.marked ? ink("on-brand") : ink("text-secondary") }}>
              {cell.tone != null && !cell.marked ? (
                <div style={{ width: 10, height: 10, background: toneColour(cell.tone) }} />
              ) : null}
              {clip(cell.note, 56)}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function Bars({ bars }: { bars: CardBar[] }) {
  const top = Math.max(1, ...bars.map((bar) => bar.value));
  const tall = 96;
  return (
    <div style={{ display: "flex", width: "100%", gap: 14, alignItems: "flex-end",
                  borderBottom: `2px solid ${ink("rule")}` }}>
      {bars.slice(0, 12).map((bar) => (
        <div key={bar.label} style={{ flex: 1, display: "flex", flexDirection: "column",
                                      alignItems: "stretch" }}>
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 30,
                        color: ink("text-primary") }}>
            {bar.value.toLocaleString("en-US")}
          </div>
          <div style={{ height: Math.max(3, Math.round(tall * bar.value / top)),
                        background: bar.marked ? ink("brand") : ink("text-primary"),
                        border: bar.marked ? `2px solid ${ink("rule")}` : "none" }} />
        </div>
      ))}
    </div>
  );
}

function BarLabels({ bars }: { bars: CardBar[] }) {
  return (
    <div style={{ display: "flex", width: "100%", gap: 14, marginTop: 6 }}>
      {bars.slice(0, 12).map((bar) => (
        <div key={bar.label} style={{ flex: 1, display: "flex", fontFamily: MONO, fontSize: 13,
                                      letterSpacing: 0.6, color: ink("text-secondary") }}>
          {clip(bar.label, bars.length > 6 ? 15 : 18).toUpperCase()}
        </div>
      ))}
    </div>
  );
}

/** One card, as an image response. Every page's card goes through here. */
export function figureCard(card: FigureCard): ImageResponse {
  const narrow = Boolean(card.art);
  const headline = `${card.lead ?? ""}${card.marked}${card.tail ?? ""}`;
  const size = headlineSize(headline, narrow);
  const address = `thetape.cc${card.path === "/" ? "" : card.path}`;

  return new ImageResponse(
    (
      <div style={{
        width: "100%", height: "100%", display: "flex", flexDirection: "column",
        background: ink("surface-0"), color: ink("text-primary"),
        padding: "38px 52px 30px", fontFamily: SANS,
      }}>
        {/* The masthead, on an ink rule. */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                      paddingBottom: 14, borderBottom: `4px solid ${ink("rule")}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 22, height: 22, background: ink("brand"),
                          border: `3px solid ${ink("rule")}` }} />
            <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 32, letterSpacing: 1 }}>
              {SITE_NAME.toUpperCase()}
            </div>
          </div>
          <div style={{ fontFamily: MONO, fontSize: 16, letterSpacing: 1.2,
                        color: ink("text-secondary") }}>
            {card.dateline}
          </div>
        </div>

        {/* The headline, with the drawing beside it when there is one. */}
        <div style={{ display: "flex", flex: 1, alignItems: "center", gap: 32 }}>
          <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
            <div style={{ fontFamily: MONO, fontSize: 15, letterSpacing: 1.6,
                          color: ink("text-muted"), marginBottom: 8 }}>
              {card.kicker.toUpperCase()}
            </div>
            <div style={{ display: "flex", flexWrap: "nowrap", alignItems: "center",
                          fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 1.08 }}>
              {card.lead ? <div style={{ display: "flex", whiteSpace: "pre" }}>{card.lead}</div> : null}
              <div style={{ display: "flex", background: ink("brand"), color: ink("on-brand"),
                            padding: "0 12px", marginLeft: card.lead ? 0 : -4 }}>
                {card.marked}
              </div>
              {card.tail ? <div style={{ display: "flex", whiteSpace: "pre" }}>{card.tail}</div> : null}
            </div>
            {card.sub ? (
              <div style={{ fontSize: narrow ? 21 : 23, lineHeight: 1.35,
                            color: ink("text-secondary"),
                            marginTop: 14, maxWidth: narrow ? 760 : 1000 }}>
                {clip(card.sub, narrow ? 190 : 170)}
              </div>
            ) : null}
          </div>
          {card.art ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                          width: 250, height: 250, border: `2px solid ${ink("rule")}`,
                          background: ink("surface-1"), color: ink("text-primary") }}>
              {card.art}
            </div>
          ) : null}
        </div>

        {/* The figures. */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {card.bars && card.bars.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <Bars bars={card.bars} />
              <BarLabels bars={card.bars} />
            </div>
          ) : null}
          {card.cells && card.cells.length > 0 ? <Cells cells={card.cells} /> : null}
          <Strip ticks={card.ticks} tenths={card.tenths} />
        </div>

        {/* The foot: where it came from, and what it is not. */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                      marginTop: 16, fontFamily: MONO, fontSize: 15 }}>
          <div style={{ fontWeight: 600, color: ink("text-primary") }}>{address}</div>
          <div style={{ color: ink("text-muted") }}>
            Figures from the close. A screening tool, not investment advice.
          </div>
        </div>
      </div>
    ),
    { ...CARD, fonts: fonts() },
  );
}
