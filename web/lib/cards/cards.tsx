import "server-only";
import { ScreenGlyph, glyphLabel } from "@/components/ScreenGlyph";
import {
  getBarcode, getBreadth, getBreakoutDates, getBreakouts, getEarnings, getEdition,
  getFollowThrough, getIndexes, getMeta, getRadar, getScreen, getUpcoming,
} from "@/lib/data";
import { readMarket } from "@/lib/marketRead";
import type { BreadthCard } from "@/lib/types";
import { clip, closeLine, type CardCell, type FigureCard } from "./base";

/**
 * What each page's card says. Every figure is read from the published files
 * the page itself renders from, so a card cannot disagree with its page.
 *
 * Each returns null when the page has nothing to show; the route then
 * answers 404 and the link falls back to the site's own banner.
 */
const STATE: Record<string, string> = { "1": "In gear", "0": "Neither", "-1": "Against" };

/** The headline split the way the page marks it. */
function parts(text: string): { lead?: string; marked: string; tail?: string } {
  const lead = "The tape is ";
  if (text.startsWith(lead)) return { lead, marked: `${text.slice(lead.length)}.` };
  const comma = text.indexOf(",");
  if (comma > 0) return { marked: text.slice(0, comma), tail: `${text.slice(comma)}.` };
  return { marked: `${text}.` };
}

function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

function figure(card: BreadthCard): string {
  return card.unit === "percent" ? `${card.value.toFixed(0)}%` : card.value.toFixed(0);
}

function onTheWeek(card: BreadthCard): { note: string; tone: 1 | 0 | -1 } | null {
  if (card.wow_delta == null) return null;
  const delta = card.wow_delta;
  const size = Math.abs(delta) >= 10 ? Math.abs(delta).toFixed(0) : Math.abs(delta).toFixed(1);
  if (Math.abs(delta) < 0.05) return { note: "Flat on the week", tone: 0 };
  return { note: `${delta > 0 ? "+" : "−"}${size} on the week`, tone: delta > 0 ? 1 : -1 };
}

// ---------------------------------------------------------------- the read
export function readCard(): FigureCard | null {
  const meta = getMeta();
  const read = readMarket(getBreadth()?.cards, getIndexes()?.regime);
  if (!meta?.as_of || read.tests.length === 0) return null;
  const inGear = read.tests.filter((test) => test.score === 1).length;
  const strength = getRadar()?.read.label;
  return {
    dateline: closeLine(meta.as_of),
    kicker: `The read · ${inGear} of ${read.tests.length} checks in gear`
      + (strength ? ` · ${strength}` : ""),
    ...parts(read.headline),
    sub: read.blurb,
    cells: read.tests.map((test) => ({
      label: test.label, value: test.value,
      note: STATE[String(test.score)], tone: test.score,
    })),
    ticks: getBarcode()?.ticks ?? null,
    path: "/",
  };
}

export function editionCard(date: string): FigureCard | null {
  const edition = getEdition(date);
  if (!edition) return null;
  const inGear = edition.meter.filter((cell) => cell.score === 1).length;
  return {
    dateline: closeLine(edition.date),
    kicker: `Back issue · ${inGear} of ${edition.meter.length} checks in gear`
      + (edition.radar?.label ? ` · ${edition.radar.label}` : ""),
    ...parts(edition.headline),
    sub: edition.blurb,
    cells: edition.meter.map((cell) => ({
      label: cell.label, value: cell.value,
      note: STATE[String(cell.score)], tone: cell.score,
    })),
    tenths: edition.tenths ?? null,
    path: `/market/editions/${edition.date}`,
  };
}

// ---------------------------------------------------------------- a screen
export function screenCard(key: string): FigureCard | null {
  const screen = getScreen(key);
  if (!screen) return null;
  const order = Object.keys(screen.stage_labels ?? screen.stage_counts ?? {});
  const cells: CardCell[] = order.slice(0, 4).map((stage) => ({
    label: screen.stage_labels?.[stage] ?? stage.replace(/_/g, " "),
    value: String(screen.stage_counts?.[stage] ?? 0),
    note: screen.stage_help?.[stage] ?? null,
    marked: stage === "fresh_breakout",
  }));
  const href = `/screens/${key}`;
  return {
    dateline: closeLine(screen.as_of),
    kicker: `Screen · ${screen.direction === "short" ? "reads down" : "reads up"}`
      + ` · ${screen.total} ${plural(screen.total, "name", "names")} tonight`,
    marked: screen.name,
    sub: glyphLabel(href)
      ? `${glyphLabel(href)}. ${clip(screen.description, 110)}`
      : screen.description,
    cells,
    art: <ScreenGlyph href={href} size={200} />,
    path: href,
  };
}

// ---------------------------------------------------------------- breakouts
export function breakoutsCard(): FigureCard | null {
  const meta = getMeta();
  const latest = getBreakoutDates().slice(-1)[0];
  const file = latest ? getBreakouts(latest) : null;
  if (!meta?.as_of) return null;
  const count = file?.count ?? 0;
  // By screen from the run's own totals, which are whole. The page's list is
  // the free sample, and a bar built from it would be a bar of the paywall.
  const bars = (meta.screens ?? [])
    .map((screen) => ({ label: screen.name, value: screen.stages?.fresh_breakout ?? 0 }))
    .filter((bar) => bar.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
  const top = bars[0]?.value ?? 0;
  return {
    dateline: closeLine(latest ?? meta.as_of),
    kicker: "All breakouts today",
    ...(count > 0
      ? { marked: String(count),
          tail: ` ${plural(count, "name", "names")} cleared a pivot.` }
      : { marked: "Nothing", tail: " broke out today." }),
    sub: count > 0
      ? "Closed above the level each base was resting under. By screen, still inside the buy window:"
      : "No name closed above its pivot. That is a reading of the day, not a fault.",
    bars: bars.map((bar) => ({ ...bar, marked: bar.value === top })),
    path: "/market/breakouts",
  };
}

export function followCard(): FigureCard | null {
  const file = getFollowThrough();
  const rows = Object.values(file?.screens ?? {}).filter((row) => row.settled > 0);
  if (!file || rows.length === 0) return null;
  const settled = rows.reduce((sum, row) => sum + row.settled, 0);
  const up = rows.reduce((sum, row) => sum + row.up, 0);
  const cells: CardCell[] = [...rows]
    .sort((a, b) => b.settled - a.settled)
    .slice(0, 4)
    .map((row) => ({
      label: row.name,
      value: `${Math.round(100 * row.up / row.settled)}%`,
      note: `${row.up} of ${row.settled} above`,
      tone: row.up * 2 >= row.settled ? 1 : -1,
    }));
  return {
    dateline: closeLine(file.as_of),
    kicker: `Did it work? · breakouts of the last ${file.window_days} days`,
    marked: `${up} of ${settled}`,
    tail: " are above where they broke out.",
    sub: "Every breakout the screens flagged, followed afterwards. The four most active screens:",
    cells,
    path: "/market/followthrough",
  };
}

// ---------------------------------------------------------------- the week
export function calendarCard(): FigureCard | null {
  const upcoming = getUpcoming();
  const asOf = upcoming?.as_of ?? getMeta()?.as_of;
  if (!asOf) return null;
  // The next five weekdays after the session, as the home page counts them.
  const days: string[] = [];
  const cursor = new Date(`${asOf}T12:00:00Z`);
  while (days.length < 5) {
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    const weekday = cursor.getUTCDay();
    if (weekday !== 0 && weekday !== 6) days.push(cursor.toISOString().slice(0, 10));
  }
  const counts = new Map<string, number>(days.map((day) => [day, 0]));
  for (const event of upcoming?.events ?? []) {
    if (event.type !== "earnings" || event.readthrough) continue;
    if (counts.has(event.date)) counts.set(event.date, (counts.get(event.date) ?? 0) + 1);
  }
  const total = [...counts.values()].reduce((sum, n) => sum + n, 0);
  const busiest = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  const name = (iso: string, style: "short" | "long") =>
    new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { weekday: style, timeZone: "UTC" });
  return {
    dateline: closeLine(asOf),
    kicker: "The calendar · the week ahead",
    ...(total > 0
      ? { marked: String(total),
          tail: ` ${plural(total, "company reports", "companies report")} this week.` }
      : { marked: "A quiet week", tail: " for earnings." }),
    sub: total > 0 && busiest
      ? `Companies in the universe reporting each day. ${name(busiest[0], "long")} is the busiest, with ${busiest[1]}.`
      : "No company in the universe has a dated report in the next five sessions.",
    bars: days.map((day) => ({
      label: `${name(day, "short")} ${Number(day.slice(8))}`,
      value: counts.get(day) ?? 0,
      marked: total > 0 && day === busiest?.[0],
    })),
    path: "/market/calendar",
  };
}

// ---------------------------------------------------------------- breadth
export function breadthCard(): FigureCard | null {
  const breadth = getBreadth();
  const cards = breadth?.cards ?? [];
  const lead = cards.find((card) => card.key === "above_50ma");
  if (!breadth || !lead) return null;
  const wanted = ["above_200ma", "confirmed_uptrend", "near_52w_highs", "near_52w_lows"];
  const cells: CardCell[] = wanted
    .map((key) => cards.find((card) => card.key === key))
    .filter((card): card is BreadthCard => Boolean(card))
    .map((card) => ({ label: card.label, value: figure(card), ...(onTheWeek(card) ?? {}) }));
  const week = onTheWeek(lead);
  return {
    dateline: closeLine(breadth.as_of),
    kicker: `Breadth · ${breadth.universe_size.toLocaleString("en-US")} names`,
    marked: figure(lead),
    tail: " are above their 50-day line.",
    sub: `${week ? `${week.note}. ` : ""}Below, every ranked stock strongest first: `
      + "tall bars are above both moving averages, short ones under both.",
    cells,
    ticks: getBarcode()?.ticks ?? null,
    path: "/market/breadth",
  };
}

// ---------------------------------------------------------------- earnings
export function earningsCard(): FigureCard | null {
  const file = getEarnings();
  if (!file) return null;
  const reads = file.reads ?? [];
  const cells: CardCell[] = reads.slice(0, 4).map((read) => ({
    label: read.symbol,
    value: read.symbol,
    note: clip(read.name, 28),
  }));
  return {
    dateline: closeLine(file.as_of),
    kicker: `Earnings · reports of the last ${file.read_days} days`,
    ...(reads.length > 0
      ? { marked: String(reads.length),
          tail: ` ${plural(reads.length, "report", "reports")} read against the numbers.` }
      : { marked: "No reports", tail: " read tonight." }),
    sub: "What each quarter's figures say, what is not obvious in them, and what the stock did next.",
    cells: cells.map((cell) => ({ ...cell, label: "Read" })),
    path: "/market/earnings",
  };
}

/** The fixed cards by the name their address uses. */
export const PAGE_CARDS: Record<string, () => FigureCard | null> = {
  read: readCard,
  breakouts: breakoutsCard,
  followthrough: followCard,
  calendar: calendarCard,
  breadth: breadthCard,
  earnings: earningsCard,
};
