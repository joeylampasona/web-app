"use client";

import { signed, tone } from "@/lib/format";
import { useGapToPivot } from "@/lib/useQuotes";

/**
 * How far price is from the pivot, using the delayed quote when one exists.
 *
 * The published figure is from the close. During the session that is the one
 * number on the card most likely to be wrong, and it is the number the whole
 * screen is about — so this replaces it when a quote is available and leaves
 * it alone when one is not.
 *
 * Marked whenever it is delayed. A price that is twenty minutes old presented
 * as though it were the close is a worse fault than showing the close, because
 * the reader has no way to tell. The dot is the mark; the title carries the
 * time it was taken.
 */
export function DelayedGap({
  symbol, pivot, published,
}: {
  symbol: string;
  pivot: number | null;
  published: number | null;
}) {
  const { pct, delayed, at } = useGapToPivot(symbol, pivot, published);
  if (pct === null) return <span className="num dim">—</span>;
  return (
    <span
      className={`num ${tone(pct)}`}
      title={delayed
        ? `Delayed price${at ? `, taken ${at.replace("T", " ")}` : ""}. `
          + `At the close it was ${signed(published)}.`
        : "At the close."}
    >
      {signed(pct)}
      {delayed && (
        <span
          aria-hidden
          style={{
            display: "inline-block", width: 4, height: 4, borderRadius: "50%",
            background: "var(--warn)", verticalAlign: "super", marginLeft: 3,
          }}
        />
      )}
    </span>
  );
}
