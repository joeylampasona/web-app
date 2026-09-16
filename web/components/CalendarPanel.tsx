"use client";

import { useMemo, useState } from "react";
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
 */
const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                   "Saturday", "Sunday"];

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

/** The releases filter is its own chip rather than a type inside `events`,
 *  because a data release has no ticker and everything in `events` does. */
const RELEASES = "data_releases";

export function CalendarPanel({ file, releases }: {
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
}) {
  const [monday, setMonday] = useState(() => weekStart(file.as_of));
  const [kind, setKind] = useState<string | null>(null);

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
      rows.sort((a, b) => a.type.localeCompare(b.type) || a.ticker.localeCompare(b.ticker));
    }
    return window.map((date) => ({ date, events: grouped.get(date)! }));
  }, [file.events, kind, monday]);

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

      {days.map(({ date, events }) => {
        const dayReleases = releasesByDay.get(date) ?? [];
        const dayFomc = fomcByDay.get(date) ?? [];
        const weekend = [5, 6].includes((new Date(`${date}T12:00:00`).getDay() + 6) % 7);
        if (weekend && events.length === 0 && dayReleases.length === 0
            && dayFomc.length === 0) return null;
        return (
          <section key={date} className="stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="between">
              <div className="eyebrow">
                {DAY_NAMES[(new Date(`${date}T12:00:00`).getDay() + 6) % 7]}
                {" · "}{prettyDate(date)}
              </div>
              <span className="caption dim">
                <span className="num">
                  {events.length + dayReleases.length + dayFomc.length}
                </span>
                {events.length > 0
                  && events.every((e) => e.confirmed !== "confirmed")
                  && " · all estimated"}
              </span>
            </div>
            {dayFomc.map((meeting) => (
              <div key={`fomc-${meeting.date}-${meeting.label}`}
                   style={{ padding: "var(--pad-sm) var(--pad-md)" }}>
                <div className="footnote">{meeting.label}</div>
                <div className="caption dim">
                  Federal Reserve · the decision lands at the end of this day
                </div>
              </div>
            ))}
            {dayReleases.length > 0 && (
              <div className="grid-auto" style={{ gap: "var(--gap-xs)" }}>
                {dayReleases.map((row) => (
                  // Borderless to match the ticker rows beside it: TickerLink
                  // sets border and background to none inline, so a bordered
                  // card here made a data release look heavier than an earnings
                  // date sitting on the same day. They rank the same.
                  <div key={`${row.date}-${row.release_id}-${row.name}`}
                       style={{ padding: "var(--pad-sm) var(--pad-md)" }}>
                    <div className="footnote">{row.name}</div>
                    <div className="row wrap caption dim" style={{ gap: "var(--gap-xs)" }}>
                      <span>data release</span>
                      {row.notable && <span>· widely watched</span>}
                      {row.link && (
                        <a href={row.link} target="_blank" rel="noopener noreferrer"
                           style={{ textDecoration: "underline" }}>FRED</a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {events.length === 0 && dayReleases.length === 0
              && dayFomc.length === 0 ? (
              <p className="caption dim" style={{ margin: 0 }}>Nothing dated.</p>
            ) : (
              // A busy day is three hundred rows. One column of them wastes a
              // wide screen and buries the day after it; grid-auto is already
              // auto-fill, so this is three or four across on a desktop and one
              // on a phone.
              <div className="grid-auto" style={{ gap: "var(--gap-xs)" }}>
                {events.map((event) => (
                  <TickerLink
                    key={`${event.ticker}-${event.type}-${event.date}`}
                    symbol={event.ticker}
                    className="card"
                    style={{ padding: "var(--pad-sm) var(--pad-md)", width: "100%" }}
                  >
                    <div>
                      <span className="mono">{event.ticker}</span>{" "}
                      {/* The title already says which kind of event this is —
                          "Quarterly earnings", "Ex-dividend date", "Stock split"
                          — so a type label beside it was the same word twice. */}
                      <span className="footnote">{event.title}</span>
                    </div>
                    <div className="row wrap caption dim" style={{ gap: "var(--gap-xs)" }}>
                      {/* Confirmed is the rare one — twelve of nine hundred — so
                          it is the one that gets emphasis. Marking every estimate
                          in amber put a warning on all three hundred rows of a
                          reporting week, which teaches a reader to stop seeing
                          it. The caveat is still on every row, just quietly, and
                          the count at the top of the week says it out loud. */}
                      <span style={{ color: event.confirmed === "confirmed"
                        ? "var(--text-secondary)" : undefined }}>
                        {event.confirmed === "confirmed" ? "confirmed by the company"
                          : event.confirmed === "window" ? "estimated window"
                            : "estimated"}
                      </span>
                      {event.readthrough && (
                        <span>· reads through from {event.readthrough.from}</span>
                      )}
                    </div>
                  </TickerLink>
                ))}
              </div>
            )}
          </section>
        );
      })}

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
