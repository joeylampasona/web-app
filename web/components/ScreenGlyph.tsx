/**
 * A tiny diagram of the shape each screen looks for.
 *
 * Drawn rather than lettered, and drawn to be the actual structure rather than
 * a generic chart squiggle: the VCP glyph really does have a decaying
 * amplitude, the cup really is a rounded bottom with a shallower handle after
 * it, the flat base really is level before it lifts. Someone who has not read
 * the blurb should be able to guess which is which, and someone who has should
 * find the picture agrees with it.
 *
 * Stroke is currentColor so the glyph takes the colour of whatever text it sits
 * beside, which keeps it muted next to a description and legible on both
 * themes without a second set of values.
 */
const SIZE = 24;

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label={label}
      style={{ flexShrink: 0, opacity: 0.85 }}
    >
      {children}
    </svg>
  );
}

const GLYPHS: Record<string, { label: string; art: React.ReactNode }> = {
  "/screens/vcp": {
    label: "Contractions getting smaller",
    // Each swing half the last. That decay is the pattern.
    art: (
      <>
        <path d="M2 6 L5 18 L8 8 L11 15 L14 10 L16 13.5 L18 11.5 L19.5 12.6" />
        <path d="M19.5 12.6 L22 7" strokeDasharray="2 1.6" />
      </>
    ),
  },
  "/screens/blue_sky": {
    // No overhead supply: the lid is behind it, not above it.
    label: "Above every prior price",
    art: (
      <>
        <path d="M2 17 L7 14 L11 15 L15 9 L19 5" />
        <path d="M2 8.5 L11 8.5" strokeDasharray="2 1.6" opacity={0.55} />
        <circle cx="19" cy="5" r="1.6" fill="currentColor" stroke="none" />
      </>
    ),
  },
  "/screens/multi_year": {
    // A lid that has held for years, approached again from far below. Drawn
    // angular on purpose: a smooth bowl here is the cup-and-handle glyph, and
    // at 24px the two were indistinguishable. The decline is a sharp break, the
    // trough is long and flat, the return is one straight climb.
    label: "A long lid, approached again",
    art: (
      <>
        <path d="M1.5 5.5 L22.5 5.5" strokeDasharray="2.5 2" />
        <path d="M2 7.5 L7 20 L13.5 19.5 L22 8" />
      </>
    ),
  },
  "/screens/ipo": {
    // Short history: nothing to the left of the listing.
    art: (
      <>
        <path d="M8 3 L8 21" strokeDasharray="2 1.8" opacity={0.6} />
        <path d="M9.5 15 L12 9 L14.5 13 L17 11.5 L19 12.5 L21.5 7" />
      </>
    ),
    label: "A recent listing's first base",
  },
  "/screens/flat_base": {
    // Level, then it lifts. The blurb's own description.
    art: (
      <>
        <path d="M2 14 L14 14" strokeDasharray="2.5 2" />
        <path d="M14 14 L21 7" />
        <path d="M16.5 7 L21 7 L21 11.5" />
      </>
    ),
    label: "A level shelf, then a lift",
  },
  "/screens/cup_and_handle": {
    // Rounded bottom, then a shallower pause under the same lid.
    art: (
      <>
        <path d="M3 5 C3 16, 13 16, 13 5" />
        <path d="M13 5 L13 9 C13 13, 18 13, 18 9 L18 6" />
        <path d="M18 6 L21.5 3.5" />
      </>
    ),
    label: "A rounded bottom, then a small pause",
  },
  "/screens/bull_flag": {
    label: "A sharp rise, then a short drift down",
    // The pole does the talking: steep, then a small tilted pause.
    art: (
      <>
        <path d="M3 20 L10 5" />
        <path d="M10 6.5 L17 9 L17 14.5 L10 12 Z" />
        <path d="M17 11.5 L21.5 9.5" strokeDasharray="2 1.6" />
      </>
    ),
  },
  "/screens/bear_flag": {
    label: "A sharp fall, then a short drift up",
    // The mirror, so the pair reads as a pair at a glance.
    art: (
      <>
        <path d="M3 4 L10 19" />
        <path d="M10 17.5 L17 15 L17 9.5 L10 12 Z" />
        <path d="M17 12.5 L21.5 14.5" strokeDasharray="2 1.6" />
      </>
    ),
  },
  "/screens/falling_wedge": {
    label: "Both lines falling, the upper one faster",
    art: (
      <>
        <path d="M2.5 4 L21 15" />
        <path d="M2.5 13 L21 17" />
      </>
    ),
  },
  "/screens/rising_wedge": {
    label: "Both lines rising, the lower one faster",
    art: (
      <>
        <path d="M2.5 20 L21 9" />
        <path d="M2.5 11 L21 7" />
      </>
    ),
  },
  "/screens/triangle": {
    label: "Falling highs against rising or level lows",
    art: (
      <>
        <path d="M2.5 5 L21 12" />
        <path d="M2.5 19 L21 12" />
      </>
    ),
  },
  "/screens/descending_triangle": {
    label: "Falling highs against a level floor",
    art: (
      <>
        <path d="M2.5 5 L21 17" />
        <path d="M2.5 17.5 L21 17.5" />
      </>
    ),
  },
  "/screens/squeeze": {
    label: "The range at its quietest in months",
    // Wide, then pinched: the compression is the whole idea.
    art: (
      <>
        <path d="M2.5 3.5 L10 9 L21 11" />
        <path d="M2.5 20.5 L10 15 L21 13" />
      </>
    ),
  },
  "/screens/combine": {
    label: "Several screens at once",
    art: (
      <>
        <circle cx="9.5" cy="12" r="6" opacity={0.8} />
        <circle cx="15.5" cy="12" r="6" opacity={0.8} />
      </>
    ),
  },
  "/screens/custom": {
    label: "Move every dial yourself",
    art: (
      <>
        <path d="M3 7 L21 7" opacity={0.6} />
        <path d="M3 12 L21 12" opacity={0.6} />
        <path d="M3 17 L21 17" opacity={0.6} />
        <circle cx="8" cy="7" r="2.1" fill="var(--surface-2)" />
        <circle cx="16" cy="12" r="2.1" fill="var(--surface-2)" />
        <circle cx="11" cy="17" r="2.1" fill="var(--surface-2)" />
      </>
    ),
  },
};

export function ScreenGlyph({ href }: { href: string }) {
  const glyph = GLYPHS[href];
  if (!glyph) return null;
  return <Frame label={glyph.label}>{glyph.art}</Frame>;
}

/** Whether a destination has a glyph, so callers can keep alignment consistent. */
export function hasGlyph(href: string): boolean {
  return href in GLYPHS;
}
