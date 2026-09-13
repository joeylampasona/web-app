"use client";

import { useState } from "react";
import { renderShareImage, type ShareRow } from "@/lib/shareImage";

/**
 * Shares a rendered PNG of the card — chart, metric rows and disclaimer — where
 * the platform will take a file, and falls back to the link and the clipboard
 * where it will not. Desktop browsers mostly will not, so they get a download.
 */
export function ShareButton({
  symbol, name, text, close, changePct, stage, rs, rows, getChart,
}: {
  symbol: string;
  name: string;
  text: string;
  close: number;
  changePct: number | null;
  stage: string;
  rs: number | string;
  rows: ShareRow[];
  getChart?: () => HTMLCanvasElement | null;
}) {
  const [state, setState] = useState<"idle" | "working" | "copied" | "saved">("idle");

  const flash = (next: "copied" | "saved") => {
    setState(next);
    setTimeout(() => setState("idle"), 1800);
  };

  const onClick = async () => {
    const url = typeof window === "undefined" ? "" : `${window.location.origin}/stocks/${symbol}`;
    setState("working");
    try {
      const blob = await renderShareImage({
        symbol, name, close, changePct, stage, rs, rows,
        chart: getChart?.() ?? null,
      });

      if (blob) {
        const file = new File([blob], `${symbol}.png`, { type: "image/png" });
        if (navigator.canShare?.({ files: [file] })) {
          await navigator.share({ files: [file], title: `${name} (${symbol})`, text, url });
          setState("idle");
          return;
        }
        // No file sharing here — hand over the image as a download instead.
        const href = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = href;
        anchor.download = `${symbol}.png`;
        anchor.click();
        URL.revokeObjectURL(href);
        flash("saved");
        return;
      }

      if (navigator.share) {
        await navigator.share({ title: `${name} (${symbol})`, text, url });
        setState("idle");
        return;
      }
      await navigator.clipboard.writeText(`${text}\n${url}`);
      flash("copied");
    } catch {
      try {
        await navigator.clipboard.writeText(`${text}\n${url}`);
        flash("copied");
      } catch {
        setState("idle");
      }
    }
  };

  const label = state === "working" ? "Rendering…"
    : state === "copied" ? "Copied"
    : state === "saved" ? "Image saved"
    : "Share";

  return (
    <button type="button" className="control footnote" onClick={onClick}
            disabled={state === "working"}
            style={{ minHeight: 36, padding: "0 var(--pad-md)" }}>
      {label}
    </button>
  );
}
