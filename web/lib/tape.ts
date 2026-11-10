import "server-only";
import { getBreadth, getIndexes, getLeadership, getMeta, getRadar } from "./data";

/**
 * The tape: the day's few numbers, in one line under the masthead.
 *
 * Built once on the server from files the nightly already wrote. The two
 * index prices are the nightly's close here; the strip overlays the delayed
 * quote in the browser when there is one, as the index strip always did.
 */
export interface TapeItem {
  key: string;
  label: string;
  value: string;
  /** A change or a note after the value. */
  detail?: string;
  tone?: "up" | "down";
  href?: string;
  /** Set on a quoted symbol, so the browser can lay a delayed price over it. */
  symbol?: string;
  close?: number;
  changePct?: number | null;
}

export interface TapeData {
  asOf: string | null;
  universe: number | null;
  items: TapeItem[];
}

export function buildTape(): TapeData {
  const meta = getMeta();
  const items: TapeItem[] = [];
  for (const row of getIndexes()?.rows ?? []) {
    items.push({
      key: row.symbol, label: row.symbol, value: row.close.toFixed(2),
      symbol: row.symbol, close: row.close, changePct: row.change_pct,
      href: "/market/breadth",
    });
  }
  const cards = getBreadth()?.cards ?? [];
  const card = (key: string) => cards.find((c) => c.key === key)?.value ?? null;
  const pct = (v: number | null) => (v == null ? null : `${Math.round(v)}%`);
  const add = (key: string, label: string, value: string | null, extra: Partial<TapeItem> = {}) => {
    if (value != null) items.push({ key, label, value, ...extra });
  };
  const broke = card("breakouts"), failed = card("failed_pokes");
  add("breakouts", "Cleared a pivot", broke == null ? null : broke.toFixed(0),
      { href: "/market/breakouts", tone: "up" });
  add("failed", "Fell back", failed == null ? null : failed.toFixed(0),
      { href: "/market/breadth", tone: "down" });
  add("above50", "Above 50-day", pct(card("above_50ma")), { href: "/market/breadth" });
  add("uptrend", "Confirmed uptrend", pct(card("confirmed_uptrend")), { href: "/market/breadth" });

  const layers = getLeadership();
  const front = layers?.counts?.front, before = layers?.week_ago?.front;
  if (front != null) {
    const d = before == null ? null : front - before;
    add("front", "Front line", String(front), {
      href: "/market/leadership",
      detail: d == null || d === 0 ? undefined : `${d > 0 ? "▲" : "▼"} ${Math.abs(d)} wk`,
      tone: d == null || d === 0 ? undefined : d > 0 ? "up" : "down",
    });
  }
  const radar = getRadar();
  if (radar?.read?.label) add("radar", "Radar", radar.read.label, { href: "/market/radar" });

  return { asOf: meta?.as_of ?? null, universe: meta?.universe_count ?? null, items };
}
