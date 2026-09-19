"use client";

import { useEffect, useState } from "react";
import { apply, readChoice, resolve, setChoice, subscribe, type Theme } from "@/lib/theme";

/**
 * The header's one-tap switch. The stored choice, the resolution of "system"
 * and the persistence all live in lib/theme, so this button and the settings
 * page cannot drift apart: both subscribe, and a change in either reaches the
 * other immediately rather than at the next page load.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const sync = () => {
      const next = resolve(readChoice());
      setTheme(next);
      apply(next);
    };
    sync();
    return subscribe(sync);
  }, []);

  // Toggling always picks a side. Someone reaching for this button wants the
  // other one now, not "follow the device and see what happens"; the settings
  // page is where "system" lives.
  const toggle = () => setChoice(theme === "dark" ? "light" : "dark");

  return (
    <button
      type="button"
      className="control footnote"
      style={{ minHeight: 36, padding: "0 var(--pad-sm)" }}
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      {theme === "dark" ? "◑" : "◐"}
    </button>
  );
}
