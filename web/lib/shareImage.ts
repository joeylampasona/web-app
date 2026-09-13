"use client";

import { change, price, rsText } from "./format";

/**
 * Composes a shareable PNG: the chart as it appears on screen, the same metric
 * rows underneath, and the disclaimer. No new dependency — lightweight-charts
 * hands back its own canvas and the rest is drawn by hand.
 *
 * Colours come from the tokens at draw time, so the image matches whichever
 * theme the reader is in and no colour is written down twice.
 */
export interface ShareRow {
  label: string;
  value: string;
  tone?: "gain" | "loss" | "flat";
}

export interface SharePayload {
  symbol: string;
  name: string;
  close: number;
  changePct: number | null;
  stage: string;
  rs: number | string;
  rows: ShareRow[];
  chart: HTMLCanvasElement | null;
}

const W = 1200;
const PAD = 48;

function token(name: string, fallback = "#000"): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name);
  return value.trim() || fallback;
}

function toneColour(tone: ShareRow["tone"]): string {
  if (tone === "gain") return token("--gain");
  if (tone === "loss") return token("--loss");
  return token("--text-primary");
}

export async function renderShareImage(payload: SharePayload): Promise<Blob | null> {
  if (typeof document === "undefined") return null;
  try {
    await document.fonts.ready;
  } catch {
    /* fonts API unavailable; system fallbacks are fine */
  }

  const sans = "'Inter', system-ui, sans-serif";
  const mono = "'JetBrains Mono', ui-monospace, monospace";

  const chartHeight = payload.chart
    ? Math.round(((W - PAD * 2) / payload.chart.width) * payload.chart.height)
    : 0;
  const rowHeight = 52;
  const height = PAD + 120 + (chartHeight ? chartHeight + 36 : 0)
    + payload.rows.length * rowHeight + 96 + PAD;

  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  ctx.fillStyle = token("--surface-1");
  ctx.fillRect(0, 0, W, height);

  let y = PAD + 12;

  // -- header ---------------------------------------------------------
  ctx.fillStyle = token("--text-primary");
  ctx.font = `500 38px ${sans}`;
  ctx.textAlign = "left";
  ctx.fillText(payload.name.slice(0, 34), PAD, y + 30);

  ctx.fillStyle = token("--text-muted");
  ctx.font = `400 24px ${mono}`;
  ctx.fillText(payload.symbol, PAD, y + 66);

  ctx.textAlign = "right";
  ctx.fillStyle = token("--text-primary");
  ctx.font = `400 38px ${mono}`;
  ctx.fillText(price(payload.close), W - PAD, y + 30);

  // The glyph travels with the image: a screenshot must not encode gain or
  // loss with colour alone either.
  ctx.fillStyle = payload.changePct === null ? token("--flat")
    : payload.changePct >= 0 ? token("--gain") : token("--loss");
  ctx.font = `400 26px ${mono}`;
  ctx.fillText(change(payload.changePct), W - PAD, y + 66);

  y += 110;

  // -- chart ----------------------------------------------------------
  if (payload.chart && chartHeight) {
    ctx.drawImage(payload.chart, PAD, y, W - PAD * 2, chartHeight);
    y += chartHeight + 32;
  }

  // -- metric rows ----------------------------------------------------
  for (const row of payload.rows) {
    ctx.strokeStyle = token("--border");
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(PAD, y + rowHeight - 12);
    ctx.lineTo(W - PAD, y + rowHeight - 12);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.textAlign = "left";
    ctx.fillStyle = token("--text-secondary");
    ctx.font = `400 26px ${sans}`;
    ctx.fillText(row.label, PAD, y + 26);

    ctx.textAlign = "right";
    ctx.fillStyle = toneColour(row.tone);
    ctx.font = `400 28px ${mono}`;
    ctx.fillText(row.value, W - PAD, y + 26);
    y += rowHeight;
  }

  // -- footer ---------------------------------------------------------
  y += 28;
  ctx.textAlign = "left";
  ctx.fillStyle = token("--brand");
  ctx.font = `500 24px ${sans}`;
  ctx.fillText("Base & Breakout", PAD, y);

  ctx.textAlign = "right";
  ctx.fillStyle = token("--text-muted");
  ctx.font = `400 20px ${sans}`;
  ctx.fillText(`RS ${rsText(payload.rs)} · ${payload.stage.replace("_", " ")}`,
               W - PAD, y);

  y += 30;
  ctx.textAlign = "left";
  ctx.fillStyle = token("--text-disabled");
  ctx.font = `400 18px ${sans}`;
  ctx.fillText("Not investment advice. Historical figures are hypothetical.", PAD, y);

  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), "image/png"));
}
