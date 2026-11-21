"use client";

import { useState } from "react";
import { copyText } from "@/lib/share";

/**
 * The same thing as words, for somebody who posts words.
 *
 * Every share button draws a picture, and a picture cannot be pasted into a
 * message thread, quoted, or read by a screen reader. This puts the card's
 * own facts on the clipboard as a few short lines with the page's address
 * last. `text` may be a function, so a caller with something to assemble
 * does it when asked rather than on every render.
 */
export function CopyTextButton({ text, label = "Copy as text" }: {
  text: string | (() => string);
  label?: string;
}) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const onClick = async () => {
    const done = await copyText(typeof text === "function" ? text() : text);
    setState(done ? "copied" : "failed");
    setTimeout(() => setState("idle"), 1800);
  };
  return (
    <button type="button" className="control footnote" onClick={onClick} data-copy-text
            style={{ minHeight: 36, padding: "0 var(--pad-md)" }}>
      {state === "copied" ? "Copied" : state === "failed" ? "Could not copy" : label}
    </button>
  );
}
