import Link from "next/link";
import type { CatalystEvent, DataRelease, FomcMeeting } from "@/lib/types";
import { TickerLink } from "./StockDrawer";
import { weekday, longDate } from "@/lib/format";

/**
 * What is dated in the days just ahead.
 *
 * Everything here is measured from the last settled session, not from the
 * reader's clock. The site is published after a close and the browser may be
 * opening it a day or two later, so "today" would be a lie roughly as often as
 * it was true. Dates are written out instead, and the header says what they are
 * counted from. A date is the one thing on this page that cannot be fudged.
 *
 * A day with nothing on it is left out rather than rendered empty, but a window
 * with nothing in it at all says so plainly — a quiet week is a fact about the
 * calendar, not a hole in the page.
 */

const DAYS_AHEAD = 7;
const TICKERS_PER_DAY = 10;

interface DayGroup {
  date: string;
  earnings: CatalystEvent[];
  dividends: CatalystEvent[];
  splits: CatalystEvent[];
  other: CatalystEvent[];
  releases: DataRelease[];
  fomc: FomcMeeting | null;
}

function groupByDay(
  events: CatalystEvent[],
  releases: DataRelease[],
  fomc: FomcMeeting[],
): DayGroup[] {
  const days = new Map<string, DayGroup>();
  const day = (date: string): DayGroup => {
    let found = days.get(date);
    if (!found) {
      found = { date, earnings: [], dividends: [], splits: [], other: [], releases: [], fomc: null };
      days.set(date, found);
    }
    return found;
  };

  for (const event of events) {
    if (event.days_until < 0 || event.days_until > DAYS_AHEAD) continue;
    const into = day(event.date);
    if (event.type === "earnings") into.earnings.push(event);
    else if (event.type === "dividend_ex_date") into.dividends.push(event);
    else if (event.type === "split") into.splits.push(event);
    else into.other.push(event);
  }
  // Only the releases the pipeline marked notable. The full FRED list runs to
  // dozens of technical series a week and would bury the earnings.
  for (const release of releases) {
    if (!release.notable) continue;
    if (release.days_until < 0 || release.days_until > DAYS_AHEAD) continue;
    day(release.date).releases.push(release);
  }
  for (const meeting of fomc) {
    if (meeting.days_until < 0 || meeting.days_until > DAYS_AHEAD) continue;
    day(meeting.date).fomc = meeting;
  }

  return [...days.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function Tickers({ events }: { events: CatalystEvent[] }) {
  const shown = events.slice(0, TICKERS_PER_DAY);
  const rest = events.length - shown.length;
  return (
    <span className="wrap" style={{ display: "inline" }}>
      {shown.map((event, index) => (
        <span key={event.ticker + event.type}>
          <TickerLink symbol={event.ticker} className="mono">{event.ticker}</TickerLink>
          {index < shown.length - 1 ? ", " : ""}
        </span>
      ))}
      {rest > 0 && <span className="dim"> +{rest} more</span>}
    </span>
  );
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="footnote" style={{ minWidth: 0 }}>
      <span className="muted">{label} </span>
      {children}
    </div>
  );
}

export function HomeCalendar({
  events, releases, fomc, asOf,
}: {
  events: CatalystEvent[];
  releases: DataRelease[];
  fomc: FomcMeeting[];
  asOf: string | null;
}) {
  const days = groupByDay(events, releases, fomc);

  return (
    <section className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
        <div>
          <div className="eyebrow">Dated next</div>
          <h2 style={{ fontSize: "var(--size-h3)", margin: "var(--gap-xs) 0 0 0" }}>
            The {DAYS_AHEAD} days after the {longDate(asOf)} close
          </h2>
        </div>
        {/* Without nowrap this breaks to "Full / calendar" at phone width. */}
        <Link href="/market/calendar" className="footnote"
              style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
          Full calendar
        </Link>
      </div>

      {days.length === 0 ? (
        <p className="muted footnote" style={{ margin: 0 }}>
          Nothing dated in the next {DAYS_AHEAD} days for the names this site follows.
          A quiet week is a quiet week.
        </p>
      ) : (
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          {days.map((day) => (
            <div key={day.date} className="card stack" style={{ gap: "var(--gap-xs)" }}>
              <div className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
                {/* weekday() already reads "Wed, Sep 16" -- printing shortDate
                    beside it repeated the date in a second format. */}
                <span style={{ fontWeight: 500 }}>{weekday(day.date)}</span>
                {day.fomc && (
                  <span className="badge badge--brand">FOMC</span>
                )}
              </div>

              {day.fomc && (
                <div className="footnote" style={{ color: "var(--brand)" }}>
                  {day.fomc.label}
                </div>
              )}
              {day.earnings.length > 0 && (
                <Line label={`Earnings (${day.earnings.length})`}>
                  <Tickers events={day.earnings} />
                </Line>
              )}
              {day.dividends.length > 0 && (
                <Line label={`Ex-dividend (${day.dividends.length})`}>
                  <Tickers events={day.dividends} />
                </Line>
              )}
              {day.splits.length > 0 && (
                <Line label={`Splits (${day.splits.length})`}>
                  <Tickers events={day.splits} />
                </Line>
              )}
              {day.other.length > 0 && (
                <Line label={`${day.other[0].type_label} (${day.other.length})`}>
                  <Tickers events={day.other} />
                </Line>
              )}
              {day.releases.length > 0 && (
                <Line label="Data">
                  <span>{day.releases.map((r) => r.name).join(" · ")}</span>
                </Line>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
