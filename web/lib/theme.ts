/**
 * One source of truth for the theme, because there are now two controls.
 *
 * The header toggle and the settings page both change the same thing, and if
 * each kept its own copy of the answer they would disagree the moment one of
 * them was used: the toggle would still say "Light" after settings had
 * switched to dark, because nothing told it. Every reader here subscribes, so
 * a change made anywhere reaches all of them, including in another tab.
 *
 * Three choices, two outcomes. "system" is not a third theme -- it means "do
 * not store a preference, follow the device", and it is stored as the absence
 * of a value rather than as the string "system". That way a reader who never
 * touches this keeps following their device forever, and one who picks a side
 * keeps that side even when the device changes its mind at sunset.
 */

export type Theme = "dark" | "light";
export type ThemeChoice = Theme | "system";

const KEY = "theme";
const EVENT = "themechange";

/** Dark is the default a device gets when it expresses no preference. A
 *  light-first financial site is a tell that nobody who trades built it. */
const FALLBACK: Theme = "dark";

export function readChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    // Private browsing, blocked site data: the reader still gets a theme.
    return "system";
  }
}

export function systemTheme(): Theme {
  try {
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light" : FALLBACK;
  } catch {
    return FALLBACK;
  }
}

export function resolve(choice: ThemeChoice): Theme {
  return choice === "system" ? systemTheme() : choice;
}

export function apply(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function setChoice(choice: ThemeChoice): void {
  try {
    if (choice === "system") window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, choice);
  } catch {
    // The theme still applies for this page view; it just will not persist.
  }
  apply(resolve(choice));
  window.dispatchEvent(new CustomEvent(EVENT));
}

/** Calls back whenever the choice changes here, in another tab, or -- while
 *  the reader is on "system" -- when the device itself switches. */
export function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia("(prefers-color-scheme: light)");
  const onMedia = () => { if (readChoice() === "system") onChange(); };

  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  media.addEventListener("change", onMedia);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
    media.removeEventListener("change", onMedia);
  };
}
