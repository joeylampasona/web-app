"use client";

import { SITE_NAME } from "@/lib/copy";

/**
 * The night's read as one image: the headline under the highlighter, the
 * four checks as a meter, the breadth barcode, and the date.
 *
 * It is the top of the home page, redrawn at a size made for posting. Drawn
 * by hand on a canvas, as the stock card's image is, so there is no new
 * dependency and the colours are read from the tokens at draw time: the image
 * matches whichever theme the reader is in.
 *
 * A still outlives the session it describes, so the date is set large enough
 * to survive a crop and the image says what it is not.
 */
export interface ReadCard {
  /** The session's date, ISO. */
  asOf: string;
  headline: string;
  blurb: string;
  cells: { label: string; value: string; score: -1 | 0 | 1 }[];
  /** One character per ranked stock, strongest first: 3 above both lines,
   *  2 and 1 above one, 0 under both. */
  ticks?: string | null;
  /** The radar's label for where strength sits. */
  strength?: string | null;
}

const W = 1200;
const H = 675;
const PAD = 56;
const STATE: Record<string, string> = { "1": "In gear", "0": "Neither", "-1": "Against" };

function token(name: string, fallback = "#000"): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name);
  return value.trim() || fallback;
}

/** The headline split the way the page marks it: [plain lead, marked, plain tail]. */
function parts(text: string): [string, string, string] {
  const lead = "The tape is ";
  if (text.startsWith(lead)) return [lead, `${text.slice(lead.length)}.`, ""];
  const comma = text.indexOf(",");
  if (comma > 0) return ["", text.slice(0, comma), `${text.slice(comma)}.`];
  return ["", `${text}.`, ""];
}

function wrap(ctx: CanvasRenderingContext2D, text: string, width: number, lines: number): string[] {
  const out: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width <= width) { line = next; continue; }
    out.push(line);
    line = word;
    if (out.length === lines) break;
  }
  if (out.length < lines && line) out.push(line);
  return out;
}

export async function renderReadImage(card: ReadCard): Promise<Blob | null> {
  if (typeof document === "undefined") return null;
  const display = "'IBM Plex Sans Condensed', 'Arial Narrow', sans-serif";
  const sans = "'IBM Plex Sans', system-ui, sans-serif";
  const mono = "'IBM Plex Mono', ui-monospace, monospace";
  try {
    // A canvas draws with a face only once that exact weight has loaded.
    await Promise.all([
      document.fonts.load(`700 96px ${display}`), document.fonts.load(`400 24px ${sans}`),
      document.fonts.load(`600 30px ${mono}`), document.fonts.load(`400 16px ${mono}`),
    ]);
  } catch { /* the fallbacks keep the layout */ }

  const canvas = document.createElement("canvas");
  canvas.width = W * 2;
  canvas.height = H * 2;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(2, 2);

  const paper = token("--surface-0", "#F2F4F3");
  const ink = token("--text-primary", "#101412");
  const muted = token("--text-muted", "#5A645F");
  const secondary = token("--text-secondary", "#3A433F");
  const border = token("--border", "#C5CCC8");
  const rule = token("--rule", "#101412");
  const brand = token("--brand", "#D8F23A");
  const onBrand = token("--on-brand", "#101412");
  const gain = token("--gain", "#0B6B3A");
  const loss = token("--loss", "#B3261E");

  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, W, H);
  ctx.textBaseline = "alphabetic";

  // ---- masthead on an ink rule
  ctx.fillStyle = brand;
  ctx.fillRect(PAD, 40, 20, 20);
  ctx.strokeStyle = rule;
  ctx.lineWidth = 3;
  ctx.strokeRect(PAD, 40, 20, 20);
  ctx.fillStyle = ink;
  ctx.font = `700 30px ${display}`;
  ctx.fillText(SITE_NAME.toUpperCase(), PAD + 32, 62);
  const day = new Date(`${card.asOf}T12:00:00Z`);
  const dateline = `${day.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" })} close · `
    + day.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  ctx.font = `400 16px ${mono}`;
  ctx.fillStyle = secondary;
  ctx.textAlign = "right";
  ctx.fillText(dateline.toUpperCase(), W - PAD, 60);
  ctx.textAlign = "left";
  ctx.fillStyle = rule;
  ctx.fillRect(PAD, 78, W - PAD * 2, 4);

  // ---- the read
  const inGear = card.cells.filter((c) => c.score === 1).length;
  ctx.font = `400 15px ${mono}`;
  ctx.fillStyle = muted;
  ctx.fillText(`THE READ${card.cells.length ? ` · ${inGear} OF ${card.cells.length} CHECKS IN GEAR` : ""}`, PAD, 122);

  const [lead, marked, tail] = parts(card.headline);
  let size = 104;
  ctx.font = `700 ${size}px ${display}`;
  while (size > 56 && ctx.measureText(lead + marked + tail).width > W - PAD * 2 - 24) {
    size -= 4;
    ctx.font = `700 ${size}px ${display}`;
  }
  const base = 132 + size;
  let x = PAD;
  ctx.fillStyle = ink;
  ctx.fillText(lead, x, base);
  x += ctx.measureText(lead).width;
  const markWidth = ctx.measureText(marked).width;
  ctx.fillStyle = brand;
  ctx.fillRect(x - 6, base - size * 0.86, markWidth + 16, size * 1.08);
  ctx.fillStyle = onBrand;
  ctx.fillText(marked, x + 2, base);
  x += markWidth + 16;
  ctx.fillStyle = ink;
  ctx.fillText(tail, x, base);

  ctx.font = `400 23px ${sans}`;
  ctx.fillStyle = secondary;
  let y = base + 52;
  for (const line of wrap(ctx, card.blurb, W - PAD * 2 - 160, 2)) {
    ctx.fillText(line, PAD, y);
    y += 32;
  }

  // ---- the meter
  const meterTop = Math.max(y + 6, 356);
  const cellH = 118;
  if (card.cells.length) {
    const cellW = (W - PAD * 2) / card.cells.length;
    card.cells.forEach((cell, i) => {
      const left = PAD + i * cellW;
      const lit = cell.score === 1;
      ctx.fillStyle = lit ? brand : token("--surface-2", "#fff");
      ctx.fillRect(left, meterTop, cellW, cellH);
      ctx.fillStyle = lit ? rule : cell.score === -1 ? loss : border;
      ctx.fillRect(left, meterTop, cellW, 8);
      const text = lit ? onBrand : ink;
      ctx.font = `400 12px ${mono}`;
      ctx.fillStyle = lit ? onBrand : muted;
      ctx.fillText(cell.label.toUpperCase().slice(0, 34), left + 14, meterTop + 34);
      ctx.font = `600 38px ${mono}`;
      ctx.fillStyle = text;
      ctx.fillText(cell.value, left + 14, meterTop + 78);
      ctx.font = `400 16px ${sans}`;
      ctx.fillStyle = lit ? onBrand : secondary;
      ctx.fillText(STATE[String(cell.score)], left + 14, meterTop + 104);
      if (i) { ctx.fillStyle = border; ctx.fillRect(left, meterTop + 8, 1, cellH - 8); }
    });
    ctx.strokeStyle = rule;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(PAD, meterTop, W - PAD * 2, cellH);
  }

  // ---- the barcode
  const barTop = meterTop + cellH + 40;
  const barH = Math.max(34, Math.min(64, H - 62 - barTop));
  if (card.ticks && card.ticks.length > 20) {
    const colours: Record<string, string> = {
      "3": gain, "2": `rgba(${token("--heat-up", "20,122,72")}, 0.45)`,
      "1": `rgba(${token("--heat-down", "205,84,40")}, 0.45)`, "0": loss,
    };
    const step = (W - PAD * 2) / card.ticks.length;
    for (let i = 0; i < card.ticks.length; i += 1) {
      ctx.fillStyle = colours[card.ticks[i]] ?? border;
      ctx.fillRect(PAD + i * step, barTop, step + 0.6, barH);
    }
    ctx.strokeStyle = rule;
    ctx.strokeRect(PAD, barTop, W - PAD * 2, barH);
    ctx.font = `400 13px ${mono}`;
    ctx.fillStyle = muted;
    ctx.fillText(`EVERY RANKED STOCK · STRONGEST ON THE LEFT · GREEN IS ABOVE ITS 50- AND 200-DAY LINES`,
      PAD, barTop - 10);
  }

  // ---- foot
  ctx.font = `400 14px ${sans}`;
  ctx.fillStyle = muted;
  const host = typeof window === "undefined" ? "" : window.location.host;
  ctx.fillText(`${card.strength ? `Where strength sits: ${card.strength}. ` : ""}Counts of what happened at the close, not a forecast. Not investment advice.`,
    PAD, H - 26);
  ctx.textAlign = "right";
  ctx.font = `600 14px ${mono}`;
  ctx.fillStyle = ink;
  ctx.fillText(host, W - PAD, H - 26);
  ctx.textAlign = "left";

  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), "image/png"));
}
