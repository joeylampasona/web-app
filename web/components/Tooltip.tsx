"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The (i) affordance. Every metric on a card has one, and none of them define a
 * metric as predictive — they say what the number measures and nothing more.
 */
export function Tooltip({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <span ref={ref} style={{ position: "relative", display: "inline-flex" }}>
      <button
        type="button"
        aria-label={`What ${label} means`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        style={{
          width: 18, height: 18, lineHeight: "16px", padding: 0,
          borderRadius: "var(--radius-pill)", cursor: "pointer",
          border: "0.5px solid var(--border-strong)", background: "transparent",
          color: "var(--text-muted)", fontSize: "var(--size-caption)",
        }}
      >
        i
      </button>
      {open && (
        <span
          role="tooltip"
          style={{
            position: "absolute", zIndex: 40, top: 24, left: -8, width: 248,
            background: "var(--surface-3)", color: "var(--text-secondary)",
            border: "0.5px solid var(--border-strong)",
            borderRadius: "var(--radius)", padding: "var(--pad-md)",
            fontSize: "var(--size-footnote)", lineHeight: 1.4,
          }}
        >
          <strong style={{ color: "var(--text-primary)", fontWeight: 500 }}>{label}</strong>
          <br />
          {text}
        </span>
      )}
    </span>
  );
}
