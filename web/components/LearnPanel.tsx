"use client";

import Link from "next/link";
import { useState } from "react";
import type { LearnFile } from "@/lib/types";
import { LearnSchematic } from "./LearnSchematic";

const TONE: Record<string, string> = {
  gain: "var(--gain)", loss: "var(--loss)", flat: "var(--flat)",
};

export function LearnPanel({ files }: { files: LearnFile[] }) {
  const [screen, setScreen] = useState(files[0]?.screen ?? "vcp");
  const [anchor, setAnchor] = useState<string | null>(null);
  const file = files.find((f) => f.screen === screen) ?? files[0];
  if (!file) return null;

  return (
    <div className="stack" style={{ gap: "var(--pad-xl)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {files.map((option) => (
          <button
            key={option.screen}
            type="button"
            className="control footnote"
            style={{ borderRadius: "var(--radius-pill)" }}
            aria-pressed={option.screen === screen}
            onClick={() => {
              setScreen(option.screen);
              setAnchor(null);
            }}
          >
            {option.name}
          </button>
        ))}
      </div>

      <section className="stack">
        <div className="eyebrow">1 · The anatomy of a breakout</div>
        <p className="muted footnote" style={{ margin: 0 }}>{file.shape}</p>
        <LearnSchematic screen={file.screen} selected={anchor} onSelect={setAnchor} />
      </section>

      <section className="stack">
        <div className="eyebrow">2 · The concepts</div>
        <ol className="stack" style={{ listStyle: "none", padding: 0, margin: 0,
                                       gap: "var(--gap-sm)" }}>
          {file.concepts.map((concept, index) => {
            const active = anchor === concept.anchor;
            return (
              <li key={concept.anchor + index}>
                <button
                  type="button"
                  className="card"
                  style={{
                    width: "100%", textAlign: "left", cursor: "pointer",
                    padding: "var(--pad-md) var(--pad-lg)",
                    borderColor: active ? "var(--brand)" : "var(--border)",
                    background: active ? "var(--brand-muted)" : "var(--surface-1)",
                  }}
                  aria-pressed={active}
                  onClick={() => setAnchor(active ? null : concept.anchor)}
                >
                  <span className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
                    <span className="num dim caption">{index + 1}</span>
                    <span>{concept.title}</span>
                  </span>
                  <span className="footnote muted">{concept.text}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="stack">
        <div className="eyebrow">3 · How we narrow the market down</div>
        <p className="muted footnote" style={{ margin: 0 }}>{file.funnel_preface}</p>
        <ol className="stack" style={{ paddingLeft: "var(--pad-lg)", margin: 0,
                                       gap: "var(--gap-sm)" }}>
          {file.funnel.map((step) => (
            <li key={step.key}>
              <div>{step.title}</div>
              <div className="footnote muted">{step.text}</div>
            </li>
          ))}
        </ol>
        <Link href={file.funnel_callout.href} className="card between"
              style={{ minHeight: "var(--h-control)" }}>
          <span className="footnote">{file.funnel_callout.text}</span>
          <span className="dim">{file.funnel_callout.cta} →</span>
        </Link>
      </section>

      <section className="stack">
        <div className="eyebrow">4 · The trade, once it triggers</div>
        <p className="muted footnote" style={{ margin: 0 }}>{file.trade_steps_preface}</p>
        <ol className="stack" style={{ listStyle: "none", padding: 0, margin: 0,
                                       gap: "var(--gap-md)" }}>
          {file.trade_steps.map((step) => (
            <li key={step.step} className="row" style={{ alignItems: "flex-start",
                                                         gap: "var(--gap-md)" }}>
              <span
                className="num"
                aria-hidden
                style={{
                  width: 24, height: 24, borderRadius: "var(--radius-pill)",
                  display: "grid", placeItems: "center", flex: "0 0 auto",
                  border: `1px solid ${TONE[step.tone] ?? "var(--border-strong)"}`,
                  color: TONE[step.tone] ?? "var(--text-secondary)",
                  fontSize: "var(--size-caption)",
                }}
              >
                {step.step}
              </span>
              <span>
                <div>{step.title}</div>
                <div className="footnote muted">{step.text}</div>
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
