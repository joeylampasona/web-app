import { change, tone } from "@/lib/format";

/**
 * Gain and loss are never encoded with colour alone. This component always
 * emits the glyph and the explicit sign alongside the colour; there is no prop
 * to turn the glyph off, because removing it for visual cleanliness is exactly
 * the mistake the design system exists to prevent.
 */
export function PriceChange({
  value, digits = 2, unit = "%", className = "", badge = false,
}: {
  value: number | null | undefined;
  digits?: number;
  unit?: string;
  className?: string;
  /** Wrap the figure in a tinted pill, for a column read as a heat map. */
  badge?: boolean;
}) {
  const t = tone(value);
  if (badge) {
    // .badge--gain and .badge--loss are the existing tinted fills, already at
    // the low opacity this wants. The glyph and the sign still come from
    // change(), so the pill is an addition to the encoding and never a
    // replacement for it.
    const variant = t === "flat" ? "" : ` badge--${t}`;
    return (
      <span className={`badge num${variant} ${className}`.trim()}>
        {change(value, digits, unit)}
      </span>
    );
  }
  return (
    <span className={`num ${t} ${className}`.trim()}>
      {change(value, digits, unit)}
    </span>
  );
}
