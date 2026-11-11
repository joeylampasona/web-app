"use client";

import { useState } from "react";
import { shareOrSave } from "@/lib/shareBlob";
import { renderEarningsImage, type EarningsCard } from "@/lib/shareEarnings";

/** One tap: this earnings read as an image, shared or saved. */
export function ShareEarningsRead({ card }: { card: EarningsCard }) {
  const [state, setState] = useState<"idle" | "working" | "saved" | "failed">("idle");
  const flash = (next: "saved" | "failed") => {
    setState(next);
    setTimeout(() => setState("idle"), 2000);
  };
  const onClick = async () => {
    setState("working");
    try {
      const blob = await renderEarningsImage(card);
      if (!blob) { flash("failed"); return; }
      const done = await shareOrSave(blob, `${card.symbol}-earnings-read.png`, {
        title: `${card.name} (${card.symbol}): ${card.takeaway}`,
        url: `${window.location.origin}/stocks/${card.symbol}`,
      });
      if (done === "saved") flash("saved"); else setState("idle");
    } catch {
      flash("failed");
    }
  };
  return (
    <button type="button" className="control footnote" onClick={onClick}
            disabled={state === "working"} data-share-earnings={card.symbol}
            style={{ minHeight: 36, padding: "0 var(--pad-md)" }}>
      {state === "working" ? "Drawing…" : state === "saved" ? "Image saved"
        : state === "failed" ? "Could not draw it" : "Share this read"}
    </button>
  );
}
