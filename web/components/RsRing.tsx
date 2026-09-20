import { isRanked } from "@/lib/format";
import type { Rating } from "@/lib/types";

/**
 * The relative strength rating as a ring.
 *
 * RS is the one number on this page the site's own backtest found an edge in,
 * and it was printed as a bare integer in a row of grey metadata — the same
 * weight as the industry name. A 1-to-99 percentile is exactly the shape a
 * ring reads well: the arc is the percentile, so 92 and 41 are different at a
 * glance without reading either digit.
 *
 * Drawn as SVG rather than a conic gradient because a conic gradient cannot be
 * given a rounded cap and renders a visible seam at 0deg in Safari.
 */
const SIZE = 46;
const STROKE = 4;
const R = (SIZE - STROKE) / 2;
const CIRCUM = 2 * Math.PI * R;

/** Where the arc stops being neutral. The screens ask for 70+; 90+ is the
 *  band the leaders sit in. Three steps, not a gradient: a continuously
 *  shifting hue implies a precision a percentile rank does not have. */
function ringColor(rating: number): string {
  if (rating >= 90) return "var(--gain)";
  if (rating >= 70) return "var(--brand)";
  if (rating <= 30) return "var(--loss)";
  return "var(--text-muted)";
}

export function RsRing({ rating, label = "RS" }: { rating: Rating | null; label?: string }) {
  const ranked = isRanked(rating);
  // An unranked stock gets the same ring with no arc, not a hidden component:
  // the gap where it would sit is what tells the reader the number is missing
  // rather than zero.
  const pct = ranked ? Math.max(0, Math.min(99, rating)) / 99 : 0;
  const color = ranked ? ringColor(rating) : "var(--border-stronger)";

  return (
    <div
      className="row"
      style={{ gap: "var(--gap-xs)", alignItems: "center", flexShrink: 0 }}
      title={ranked ? `Relative strength ${rating} of 99` : "Not ranked yet — too little history"}
    >
      <div style={{ position: "relative", width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} aria-hidden style={{ transform: "rotate(-90deg)" }}>
          <circle
            cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none"
            stroke="var(--border-stronger)" strokeWidth={STROKE}
          />
          {ranked && (
            <circle
              cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none"
              stroke={color} strokeWidth={STROKE} strokeLinecap="round"
              strokeDasharray={`${CIRCUM * pct} ${CIRCUM}`}
            />
          )}
        </svg>
        <div
          style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 0,
          }}
        >
          <span className="num" style={{ fontSize: 13, fontWeight: 600, lineHeight: 1,
                                         color: ranked ? "var(--text-primary)" : "var(--text-muted)" }}>
            {ranked ? rating : "—"}
          </span>
          <span className="dim" style={{ fontSize: 8, letterSpacing: "0.06em",
                                         textTransform: "uppercase", lineHeight: 1.4 }}>
            {label}
          </span>
        </div>
      </div>
    </div>
  );
}
