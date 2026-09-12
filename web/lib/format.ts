// Price change format is always glyph, sign, value: `▲ +14.64%` and `▼ −3.61%`.
// True minus (−), not a hyphen, so widths match. The glyph is not decorative:
// roughly 8% of men are red-green colourblind and this whole product is
// red-green, so nothing here may encode gain or loss with colour alone.

export const MINUS = "−";
export const UP = "▲";
export const DOWN = "▼";
export const FLAT = "–";

export type Tone = "gain" | "loss" | "flat";

export function tone(value: number | null | undefined): Tone {
  if (value === null || value === undefined || Number.isNaN(value)) return "flat";
  if (value > 0) return "gain";
  if (value < 0) return "loss";
  return "flat";
}

export function glyph(value: number | null | undefined): string {
  const t = tone(value);
  return t === "gain" ? UP : t === "loss" ? DOWN : FLAT;
}

/** `+14.64%` / `−3.61%`, with a true minus. */
export function signed(value: number | null | undefined, digits = 2, unit = "%"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? MINUS : "";
  return `${sign}${Math.abs(value).toFixed(digits)}${unit}`;
}

/** The full `▲ +14.64%`. Never render one half without the other. */
export function change(value: number | null | undefined, digits = 2, unit = "%"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${glyph(value)} ${signed(value, digits, unit)}`;
}

export function price(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function money(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function compactMoney(value: number | null | undefined): string {
  if (!value) return "—";
  const units: [number, string][] = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  for (const [size, suffix] of units) {
    if (Math.abs(value) >= size) return `$${(value / size).toFixed(1)}${suffix}`;
  }
  return `$${value.toFixed(0)}`;
}

export function volume(value: number | null | undefined): string {
  if (!value) return "—";
  const units: [number, string][] = [[1e9, "B"], [1e6, "M"], [1e3, "K"]];
  for (const [size, suffix] of units) {
    if (value >= size) return `${(value / size).toFixed(1)}${suffix}`;
  }
  return value.toFixed(0);
}

export function ratio(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}×`;
}

export function decimal(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** New listings return the string `not ranked yet`. Print it verbatim. */
export function rsText(rating: number | string | null | undefined): string {
  if (typeof rating === "number") return String(rating);
  if (typeof rating === "string" && rating.length) return rating;
  return "not ranked yet";
}

export function isRanked(rating: number | string | null | undefined): rating is number {
  return typeof rating === "number";
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${m}/${d}`;
}

export function longDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(`${iso}T00:00:00Z`);
  return date.toLocaleDateString("en-US", {
    timeZone: "UTC", day: "numeric", month: "short", year: "numeric",
  });
}

export function weekday(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(`${iso}T00:00:00Z`);
  return date.toLocaleDateString("en-US", {
    timeZone: "UTC", weekday: "short", day: "numeric", month: "short",
  });
}
