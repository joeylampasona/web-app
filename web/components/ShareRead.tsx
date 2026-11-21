"use client";

import { useState } from "react";
import { postText } from "@/lib/share";
import { shareOrSave } from "@/lib/shareBlob";
import { renderReadImage, type ReadCard } from "@/lib/shareRead";
import { CopyTextButton } from "./CopyTextButton";

/** The read as a post: the night, the verdict, the four checks, the address. */
export function readText(card: ReadCard): string {
  const day = new Date(`${card.asOf}T12:00:00Z`);
  const when = `${day.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" })} close, `
    + day.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const inGear = card.cells.filter((cell) => cell.score === 1).length;
  const verdict = /[.!?]$/.test(card.headline) ? card.headline : `${card.headline}.`;
  return postText([
    `The Tape · ${when}`,
    `${verdict} ${inGear} of ${card.cells.length} checks in gear.`,
    card.cells.map((cell) => `${cell.label} ${cell.value}`).join(" · "),
    card.strength ? `Strength: ${card.strength}` : null,
  ], "/");
}

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
    <>
      <button type="button" className="control footnote" onClick={onClick}
              disabled={state === "working"} data-share-read
              style={{ minHeight: 36, padding: "0 var(--pad-md)", alignSelf: "flex-start" }}>
        {state === "working" ? "Drawing…" : state === "saved" ? "Image saved"
          : state === "failed" ? "Could not draw it" : "Share tonight’s read"}
      </button>
      <CopyTextButton text={() => readText(card)} />
    </>
  );
}
