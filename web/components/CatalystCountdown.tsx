import { longDate } from "@/lib/format";
import type { CatalystEvent } from "@/lib/types";

/**
 * The next dated event, and how long until it.
 *
 * The roadmap below this lists everything in order, which answers "what is
 * coming" but not "is anything coming *soon*" — and the second question is the
 * one that changes whether someone takes a position today. Reading it off the
 * list meant scanning for the smallest `in Nd`, which is work the page can do.
 *
 * Anything already past is skipped: a timeline is allowed to show last week's
 * earnings for context, but a countdown to a date that has gone is nonsense.
 */
const NEAR_DAYS = 7;

export function CatalystCountdown({ events }: { events: CatalystEvent[] }) {
  const upcoming = events
    .filter((event) => event.days_until >= 0)
    .sort((a, b) => a.days_until - b.days_until);
  const next = upcoming[0];
  if (!next) return null;

  const near = next.days_until <= NEAR_DAYS;
  const when = next.days_until === 0 ? "today"
    : next.days_until === 1 ? "tomorrow"
      : `in ${next.days_until} days`;
  // A tentative date is a guess from a past pattern, and a countdown renders
  // any date as if it were fixed. Saying so costs one word.
  const hedge = next.confirmed === "confirmed" ? "" :
    next.confirmed === "window" ? " (a window, not a fixed date)" : " (not yet confirmed)";

  return (
    <div
      className="row"
      style={{
        gap: "var(--gap-md)", alignItems: "center",
        padding: "var(--pad-sm) var(--pad-md)",
        border: `1px solid ${near ? "var(--brand)" : "var(--border)"}`,
        borderRadius: "var(--radius)",
        background: near ? "var(--brand-muted)" : "var(--surface-2)",
      }}
    >
      <div style={{ textAlign: "center", flexShrink: 0, minWidth: "3.2em" }}>
        <div className="num" style={{ fontSize: 22, fontWeight: 600, lineHeight: 1.1 }}>
          {next.days_until}
        </div>
        <div className="dim" style={{ fontSize: 9, letterSpacing: "0.06em",
                                      textTransform: "uppercase" }}>
          {next.days_until === 1 ? "day" : "days"}
        </div>
      </div>
      <div className="stack" style={{ gap: 2, minWidth: 0 }}>
        <div className="footnote">
          <strong>{next.type_label}</strong> {when}{hedge}
        </div>
        <div className="caption dim">
          {longDate(next.date)}
          {upcoming.length > 1 && ` · ${upcoming.length - 1} more dated below`}
        </div>
      </div>
    </div>
  );
}
