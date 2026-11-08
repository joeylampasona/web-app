/**
 * The navigation's icons, drawn in the same 1.6px line as the screen glyphs.
 *
 * They were typed characters (◆ ▦ ⌕ ◳ ☆ ⚙ ◐), each from whatever font the
 * device reached for, so they came out at five different sizes and weights,
 * and the theme toggle's half-moon is missing from the site's font entirely:
 * it rendered as a sliver that read as "‹". A path is the same on every device.
 */
export type NavIconName =
  | "home" | "screens" | "search" | "market" | "watchlist" | "settings" | "sun" | "moon";

const PATHS: Record<NavIconName, React.ReactNode> = {
  home: (
    <>
      <path d="M4 11.5 L12 4.5 L20 11.5" />
      <path d="M6.5 9.5 V19.5 H17.5 V9.5" />
      <path d="M10.5 19.5 V14.5 H13.5 V19.5" />
    </>
  ),
  screens: (
    <>
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15 L20 20" />
    </>
  ),
  market: (
    <>
      <path d="M4 20 H20" />
      <path d="M4 16 L9 11 L13 14 L20 6" />
      <path d="M16 6 H20 V10" />
    </>
  ),
  watchlist: (
    <path d="M12 4 L14.3 8.9 L19.6 9.5 L15.6 13.1 L16.7 18.4 L12 15.7 L7.3 18.4 L8.4 13.1 L4.4 9.5 L9.7 8.9 Z" />
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5 V5 M12 19 V21.5 M2.5 12 H5 M19 12 H21.5 M5.3 5.3 L7 7 M17 17 L18.7 18.7 M5.3 18.7 L7 17 M17 7 L18.7 5.3" />
    </>
  ),
  moon: <path d="M20 14.5 A8 8 0 1 1 9.5 4 A6.5 6.5 0 0 0 20 14.5 Z" />,
};

export function NavIcon({ name, size = 18 }: { name: NavIconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"
         aria-hidden focusable="false" style={{ display: "block", flexShrink: 0 }}>
      {PATHS[name]}
    </svg>
  );
}
