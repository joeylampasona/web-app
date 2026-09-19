import Link from "next/link";
import { TOTAL_TESTS, type MarketRead, type Verdict } from "@/lib/marketRead";

/**
 * The market read, with its arithmetic shown.
 *
 * The verdict is the headline, but the three tests underneath it are the point:
 * they let a reader disagree. A one-word call with nothing behind it is the
 * kind of thing that sounds authoritative on a good day and looks foolish on a
 * bad one, and this site is not in the business of sounding authoritative.
 *
 * Colour never carries the verdict on its own. "In gear" and "against" are
 * words first; the tint is a second channel for people who read the shape of a
 * page before its text, and the gain/loss greens and reds stay out of it
 * entirely because this is not price data.
 */

const TINT: Record<Verdict, { border: string; bg: string; ink: string }> = {
  in_gear: { border: "var(--brand-border)", bg: "var(--brand-muted)", ink: "var(--brand)" },
  against: { border: "var(--warn-border)", bg: "var(--warn-bg)", ink: "var(--warn)" },
  mixed:   { border: "var(--border-strong)", bg: "transparent", ink: "var(--text-secondary)" },
  unknown: { border: "var(--border)", bg: "transparent", ink: "var(--text-muted)" },
};

function Mark({ score }: { score: -1 | 0 | 1 }) {
  // A glyph as well as a word, so the column scans without relying on colour.
  const face = score === 1 ? "+" : score === -1 ? "−" : "·";
  const tone = score === 1 ? "var(--brand)"
             : score === -1 ? "var(--warn)"
             : "var(--text-muted)";
  return (
    <span
      className="mono"
      aria-hidden
      style={{
        color: tone, width: "1.1em", flexShrink: 0,
        fontSize: "var(--size-lead)", lineHeight: 1.2, textAlign: "center",
      }}
    >
      {face}
    </span>
  );
}

export function HomeRead({ read }: { read: MarketRead }) {
  const tint = TINT[read.verdict];
  return (
    <section
      className="card stack"
      style={{
        gap: "var(--gap-md)",
        borderColor: tint.border,
        background: tint.bg,
      }}
    >
      <div>
        <div className="eyebrow" style={{ color: tint.ink }}>The read</div>
        <h2 style={{ fontSize: "var(--size-h2)", margin: "var(--gap-xs) 0 0 0" }}>
          {read.headline}
        </h2>
      </div>

      <p className="muted footnote" style={{ margin: 0, maxWidth: "62ch" }}>
        {read.blurb}
      </p>

      {read.tests.length > 0 && (
        <ul
          className="stack"
          style={{ gap: "var(--gap-xs)", listStyle: "none", margin: 0, padding: 0 }}
        >
          {read.tests.map((test) => (
            <li key={test.label} className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
              <Mark score={test.score} />
              <span className="footnote" style={{ minWidth: 0 }}>
                <span style={{ color: "var(--text-primary)" }}>{test.label}.</span>{" "}
                <span className="muted">{test.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="caption dim" style={{ margin: 0 }}>
        {read.measured === TOTAL_TESTS
          ? "Four checks on the published numbers, nothing else."
          : `${read.measured} of ${TOTAL_TESTS} checks had data in the last run.`}{" "}
        <Link href="/market/breadth" style={{ textDecoration: "underline" }}>
          See the breadth page
        </Link>{" "}
        for what each one is counting.
      </p>
    </section>
  );
}
