import { change, tone } from "@/lib/format";

/**
 * Gain and loss are never encoded with colour alone. This component always
 * emits the glyph and the explicit sign alongside the colour; there is no prop
 * to turn the glyph off, because removing it for visual cleanliness is exactly
 * the mistake the design system exists to prevent.
 */
export function PriceChange({
  value, digits = 2, unit = "%", className = "",
}: {
  value: number | null | undefined;
  digits?: number;
  unit?: string;
  className?: string;
}) {
  const t = tone(value);
  return (
    <span className={`num ${t} ${className}`.trim()}>
      {change(value, digits, unit)}
    </span>
  );
}
