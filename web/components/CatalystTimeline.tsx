"use client";

import { useState } from "react";
import { longDate } from "@/lib/format";
import type { CatalystEvent } from "@/lib/types";

const CONFIRM_LABEL: Record<string, string> = {
  confirmed: "confirmed", tentative: "tentative", window: "window",
};

function calendarHref(event: CatalystEvent): string {
  const date = event.date.replace(/-/g, "");
  const next = new Date(`${event.date}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  const end = next.toISOString().slice(0, 10).replace(/-/g, "");
  const title = encodeURIComponent(`${event.ticker} — ${event.title || event.type_label}`);
  const details = encodeURIComponent(event.details || "");
  return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}` +
    `&dates=${date}/${end}&details=${details}`;
}

export function CatalystTimeline({ events }: { events: CatalystEvent[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (events.length === 0) {
    return (
      <p className="muted footnote">
        Nothing dated in the next three months that we can ingest automatically.
      </p>
    );
  }
  return (
    <ol className="stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {events.map((event, index) => (
        <li key={`${event.type}-${event.date}-${index}`} className="card stack"
            style={{ gap: "var(--gap-sm)", borderLeft: "2px solid var(--border-strong)" }}>
          <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
            <span className="badge">{event.type_label}</span>
            <span className="badge">{CONFIRM_LABEL[event.confirmed] ?? event.confirmed}</span>
            {event.readthrough && (
              <span className="badge badge--warn">
                {event.readthrough.from} · {event.readthrough.tag}
              </span>
            )}
            <span className="grow" />
            <span className="num caption dim">
              {event.days_until >= 0 ? `in ${event.days_until}d` : `${-event.days_until}d ago`}
            </span>
          </div>
          <div>
            <div>{event.title || event.type_label}</div>
            <div className="caption dim">{longDate(event.date)}</div>
          </div>
          <div className="row" style={{ gap: "var(--gap-sm)" }}>
            <button type="button" className="control footnote" style={{ minHeight: 36 }}
                    onClick={() => setOpen(open === index ? null : index)}
                    aria-expanded={open === index}>
              Details
            </button>
            <a className="control footnote" style={{ minHeight: 36 }}
               href={calendarHref(event)} target="_blank" rel="noreferrer">
              Add to calendar
            </a>
          </div>
          {open === index && (
            <p className="footnote muted" style={{ margin: 0 }}>
              {event.details || "No further detail is published for this event."}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
