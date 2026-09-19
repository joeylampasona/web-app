"use client";

import { useMemo, useState } from "react";
import type { Bar, ScreenFile, Setup } from "@/lib/types";
import { StockCard } from "./StockCard";

/** Tick several screens and see the union — a ticker appears once. */
export function CombinePanel({
  files, bars,
}: {
  files: ScreenFile[];
  bars: Record<string, Bar[]>;
}) {
  const [picked, setPicked] = useState<string[]>(files.map((f) => f.screen));

  const union = useMemo(() => {
    const seen = new Map<string, Setup & { screens: string[] }>();
    for (const file of files) {
      if (!picked.includes(file.screen)) continue;
      for (const setups of Object.values(file.setups)) {
        for (const setup of setups) {
          const existing = seen.get(setup.symbol);
          if (existing) {
            existing.screens.push(file.screen);
          } else {
            seen.set(setup.symbol, { ...setup, screens: [file.screen] });
          }
        }
      }
    }
    return [...seen.values()].sort((a, b) => {
      const left = typeof a.rs_rating === "number" ? a.rs_rating : -1;
      const right = typeof b.rs_rating === "number" ? b.rs_rating : -1;
      return right - left;
    });
  }, [files, picked]);

  return (
    <div className="stack">
      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        {files.map((file) => {
          const on = picked.includes(file.screen);
          return (
            <button
              key={file.screen}
              type="button"
              className="card between"
              aria-pressed={on}
              style={{
                minHeight: "var(--h-control)", padding: "var(--pad-md) var(--pad-lg)",
                cursor: "pointer",
                borderColor: on ? "var(--brand-ink)" : "var(--border)",
                background: on ? "var(--brand-muted)" : "var(--surface-1)",
              }}
              onClick={() =>
                setPicked(on
                  ? picked.filter((key) => key !== file.screen)
                  : [...picked, file.screen])}
            >
              <span>
                <span aria-hidden style={{ marginRight: "var(--gap-sm)" }}>
                  {on ? "▣" : "□"}
                </span>
                {file.name}
              </span>
              <span className="num dim">{file.total}</span>
            </button>
          );
        })}
      </div>

      <p className="footnote muted">
        {union.length} names across {picked.length} screen{picked.length === 1 ? "" : "s"}.
        A ticker on more than one appears once.
      </p>

      <div className="grid-auto">
        {union.map((setup) => (
          <StockCard key={setup.symbol} setup={setup} bars={bars[setup.symbol]} />
        ))}
      </div>
    </div>
  );
}
