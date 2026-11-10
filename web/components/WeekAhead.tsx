import Link from "next/link";
import type { CatalystEvent, DataRelease, FomcMeeting } from "@/lib/types";
import { TickerLink } from "./StockDrawer";

/**
 * The week ahead as a bar per day.
 *
 * How many companies report each day is the shape of the week, and a list of
 * tickers could not show it: a Thursday with 156 reports and a Friday with
 * nine read the same. The bar is the count; over it, the scheduled data that
 * moves the whole market that day; under it, the reports the options price
 * for the biggest moves, or failing that the first few names.
 *
 * Counted from the last settled session, not the reader's clock, like every
 * date on this site.
 */
const DAYS = 5;
const NAMES = 3;

/** A release's name as a flag: short enough for a column a fifth of a card. */
const FLAGS: [RegExp, string][] = [
  [/fomc/i, "FOMC"], [/consumer price/i, "CPI"], [/producer price/i, "PPI"],
  [/employment situation|nonfarm/i, "JOBS"], [/retail/i, "RETAIL"],
  [/gross domestic|national accounts|\bgdp\b(?!now)/i, "GDP"],
  [/personal income|pce/i, "PCE"], [/unemployment insurance/i, "CLAIMS"],
  [/industrial production/i, "OUTPUT"],
];

function flagsFor(releases: DataRelease[], fomc: boolean): string[] {
  const out: string[] = fomc ? ["FOMC"] : [];
  for (const release of releases) {
    const hit = FLAGS.find(([rx]) => rx.test(release.name));
    if (hit && !out.includes(hit[1])) out.push(hit[1]);
  }
  return out.slice(0, 2);
}

interface Day {
  date: string;
  reports: CatalystEvent[];
  dividends: number;
  flags: string[];
}

function dayLabel(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`);
  return `${d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })} ${d.getUTCDate()}`;
}

export function WeekAhead({ events, releases, fomc, pricedHeld }: {
  events: CatalystEvent[];
  releases: DataRelease[];
  fomc: FomcMeeting[];
  /** How often the priced move has held, when the desk has scored enough. */
  pricedHeld?: { n: number; inside_pct: number } | null;
}) {
  const byDate = new Map<string, Day>();
  const day = (date: string) => {
    let found = byDate.get(date);
    if (!found) { found = { date, reports: [], dividends: 0, flags: [] }; byDate.set(date, found); }
    return found;
  };
  for (const event of events) {
    if (event.days_until < 0 || event.days_until > 9) continue;
    if (event.type === "earnings" && !event.readthrough) {
      const into = day(event.date);
      if (!into.reports.some((e) => e.ticker === event.ticker)) into.reports.push(event);
    } else if (event.type === "dividend_ex_date") {
      day(event.date).dividends += 1;
    }
  }
  const notable = releases.filter((r) => r.notable && r.days_until >= 0 && r.days_until <= 9);
  const days = [...byDate.values()]
    // Weekdays with something on them; a "report" dated a Saturday is a
    // filing date, not a session.
    .filter((d) => { const wd = new Date(`${d.date}T12:00:00Z`).getUTCDay(); return wd >= 1 && wd <= 5; })
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, DAYS);
  for (const d of days) {
    d.flags = flagsFor(notable.filter((r) => r.date === d.date),
                       fomc.some((m) => m.date === d.date));
  }
  if (!days.length) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        Nothing dated in the days ahead for the names this site follows. A quiet
        week is a quiet week.
      </p>
    );
  }
  const max = Math.max(...days.map((d) => d.reports.length), 1);
  const anyPriced = days.some((d) => d.reports.some((e) => e.priced_move_pct));

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="weekbars">
        {days.map((d) => {
          const priced = d.reports.filter((e) => e.priced_move_pct)
            .sort((a, b) => (b.priced_move_pct ?? 0) - (a.priced_move_pct ?? 0));
          const shown = (priced.length ? priced : d.reports).slice(0, NAMES);
          return (
            <div key={d.date} className="weekbar-col">
              <div className="weekbar-plot" role="img"
                   aria-label={`${dayLabel(d.date)}: ${d.reports.length} reports`}>
                <div className="num" style={{ fontWeight: 600, paddingBottom: 3 }}>
                  {d.reports.length}
                </div>
                <div className="bar" style={{ height: `${(d.reports.length / max) * 78}%` }} />
              </div>
              <div className="label-caps">{dayLabel(d.date)}</div>
              <div className="row wrap" style={{ gap: 4, minHeight: 20 }}>
                {d.flags.map((f) => <span key={f} className="weekbar-flag">{f}</span>)}
              </div>
              {shown.map((e) => (
                <TickerLink key={e.ticker} symbol={e.ticker} className="weekbar-name">
                  <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>{e.ticker}</span>
                  {e.priced_move_pct ? (
                    <span className="mono caption dim">±{e.priced_move_pct.toFixed(1)}%</span>
                  ) : null}
                </TickerLink>
              ))}
              {d.dividends > 0 && (
                <div className="caption dim">{d.dividends} ex-div</div>
              )}
            </div>
          );
        })}
      </div>
      <p className="footnote" style={{ margin: 0, color: "var(--text-secondary)" }}>
        Companies reporting each day{anyPriced && <>, with the moves the options price into the
        biggest</>}.
        {anyPriced && pricedHeld && (
          <> Across the last {pricedHeld.n} reports read, the actual move stayed inside the priced
            one <span className="num hl" style={{ fontWeight: 600 }}>{pricedHeld.inside_pct}%</span> of
            the time.</>
        )}{" "}
        <Link href="/market/calendar" style={{ textDecoration: "underline" }}>Full calendar</Link>
        {" · "}
        <Link href="/market/earnings" style={{ textDecoration: "underline" }}>Earnings</Link>
      </p>
    </div>
  );
}
