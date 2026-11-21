import Link from "next/link";
import type { Meta, SourceReport } from "@/lib/types";

/**
 * A plain mark for a figure that is older, or thinner, than the page around it.
 *
 * The site is built each night from several sources, and on a night one of
 * them does not answer the pipeline keeps what it had rather than leaving a
 * hole. That is the right thing to do and it is invisible unless the page says
 * so: the gamma for a name carried from Tuesday sits beside Thursday's price
 * and looks exactly as fresh. This is the smallest thing that says so, a
 * boxed word in the caps face, with the reason on hover and in the text
 * beside it wherever there is room for one.
 *
 * No colour. It is not a warning that something is wrong with the number, it
 * is a statement about its date, and the page already spends colour on gain
 * and loss.
 */
export function CarriedOver({
  children = "Carried over", title,
}: {
  children?: React.ReactNode;
  title?: string;
}) {
  return <span className="carried" title={title}>{children}</span>;
}

/** `2026-11-18` as `Nov 18`. Noon UTC, so no timezone can move the day. */
export function shortDay(iso: string | null | undefined): string | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`)
    .toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** The sources that did less than a full night's work. Empty when the report
 *  is absent: no report is not the same as a bad one. */
export function sourcesShort(meta: Meta | null | undefined): SourceReport[] {
  return (meta?.sources ?? []).filter((s) => s && s.status && s.status !== "ok");
}

/**
 * For a page fed by the Market Desk, on a night the desk's last run is older
 * than the session the rest of the page shows. Renders nothing otherwise.
 */
export function DeskBehind({ meta }: { meta: Meta | null | undefined }) {
  const desk = (meta?.sources ?? []).find((s) => s.key === "desk");
  if (!desk || desk.status === "ok") return null;
  const day = shortDay(desk.as_of);
  return (
    <p className="caption" style={{ margin: "var(--gap-sm) 0 0", color: "var(--text-secondary)" }}>
      <CarriedOver title={desk.detail}>
        {desk.status === "down" ? "Not updated" : "Carried over"}
      </CarriedOver>{" "}
      {day ? <>Market Desk data from {day}.</> : <>Market Desk data is from an earlier run.</>}{" "}
      {desk.detail}{" "}
      <Link href="/colophon" style={{ textDecoration: "underline" }}>How this edition was made</Link>
    </p>
  );
}
