"use client";

import { useEffect, useState } from "react";

/**
 * How much of the screen the on-screen keyboard is covering.
 *
 * A bottom sheet is `position: fixed; bottom: 0`, which anchors it to the
 * layout viewport. iOS does not shrink the layout viewport when the keyboard
 * opens — it shrinks the *visual* viewport and scrolls — so a sheet stays
 * pinned to the bottom of the screen with the keyboard drawn on top of it. The
 * field you are typing into ends up underneath your own thumbs, which is what
 * "the sign-in disappears and I cannot see where I am typing" is.
 *
 * visualViewport reports the covered height, so the sheet can lift by exactly
 * that much. Returns 0 wherever the API is absent, where the sheet then behaves
 * as it always has.
 */
export function useKeyboardInset(): number {
  const [inset, setInset] = useState(0);

  useEffect(() => {
    const view = typeof window === "undefined" ? null : window.visualViewport;
    if (!view) return;

    const measure = () => {
      // What the layout viewport has that the visual one does not: the keyboard,
      // plus any browser chrome that slid in with it. Small values are that
      // chrome rather than a keyboard, so they are ignored.
      const covered = window.innerHeight - view.height - view.offsetTop;
      setInset(covered > 80 ? Math.round(covered) : 0);
    };

    measure();
    view.addEventListener("resize", measure);
    view.addEventListener("scroll", measure);
    return () => {
      view.removeEventListener("resize", measure);
      view.removeEventListener("scroll", measure);
    };
  }, []);

  return inset;
}
