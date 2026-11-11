"use client";

import { useState } from "react";
import { shareOrSave } from "@/lib/shareBlob";
import { renderReadImage, type ReadCard } from "@/lib/shareRead";

/**
 * One tap: the night's read as an image. Shared as a file where the platform
 * takes one (a phone's share sheet), saved as a download where it does not.
 */
export function ShareRead({ card }: { card: ReadCard }) {
  const [state, setState] = useState<"idle" | "working" | "saved" | "failed">("idle");
  const flash = (next: "saved" | "failed") => {
    setState(next);
    setTimeout(() => setState("idle"), 2000);
  };

  const onClick = async () => {
    setState("working");
    try {
      const blob = await renderReadImage(card);
      if (!blob) { flash("failed"); return; }
      const done = await shareOrSave(blob, `the-read-${card.asOf}.png`,
        { title: card.headline, url: window.location.origin });
      if (done === "saved") flash("saved"); else setState("idle");
    } catch {
      flash("failed");
    }
  };

  return (
    <button type="button" className="control footnote" onClick={onClick}
            disabled={state === "working"} data-share-read
            style={{ minHeight: 36, padding: "0 var(--pad-md)", alignSelf: "flex-start" }}>
      {state === "working" ? "Drawing…" : state === "saved" ? "Image saved"
        : state === "failed" ? "Could not draw it" : "Share tonight’s read"}
    </button>
  );
}
