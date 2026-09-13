"use client";

import { useState } from "react";
import { longDate } from "@/lib/format";
import type { Article } from "@/content/reading";

export function ReadingList({ articles }: { articles: Article[] }) {
  const [kind, setKind] = useState<"guide" | "case_study">("guide");
  const rows = articles.filter((article) => article.kind === kind);
  return (
    <div className="stack">
      <div className="row" style={{ gap: 0 }}>
        <button type="button" className="control footnote grow" aria-pressed={kind === "guide"}
                style={{ borderRadius: "var(--radius) 0 0 var(--radius)" }}
                onClick={() => setKind("guide")}>Guides</button>
        <button type="button" className="control footnote grow"
                aria-pressed={kind === "case_study"}
                style={{ borderRadius: "0 var(--radius) var(--radius) 0", marginLeft: -1 }}
                onClick={() => setKind("case_study")}>Case studies</button>
      </div>
      {rows.map((article) => (
        <article key={article.slug} className="card stack" style={{ gap: "var(--gap-xs)" }}>
          <h3 style={{ fontSize: "var(--size-lead)" }}>{article.title}</h3>
          <p className="footnote muted" style={{ margin: 0 }}>{article.excerpt}</p>
          <div className="row" style={{ gap: "var(--gap-sm)" }}>
            <span className="caption dim">{longDate(article.date)}</span>
            <span className="badge">not written yet</span>
          </div>
        </article>
      ))}
    </div>
  );
}
