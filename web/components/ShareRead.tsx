"use client";

import { useState } from "react";
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
      const name = `the-read-${card.asOf}.png`;
      const file = new File([blob], name, { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title: card.headline, url: window.location.origin });
          setState("idle");
          return;
        } catch (error) {
          // Closing the share sheet is not a failure, and needs no download.
          if ((error as Error)?.name === "AbortError") { setState("idle"); return; }
        }
      }
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = name;
      anchor.click();
      URL.revokeObjectURL(href);
      flash("saved");
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
