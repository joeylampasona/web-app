import Link from "next/link";
import { TOTAL_TESTS, type MarketRead } from "@/lib/marketRead";
import type { IndexRow } from "@/lib/types";
import { PriceChange } from "./PriceChange";
import { price } from "@/lib/format";

/**
 * The hero: the market read, with its arithmetic shown, on a dark slab.
 *
 * The slab is near-black in both themes. That is the one structural idea taken
 * from the reference designs -- a dark card at the top of a pale page -- and it
 * earns its place here for a reason beyond looks: the verdict is the largest
 * claim this site makes, and putting it on its own surface stops it being read
 * as just another statistic in the stack below.
 *
 * The three tests underneath are the point. They let a reader disagree. A
 * one-word call with nothing behind it is a horoscope, and the failure mode of
 * a big confident hero card is exactly that, so the evidence stays attached to
 * it rather than being tidied away onto another page.
 *
 * Colour never carries the verdict alone. "In gear" and "against" are words
 * first; the chip and the tint are a second channel, and the gain/loss greens
 * and reds stay out of it because this is not price data.
 */

/* The chip carries the session, not the verdict.
 *
 * It said the verdict first, which put "MIXED" in a pill directly above a
 * headline reading "Mixed" -- the same word twice, one of them shouting. The
 * date is the thing a reader actually wants pinned to a claim like this and it
 * can never repeat the headline, which is how the reference designs use that
 * slot too. */

function Mark({ score }: { score: -1 | 0 | 1 }) {
  // A glyph as well as a word, so the column scans without relying on colour.
  const face = score === 1 ? "+" : score === -1 ? "−" : "·";
  const tone = score === 1 ? "var(--brand)"
             : score === -1 ? "var(--warn)"
             : "var(--text-muted)";
  return (
    <span
      className="mono" aria-hidden
      style={{
        color: tone, width: "1.1em", flexShrink: 0,
        fontSize: "var(--size-lead)", lineHeight: 1.2, textAlign: "center",
      }}
    >
      {face}
    </span>
  );
}

export function HomeRead({
  read, indexes, session,
}: {
  read: MarketRead;
  indexes: IndexRow[];
  session: string;
}) {
  return (
    <section className="hero stack" style={{ gap: "var(--gap-lg)" }}>
      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="between" style={{ alignItems: "center", gap: "var(--gap-sm)" }}>
          <span className="eyebrow" style={{ color: "var(--text-muted)" }}>The read</span>
          <span className="hero-chip">{session}</span>
        </div>
        <h2 style={{ fontSize: "var(--size-h1)", lineHeight: 1.15, margin: 0 }}>
          {read.headline}
        </h2>
        <p className="footnote" style={{ margin: 0, maxWidth: "58ch",
                                         color: "var(--text-secondary)" }}>
          {read.blurb}
        </p>
      </div>

      {read.tests.length > 0 && (
        <ul className="stack"
            style={{ gap: "var(--gap-xs)", listStyle: "none", margin: 0, padding: 0 }}>
          {read.tests.map((test) => (
            <li key={test.label} className="row"
                style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
              <Mark score={test.score} />
              <span className="footnote" style={{ minWidth: 0 }}>
                <span style={{ color: "var(--text-primary)" }}>{test.label}.</span>{" "}
                <span style={{ color: "var(--text-secondary)" }}>{test.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {indexes.length > 0 && (
        <div className="hero-strip">
          {indexes.map((row) => (
            <div key={row.symbol} className="stack" style={{ gap: 2 }}>
              <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-xs)" }}>
                <span className="mono caption" style={{ color: "var(--text-secondary)" }}>
                  {row.symbol}
                </span>
                <PriceChange value={row.change_pct} className="caption" />
              </div>
              <div className="num" style={{ fontSize: "var(--size-lead)", lineHeight: 1.2 }}>
                {price(row.close)}
              </div>
              <div className="caption" style={{ color: "var(--text-muted)" }}>
                {row.above_200 === null
                  ? "200-day not available yet"
                  : `${row.vs_200_pct === null ? "" : `${Math.abs(row.vs_200_pct).toFixed(1)}% `}` +
                    `${row.above_200 ? "above" : "below"} its 200-day`}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="caption" style={{ margin: 0, color: "var(--text-muted)" }}>
        {read.measured === TOTAL_TESTS
          ? "Four checks on the published numbers, nothing else."
          : `${read.measured} of ${TOTAL_TESTS} checks had data in the last run.`}{" "}
        <Link href="/market/breadth"
              style={{ textDecoration: "underline", color: "var(--text-secondary)" }}>
          See the breadth page
        </Link>{" "}
        for what each one is counting.
      </p>
    </section>
  );
}
