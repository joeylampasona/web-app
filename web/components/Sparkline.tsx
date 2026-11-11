import { tone } from "@/lib/format";

/**
 * A price shape for rows too small to hold a chart.
 *
 * The series arrives normalised 0-100 with no units, because a sixty-pixel
 * line cannot express a price and should not pretend to. What it can express
 * is shape, so that is all it draws.
 *
 * Direction is never carried by the line's colour alone -- the site's rule,
 * and a necessary one, since roughly one man in twelve cannot separate the
 * greens from the reds. The change figure beside the line says it in numbers,
 * and the line is tinted as a second channel rather than the only one.
 *
 * A null series renders nothing rather than a flat line. A stock that did not
 * move and a stock with no data look identical as a horizontal stroke, and
 * only one of those is true.
 */
/** Any series stretched to the 0-100 box this draws, or null with no range. */
export function normalise(values: (number | null | undefined)[]): number[] | null {
  const known = values.filter((v): v is number => v != null);
  if (known.length < 2) return null;
  const lo = Math.min(...known), hi = Math.max(...known);
  if (hi === lo) return null;
  return known.map((v) => ((v - lo) / (hi - lo)) * 100);
}

export function Sparkline({
  points, changePct, width = 64, height = 22, colour, label = "Price shape over the last six weeks",
}: {
  points: number[] | null | undefined;
  changePct?: number | null;
  width?: number;
  height?: number;
  /** For a count rather than a price, where up is not "gain": the caller's
   *  own tone instead of the sign of the change. */
  colour?: string;
  /** What the line is, for a screen reader. */
  label?: string;
}) {
  // A caller that hands over raw figures (contracts, dollars) instead of a
  // 0-100 shape would otherwise draw a line thousands of units outside its
  // box, and the box does not clip: the positioning table did exactly that
  // and ruled vertical lines down every row. Anything outside the range is
  // stretched to it here.
  if (points && points.some((v) => v < 0 || v > 100)) points = normalise(points);
  if (!points || points.length < 2) {
    return (
      <span
        className="caption dim"
        style={{ width, display: "inline-block", textAlign: "center" }}
        title="No price shape published for this name"
      >
        —
      </span>
    );
  }

  const stroke = colour ? colour : tone(changePct) === "gain" ? "var(--gain)"
               : tone(changePct) === "loss" ? "var(--loss)"
               : "var(--flat)";

  // The series is 0 at its low and 100 at its high, and SVG's y axis grows
  // downward, so the value is flipped. A 4-unit inset top and bottom keeps the
  // stroke from being clipped at the extremes.
  const INSET = 4;
  const span = 100 - INSET * 2;
  const d = points
    .map((value, i) => {
      const x = (i / (points.length - 1)) * 100;
      const y = INSET + (100 - value) / 100 * span;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      role="img"
      aria-label={
        changePct === null || changePct === undefined
          ? label
          : `${label}, ${changePct > 0 ? "up" : "down"} ${Math.abs(changePct).toFixed(1)} per cent`
      }
      style={{ display: "block", flexShrink: 0, overflow: "visible" }}
    >
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        // The viewBox is stretched non-uniformly to fit the box, which would
        // stretch the stroke with it and leave a line thick on one axis and
        // thin on the other.
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
