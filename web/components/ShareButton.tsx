"use client";

import { useState } from "react";

/**
 * The brief leaves the share payload undefined — a rendered PNG of the chart
 * plus metrics is the likely answer but it is an open decision. Until it is
 * made, this shares a link and a one-line summary through the platform sheet,
 * and falls back to the clipboard.
 */
export function ShareButton({
  symbol, name, text,
}: {
  symbol: string;
  name: string;
  text: string;
}) {
  const [copied, setCopied] = useState(false);

  const onClick = async () => {
    const url = typeof window === "undefined" ? "" : `${window.location.origin}/stocks/${symbol}`;
    const payload = { title: `${name} (${symbol})`, text, url };
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share(payload);
        return;
      } catch {
        /* the sheet was dismissed; fall through to the clipboard */
      }
    }
    try {
      await navigator.clipboard.writeText(`${text}\n${url}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <button type="button" className="control footnote" onClick={onClick}
            style={{ minHeight: 36, padding: "0 var(--pad-md)" }}>
      {copied ? "Copied" : "Share"}
    </button>
  );
}
