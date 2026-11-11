"use client";

import { useMemo, useState } from "react";
import { useWatchlist } from "@/lib/useWatchlist";
import { TickerLink } from "./StockDrawer";
import type { CatalystEvent, DataRelease, FomcMeeting, FomcStatus } from "@/lib/types";

/**
 * Every dated event the scan knows about, a week at a time.
 *
 * The same events that badge a stock's page, gathered into one place and grouped
 * by the day they fall on. Nothing here is new data — it is catalysts/upcoming
 * .json, which the nightly has been writing all along and nothing was reading.
 *
 * Two things this page has to be honest about, because a calendar implies a
 * precision it does not have:
 *
 *   - Most earnings dates are estimates. Of the 909 in tonight's file, 12 are
 *     company-confirmed and the rest are projections from the last few years of
 *     reporting. A date you can set a watch by and a date somebody guessed must
 *     not look the same, so each row says which it is.
 *   - A quiet week is usually a quiet week. Mid-September carries almost nothing
 *     because Q3 reporting does not start until mid-October; an empty day here
 *     is the calendar, not a gap in it. The empty state says so rather than
 *     leaving a reader to assume the page is broken.
 *
 * The week is drawn as the week: five columns, Monday to Friday, a chip per
 * name. It used to be a card per event, three hundred identical cards on a
 * reporting day, each repeating "Quarterly earnings" under a ticker. A column
 * of chips shows which day is the heavy one at a glance, and puts the names a
 * reader is most likely to care about first: strongest by relative strength,
 * with the ones already on a screen marked in lime and the reader's own
 * watchlist starred.
 */
const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                   "Saturday", "Sunday"];
/** Chips a day shows before the rest fold behind a button. A reporting day
 *  runs past three hundred names; the strongest forty are the column. */
const DAY_SHOWN = 40;
/** A peer's report is context, not the name's own event, so it gets less room. */
const PEERS_SHOWN = 12;

/** What the page knows about a ticker beyond its event: [RS rating, how many
 *  screens it is on tonight]. Passed as a tuple to keep the payload small. */
export type CalendarNames = Record<string, [number | null, number]>;

/** Monday of the week containing `iso`. Weeks start Monday because the market
 *  does; a Sunday-first week would split the trading week across two screens. */
function weekStart(iso: string): string {
  const date = new Date(`${iso}T12:00:00`);
  const shift = (date.getDay() + 6) % 7;          // Sunday is 0; Monday leads
  date.setDate(date.getDate() - shift);
  return date.toISOString().slice(0, 10);
}

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function prettyDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
    day: "numeric", month: "long",
  });
}

/** A day's events by kind, a company's own first. A read-through is a peer's
 *  report, so it sits in its own group below the names actually reporting. */
function groupEvents(events: CatalystEvent[], labels: Record<string, string>) {
  const groups = new Map<string, { key: string; label: string; rows: CatalystEvent[] }>();
  for (const event of events) {
    const key = event.readthrough ? "readthrough" : event.type;
    if (!groups.has(key)) {
      groups.set(key, { key, rows: [],
        label: event.readthrough ? "A peer reports" : labels[event.type] ?? event.type });
    }
    groups.get(key)!.rows.push(event);
  }
  const order = (key: string) => (key === "earnings" ? 0 : key === "readthrough" ? 9 : 1);
  return [...groups.values()].sort((a, b) => order(a.key) - order(b.key) || a.label.localeCompare(b.label));
}

/** The releases filter is its own chip rather than a type inside `events`,
 *  because a data release has no ticker and everything in `events` does. */
const RELEASES = "data_releases";

export function CalendarPanel({ file, releases, names }: {
  file: {
    as_of: string; count: number;
    events: CatalystEvent[];
    type_labels: Record<string, string>;
  };
  releases?: {
    as_of: string; configured: boolean; count: number; source: string;
    releases: DataRelease[];
    fomc?: FomcStatus;
  } | null;
  names?: CalendarNames;
}) {
  const [monday, setMonday] = useState(() => weekStart(file.as_of));
  const [kind, setKind] = useState<string | null>(null);
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const { symbols } = useWatchlist();
  const mine = useMemo(() => new Set(symbols), [symbols]);
  const rs = (ticker: string): number => names?.[ticker]?.[0] ?? -1;

  // Which types actually appear, so the filters never offer an empty one.
  const kinds = useMemo(() => {
    const seen = new Map<string, number>();
    for (const event of file.events) {
      seen.set(event.type, (seen.get(event.type) ?? 0) + 1);
    }
    const rows = [...seen.entries()].sort((a, b) => b[1] - a[1]);
    if (releases?.releases.length) rows.push([RELEASES, releases.releases.length]);
    return rows;
  }, [file.events, releases]);

  const releasesByDay = useMemo(() => {
    const grouped = new Map<string, DataRelease[]>();
    if (kind && kind !== RELEASES) return grouped;
    for (const row of releases?.releases ?? []) {
      if (!grouped.has(row.date)) grouped.set(row.date, []);
      grouped.get(row.date)!.push(row);
    }
    return grouped;
  }, [kind, releases]);

  // FOMC sits with the releases: both are market-wide and neither has a ticker.
  const fomcByDay = useMemo(() => {
    const grouped = new Map<string, FomcMeeting[]>();
    if (kind && kind !== RELEASES) return grouped;
    for (const row of releases?.fomc?.meetings ?? []) {
      if (!grouped.has(row.date)) grouped.set(row.date, []);
      grouped.get(row.date)!.push(row);
    }
    return grouped;
  }, [kind, releases]);

  const days = useMemo(() => {
    const window = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
    const within = new Set(window);
    const grouped = new Map<string, CatalystEvent[]>(window.map((d) => [d, []]));
    for (const event of file.events) {
      if (!within.has(event.date)) continue;
      if (kind && event.type !== kind) continue;   // RELEASES excludes them all
      grouped.get(event.date)!.push(event);
    }
    for (const rows of grouped.values()) {
      // The reader's own names, then strongest first. Alphabetical order put
      // a reporting day's most followed name wherever its letter fell.
      rows.sort((a, b) => Number(mine.has(b.ticker)) - Number(mine.has(a.ticker))
        || rs(b.ticker) - rs(a.ticker) || a.ticker.localeCompare(b.ticker));
    }
    return window.map((date) => ({ date, events: grouped.get(date)! }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file.events, kind, monday, mine, names]);

  const busiest = Math.max(1, ...days.map((d) => d.events.length
    + (releasesByDay.get(d.date)?.length ?? 0) + (fomcByDay.get(d.date)?.length ?? 0)));
  const releasesShown = days.reduce(
    (n, d) => n + (releasesByDay.get(d.date)?.length ?? 0)
      + (fomcByDay.get(d.date)?.length ?? 0), 0);
  const shown = days.reduce((n, d) => n + d.events.length, 0) + releasesShown;
  const estimates = days.reduce(
    (n, d) => n + d.events.filter((e) => e.confirmed !== "confirmed").length, 0);
  // Events are only ever written forward from the scan, so a week before it is
  // empty for a reason that has nothing to do with the market.
  const beforeScan = addDays(monday, 6) < file.as_of;

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        <button type="button" className="control footnote"
                onClick={() => setMonday(addDays(monday, -7))}>← Earlier</button>
        <button type="button" className="control footnote"
                onClick={() => setMonday(weekStart(file.as_of))}>This week</button>
        <button type="button" className="control footnote"
                onClick={() => setMonday(addDays(monday, 7))}>Later →</button>
        <span className="grow" />
        <label className="row footnote dim" style={{ gap: "var(--gap-xs)" }}>
          <span className="visually-hidden">Jump to a date</span>
          <input
            type="date"
            className="control"
            value={monday}
            onChange={(event) => {
              if (event.target.value) setMonday(weekStart(event.target.value));
            }}
            style={{ background: "var(--surface-2)", minHeight: "var(--h-control)" }}
          />
        </label>
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
        <button type="button" className="control footnote"
                style={{ borderRadius: "var(--radius-pill)" }}
                aria-pressed={kind === null} onClick={() => setKind(null)}>
          Everything
        </button>
        {kinds.map(([type, total]) => (
          <button
            key={type}
            type="button"
            className="control footnote"
            style={{ borderRadius: "var(--radius-pill)" }}
            aria-pressed={kind === type}
            onClick={() => setKind(kind === type ? null : type)}
          >
            {type === RELEASES ? "Data releases" : file.type_labels[type] ?? type}{" "}
            <span className="num dim">{total}</span>
          </button>
        ))}
      </div>

      <div className="footnote muted">
        Week of {prettyDate(monday)} — {shown === 0 ? "nothing scheduled" : `${shown} dated`}
        {shown > 0 && estimates > 0 && (
          <>
            {", "}
            <span>{estimates} of them estimated rather than confirmed</span>
          </>
        )}
        .
      </div>

      {releases?.fomc?.stale && (
        <p className="caption" style={{ margin: 0, color: "var(--warn)" }}>
          {releases.fomc.message}
        </p>
      )}
      {releases?.fomc && !releases.fomc.stale && releases.fomc.checked_on && (
        <p className="caption dim" style={{ margin: 0 }}>
          FOMC dates are kept by hand from the Federal Reserve&rsquo;s published
          schedule, last checked {releases.fomc.checked_on}.
        </p>
      )}
      {releases && !releases.configured && (
        <p className="caption dim" style={{ margin: 0 }}>
          Economic data releases are not switched on for this build, so only
          company events are shown.
        </p>
      )}

      {shown > 0 && (
        <>
          <div className="week-grid">
            {days.map(({ date, events }) => {
              const dayReleases = releasesByDay.get(date) ?? [];
              const dayFomc = fomcByDay.get(date) ?? [];
              const index = (new Date(`${date}T12:00:00`).getDay() + 6) % 7;
              const total = events.length + dayReleases.length + dayFomc.length;
              if (index > 4 && total === 0) return null;
              const groups = groupEvents(events, file.type_labels);
              return (
                <section key={date} className="week-day"
                         data-today={date === file.as_of || undefined}>
                  <header className="week-day-head">
                    <div className="between" style={{ alignItems: "baseline" }}>
                      <span className="label-caps">{DAY_NAMES[index]}</span>
                      <span className="num week-day-count">{total}</span>
                    </div>
                    <div className="caption dim">{prettyDate(date)}</div>
                    <div className="week-day-bar" aria-hidden>
                      <span style={{ width: `${(total / busiest) * 100}%` }} />
                    </div>
                  </header>

                  {dayFomc.map((meeting) => (
                    <div key={`fomc-${meeting.date}-${meeting.label}`} className="week-note">
                      <span className="hl" style={{ fontWeight: 600 }}>{meeting.label}</span>
                      <div className="caption dim">Federal Reserve · decision at the end of this day</div>
                    </div>
                  ))}
                  {dayReleases.map((row) => (
                    <div key={`${row.date}-${row.release_id}-${row.name}`} className="week-note">
                      {row.link
                        ? <a href={row.link} target="_blank" rel="noopener noreferrer">{row.name}</a>
                        : row.name}
                      <div className="caption dim">
                        Data release{row.notable && " · widely watched"}
                      </div>
                    </div>
                  ))}

                  {total === 0 && <p className="caption dim" style={{ margin: 0 }}>Nothing dated.</p>}

                  {groups.map((group) => {
                    const key = `${date}:${group.key}`;
                    const all = open.has(key);
                    const cap = group.key === "readthrough" ? PEERS_SHOWN : DAY_SHOWN;
                    const rows = all ? group.rows : group.rows.slice(0, cap);
                    const estimated = group.rows.filter((e) => e.confirmed !== "confirmed").length;
                    return (
                      <div key={group.key} className="stack" style={{ gap: 6 }}>
                        <div className="caption dim between">
                          <span>{group.label}</span>
                          <span className="num" title={estimated
                            ? `${estimated} of ${group.rows.length} are estimated dates` : undefined}>
                            {group.rows.length}
                          </span>
                        </div>
                        <div className="week-chips">
                          {rows.map((event) => {
                            const rating = names?.[event.ticker]?.[0];
                            const screens = names?.[event.ticker]?.[1] ?? 0;
                            const firm = event.confirmed === "confirmed";
                            return (
                              <TickerLink
                                key={`${event.ticker}-${event.type}-${event.readthrough?.from ?? "own"}`}
                                symbol={event.ticker}
                                className={`week-chip${firm ? "" : " week-chip--est"}${screens ? " week-chip--screen" : ""}`}
                                title={[
                                  event.title,
                                  firm ? "confirmed by the company"
                                    : event.confirmed === "window" ? "estimated window" : "estimated date",
                                  event.readthrough ? `reads through from ${event.readthrough.from}` : null,
                                  rating != null ? `RS ${rating}` : null,
                                  screens ? `on ${screens} screen${screens === 1 ? "" : "s"} tonight` : null,
                                  event.priced_move_pct != null
                                    ? `options price ±${event.priced_move_pct.toFixed(1)}%` : null,
                                ].filter(Boolean).join(" · ")}
                              >
                                {mine.has(event.ticker) && <span aria-label="on your watchlist">★ </span>}
                                <span className="mono" style={{ fontWeight: 600 }}>{event.ticker}</span>
                                {rating != null && <span className="num week-chip-rs">{rating}</span>}
                                {event.priced_move_pct != null && (
                                  <span className="num week-chip-move">±{event.priced_move_pct.toFixed(0)}%</span>
                                )}
                              </TickerLink>
                            );
                          })}
                        </div>
                        {group.rows.length > cap && (
                          <button type="button" className="week-more"
                                  onClick={() => setOpen((prev) => {
                                    const next = new Set(prev);
                                    if (all) next.delete(key); else next.add(key);
                                    return next;
                                  })}>
                            {all ? "Show the strongest only"
                              : `${group.rows.length - cap} more, in order of strength`}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </section>
              );
            })}
          </div>
          <div className="row wrap caption dim" style={{ gap: "6px var(--gap-lg)" }}>
            <span><span className="week-chip week-chip--screen" style={{ pointerEvents: "none" }}>
              <span className="mono" style={{ fontWeight: 600 }}>ABC</span></span> on a screen tonight</span>
            <span><span className="week-chip" style={{ pointerEvents: "none" }}>
              <span className="mono" style={{ fontWeight: 600 }}>ABC</span></span> date confirmed by the company</span>
            <span><span className="week-chip week-chip--est" style={{ pointerEvents: "none" }}>
              <span className="mono" style={{ fontWeight: 600 }}>ABC</span></span> estimated date</span>
            <span>The small figure is the RS rating; names run strongest first, your watchlist ahead of them.</span>
          </div>
        </>
      )}

      {shown === 0 && (
        <div className="card muted footnote">
          {beforeScan
            ? `Nothing here: the scan only writes events forward from the day it ran, `
              + `and this week ended before ${file.as_of}.`
            : "Nothing dated this week. Reporting season runs in waves — the weeks "
              + "either side of a season carry almost nothing, so an empty week here "
              + "is usually the calendar rather than a gap in it. Try Later."}
        </div>
      )}
    </div>
  );
}
