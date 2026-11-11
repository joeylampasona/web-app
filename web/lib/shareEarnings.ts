"use client";

import { SITE_NAME } from "@/lib/copy";

/**
 * An earnings read as one image: the company, the takeaway, the four figures,
 * what the numbers say, eight quarters as bars, what is not obvious and the
 * final read.
 *
 * It is the card on the page, redrawn at a size made for posting, with the
 * same words: nothing is summarised or reworded for the image. Drawn by hand
 * on a canvas with colours read from the tokens, so it matches whichever
 * theme the reader is in, and it is as tall as the read is long.
 */
export interface EarningsCard {
  symbol: string;
  name: string;
  /** "Reported Nov 9 · quarter ending Sep 2026" */
  dateline: string;
  takeaway: string;
  /** How many of the flags are weak decides the takeaway's frame. */
  frame: "good" | "warn" | "bad";
  tiles: { label: string; value: string; chip?: string | null; tone?: 1 | 0 | -1 }[];
  flags: { tone: 1 | 0 | -1; text: string }[];
  forensic: { tone: 1 | 0 | -1; text: string }[];
  bars: { title: string; values: (number | null)[] }[];
  /** "shares +5.4% in a year · net cash $51.8M" */
  footnote?: string | null;
  /** What Market Desk measured around the print, as the card words it. */
  desk?: string | null;
  growth: string;
  proof: string;
  question: string;
  test: string;
}

const W = 1200;
const PAD = 56;
const MAX_H = 3200;
const MARK = { "1": "▲", "0": "·", "-1": "▼" } as const;

function token(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name);
  return value.trim() || fallback;
}

function wrap(ctx: CanvasRenderingContext2D, text: string, width: number): string[] {
  const out: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    const next = line ? `${line} ${word}` : word;
    if (!line || ctx.measureText(next).width <= width) { line = next; continue; }
    out.push(line);
    line = word;
  }
  if (line) out.push(line);
  return out;
}

export async function renderEarningsImage(card: EarningsCard): Promise<Blob | null> {
  if (typeof document === "undefined") return null;
  const display = "'IBM Plex Sans Condensed', 'Arial Narrow', sans-serif";
  const sans = "'IBM Plex Sans', system-ui, sans-serif";
  const mono = "'IBM Plex Mono', ui-monospace, monospace";
  try {
    await Promise.all([
      document.fonts.load(`700 48px ${display}`), document.fonts.load(`400 22px ${sans}`),
      document.fonts.load(`600 22px ${sans}`), document.fonts.load(`600 34px ${mono}`),
      document.fonts.load(`400 16px ${mono}`),
    ]);
  } catch { /* the fallbacks keep the layout */ }

  const scale = 2;
  const canvas = document.createElement("canvas");
  canvas.width = W * scale;
  canvas.height = MAX_H * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(scale, scale);

  const paper = token("--surface-0", "#F2F4F3");
  const raised = token("--surface-2", "#FFFFFF");
  const ink = token("--text-primary", "#101412");
  const secondary = token("--text-secondary", "#3A433F");
  const muted = token("--text-muted", "#5A645F");
  const border = token("--border", "#C5CCC8");
  const rule = token("--rule", "#101412");
  const brand = token("--brand", "#D8F23A");
  const onBrand = token("--on-brand", "#101412");
  const gain = token("--gain", "#0B6B3A");
  const loss = token("--loss", "#B3261E");
  const warn = token("--warn", "#A16207");
  const toneColour = (tone: 1 | 0 | -1 | undefined) => (tone === 1 ? gain : tone === -1 ? loss : muted);
  const inner = W - PAD * 2;

  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, W, MAX_H);
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
  ctx.font = `400 16px ${mono}`;
  ctx.fillStyle = secondary;
  ctx.textAlign = "right";
  ctx.fillText("EARNINGS READ · THE QUARTER AS FILED", W - PAD, 60);
  ctx.textAlign = "left";
  ctx.fillStyle = rule;
  ctx.fillRect(PAD, 78, inner, 4);

  // ---- the company: ticker under the highlighter, name beside it
  let y = 150;
  ctx.font = `600 44px ${mono}`;
  const tickerWidth = ctx.measureText(card.symbol).width + 28;
  ctx.fillStyle = brand;
  ctx.fillRect(PAD, y - 46, tickerWidth, 60);
  ctx.fillStyle = onBrand;
  ctx.fillText(card.symbol, PAD + 14, y);
  let size = 50;
  ctx.font = `700 ${size}px ${display}`;
  const room = inner - tickerWidth - 22;
  while (size > 30 && ctx.measureText(card.name).width > room) {
    size -= 2;
    ctx.font = `700 ${size}px ${display}`;
  }
  let name = card.name;
  while (name.length > 8 && ctx.measureText(name).width > room) name = `${name.slice(0, -2).trimEnd()}…`;
  ctx.fillStyle = ink;
  ctx.fillText(name, PAD + tickerWidth + 22, y);
  y += 40;
  ctx.font = `400 16px ${mono}`;
  ctx.fillStyle = muted;
  ctx.fillText(card.dateline.toUpperCase(), PAD, y);
  y += 28;

  // ---- the takeaway, framed by how the quarter read
  ctx.font = `400 26px ${sans}`;
  const takeaway = wrap(ctx, card.takeaway, inner - 48);
  const boxH = 62 + takeaway.length * 36;
  ctx.fillStyle = raised;
  ctx.fillRect(PAD, y, inner, boxH);
  ctx.strokeStyle = card.frame === "good" ? gain : card.frame === "bad" ? loss : warn;
  ctx.lineWidth = 3;
  ctx.strokeRect(PAD, y, inner, boxH);
  ctx.font = `600 20px ${sans}`;
  ctx.fillStyle = ink;
  ctx.fillText("Key takeaway", PAD + 24, y + 38);
  ctx.font = `400 26px ${sans}`;
  takeaway.forEach((line, i) => ctx.fillText(line, PAD + 24, y + 76 + i * 36));
  y += boxH + 28;

  // ---- four figures
  const gap = 14;
  const tileW = (inner - gap * (card.tiles.length - 1)) / card.tiles.length;
  const tileH = 138;
  card.tiles.forEach((tile, i) => {
    const left = PAD + i * (tileW + gap);
    ctx.fillStyle = raised;
    ctx.fillRect(left, y, tileW, tileH);
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.strokeRect(left + 0.5, y + 0.5, tileW - 1, tileH - 1);
    ctx.font = `400 15px ${sans}`;
    ctx.fillStyle = muted;
    ctx.fillText(tile.label, left + 16, y + 30);
    ctx.font = `600 34px ${mono}`;
    ctx.fillStyle = ink;
    ctx.fillText(tile.value, left + 16, y + 76);
    if (tile.chip) {
      ctx.font = `600 15px ${sans}`;
      ctx.fillStyle = toneColour(tile.tone);
      let chip = tile.chip;
      while (chip.length > 6 && ctx.measureText(chip).width > tileW - 32) chip = `${chip.slice(0, -2).trimEnd()}…`;
      ctx.fillText(chip, left + 16, y + 112);
    }
  });
  y += tileH + 40;

  const heading = (text: string) => {
    ctx.font = `700 24px ${display}`;
    ctx.fillStyle = ink;
    ctx.fillText(text, PAD, y);
    ctx.fillStyle = rule;
    ctx.fillRect(PAD, y + 9, inner, 1.5);
    y += 44;
  };
  const lines = (rows: EarningsCard["flags"]) => {
    for (const row of rows) {
      ctx.font = `400 21px ${sans}`;
      const wrapped = wrap(ctx, row.text, inner - 40);
      ctx.fillStyle = toneColour(row.tone);
      ctx.font = `400 18px ${sans}`;
      ctx.fillText(MARK[String(row.tone) as keyof typeof MARK], PAD + 2, y);
      ctx.font = `400 21px ${sans}`;
      ctx.fillStyle = ink;
      wrapped.forEach((line, i) => ctx.fillText(line, PAD + 36, y + i * 30));
      y += wrapped.length * 30 + 8;
    }
  };

  if (card.flags.length) {
    heading("What the numbers say");
    lines(card.flags);
    y += 22;
  }

  // ---- the quarters as bars
  const charts = card.bars.filter((b) => b.values.some((v) => v != null));
  if (charts.length) {
    const chartGap = 36;
    const chartW = (inner - chartGap * (charts.length - 1)) / charts.length;
    const chartH = 84;
    charts.forEach((chart, c) => {
      const left = PAD + c * (chartW + chartGap);
      ctx.font = `400 15px ${sans}`;
      ctx.fillStyle = muted;
      ctx.fillText(chart.title, left, y);
      const known = chart.values.filter((v): v is number => v != null);
      const hi = Math.max(0, ...known), lo = Math.min(0, ...known);
      const span = hi - lo || 1;
      const top = y + 12;
      const zero = top + (hi / span) * chartH;
      const barGap = 5;
      const barW = (chartW - barGap * (chart.values.length - 1)) / chart.values.length;
      chart.values.forEach((v, i) => {
        if (v == null) return;
        const h = Math.max((Math.abs(v) / span) * chartH, 1.5);
        ctx.globalAlpha = i === chart.values.length - 1 ? 1 : 0.5;
        ctx.fillStyle = v >= 0 ? gain : loss;
        ctx.fillRect(left + i * (barW + barGap), v >= 0 ? zero - h : zero, barW, h);
      });
      ctx.globalAlpha = 1;
      ctx.fillStyle = border;
      ctx.fillRect(left, zero, chartW, 1);
    });
    y += chartH + 40;
    if (card.footnote) {
      ctx.font = `400 16px ${sans}`;
      ctx.fillStyle = muted;
      ctx.fillText(card.footnote, PAD, y);
      y += 16;
    }
    y += 28;
  }

  if (card.forensic.length) {
    heading("What is not obvious");
    lines(card.forensic);
    y += 22;
  }

  if (card.desk) {
    heading("The desk's own read");
    ctx.font = `400 21px ${sans}`;
    ctx.fillStyle = secondary;
    for (const line of wrap(ctx, card.desk, inner)) { ctx.fillText(line, PAD, y); y += 30; }
    y += 30;
  }

  // ---- the final read
  ctx.font = `400 20px ${sans}`;
  const question = wrap(ctx, `Key question: ${card.question}`, inner - 48);
  const test = wrap(ctx, card.test, inner - 48);
  const finalH = 96 + (question.length + test.length) * 29 + 22;
  ctx.fillStyle = raised;
  ctx.fillRect(PAD, y, inner, finalH);
  ctx.strokeStyle = rule;
  ctx.lineWidth = 2;
  ctx.strokeRect(PAD, y, inner, finalH);
  ctx.font = `600 20px ${sans}`;
  ctx.fillStyle = ink;
  ctx.fillText("Final read", PAD + 24, y + 38);
  let x = PAD + 24;
  const piece = (text: string, colour: string, weight = 400) => {
    ctx.font = `${weight} 26px ${sans}`;
    ctx.fillStyle = colour;
    ctx.fillText(text, x, y + 78);
    x += ctx.measureText(text).width;
  };
  piece("Growth: ", ink);
  piece(card.growth, card.growth === "REAL" ? gain : card.growth === "WEAK" ? loss : muted, 600);
  piece("  ·  Economic proof: ", ink);
  piece(card.proof, card.proof === "SHOWN" ? gain : loss, 600);
  let fy = y + 118;
  ctx.font = `400 20px ${sans}`;
  ctx.fillStyle = secondary;
  for (const line of question) { ctx.fillText(line, PAD + 24, fy); fy += 29; }
  fy += 6;
  ctx.fillStyle = ink;
  for (const line of test) { ctx.fillText(line, PAD + 24, fy); fy += 29; }
  y += finalH + 44;

  // ---- foot
  ctx.font = `400 15px ${sans}`;
  ctx.fillStyle = muted;
  ctx.fillText("From the company's 10-Q and 10-K, read by fixed rules. A reading of the filing, not a view on the stock. Not investment advice.",
    PAD, y);
  ctx.textAlign = "right";
  ctx.font = `600 15px ${mono}`;
  ctx.fillStyle = ink;
  ctx.fillText(typeof window === "undefined" ? "" : window.location.host, W - PAD, y);
  ctx.textAlign = "left";
  const height = Math.min(MAX_H, Math.ceil(y + 36));

  // The canvas was made tall enough for any read; hand back only what was drawn.
  const out = document.createElement("canvas");
  out.width = W * scale;
  out.height = height * scale;
  out.getContext("2d")?.drawImage(canvas, 0, 0);
  return new Promise((resolve) => out.toBlob((blob) => resolve(blob), "image/png"));
}
