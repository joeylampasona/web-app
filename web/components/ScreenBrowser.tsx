"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { copy } from "@/lib/copy";
import { downloadCsv, toCsv } from "@/lib/exportCsv";
import { isRanked, price, ratio, rsText, signed } from "@/lib/format";
import type { Bar, ScreenFile, Setup } from "@/lib/types";
import { STAGE_COLOURS, StageBadge } from "./Badges";
import { StockCard } from "./StockCard";
import { PriceChange } from "./PriceChange";

type SortKey = "rs_rating" | "now_vs_pivot_pct" | "base_weeks" | "from_52w_high_pct" | "symbol";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "rs_rating", label: "RS rating" },
  { key: "now_vs_pivot_pct", label: "Now vs pivot" },
  { key: "base_weeks", label: "Base length" },
  { key: "from_52w_high_pct", label: "From 52-week high" },
  { key: "symbol", label: "Ticker" },
];

const STAGE_ORDER = ["forming", "fresh_breakout", "climbing", "played_out"];

export function ScreenBrowser({
  file, bars,
}: {
  file: ScreenFile;
  bars: Record<string, Bar[]>;
}) {
  const { signedIn, requireSignUp } = useAuth();
  const [stage, setStage] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("rs_rating");
  const [descending, setDescending] = useState(true);
  const [view, setView] = useState<"grid" | "list">("grid");

  const setups = useMemo(() => {
    const rows: Setup[] = stage
      ? file.setups[stage] ?? []
      : STAGE_ORDER.flatMap((s) => file.setups[s] ?? []);
    const value = (setup: Setup): number | string => {
      if (sort === "symbol") return setup.symbol;
      if (sort === "rs_rating") return isRanked(setup.rs_rating) ? setup.rs_rating : -1;
      return (setup[sort] as number | null) ?? -Infinity;
    };
    return [...rows].sort((a, b) => {
      const left = value(a);
      const right = value(b);
      const cmp = typeof left === "string"
        ? String(left).localeCompare(String(right))
        : Number(left) - Number(right);
      return descending ? -cmp : cmp;
    });
  }, [descending, file.setups, sort, stage]);

  return (
    <>
      <div className="stack" style={{ gap: "var(--gap-sm)", marginBottom: "var(--gap-lg)" }}>
        {STAGE_ORDER.map((key) => {
          const count = file.stage_counts[key] ?? 0;
          const selected = stage === key;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={selected}
              onClick={() => setStage(selected ? null : key)}
              className="card"
              style={{
                display: "flex", alignItems: "center", gap: "var(--gap-md)",
                minHeight: "var(--h-control)", padding: "var(--pad-md) var(--pad-lg)",
                textAlign: "left", cursor: "pointer",
                borderColor: selected ? "var(--brand)" : "var(--border)",
                background: selected ? "var(--brand-muted)" : "var(--surface-1)",
              }}
            >
              <span className="num" style={{ minWidth: 34, color: STAGE_COLOURS[key] }}>
                {count}
              </span>
              <span className="grow">
                <span style={{ color: STAGE_COLOURS[key] }}>{file.stage_labels[key]}</span>{" "}
                <span className="footnote dim">{file.stage_help[key]}</span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-sm)", marginBottom: "var(--gap-md)" }}>
        <Link href="/learn" className="control footnote" style={{ minHeight: "var(--h-control)" }}>
          How the screens work
        </Link>
        <Link href="/learn/backtest" className="control footnote"
              style={{ minHeight: "var(--h-control)" }}>
          Backtest these rules
        </Link>
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-sm)", marginBottom: "var(--gap-lg)" }}>
        <div className="row" style={{ gap: 0 }}>
          <button type="button" className="control" aria-pressed={view === "grid"}
                  style={{ borderRadius: "var(--radius) 0 0 var(--radius)" }}
                  onClick={() => setView("grid")}>
            Cards
          </button>
          <button type="button" className="control" aria-pressed={view === "list"}
                  style={{ borderRadius: "0 var(--radius) var(--radius) 0", marginLeft: -1 }}
                  onClick={() => setView("list")}>
            List
          </button>
        </div>

        <label className="row footnote dim" style={{ gap: "var(--gap-xs)" }}>
          <span className="visually-hidden">Sort by</span>
          <select
            className="control"
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
            style={{ background: "var(--surface-2)", minHeight: "var(--h-control)" }}
          >
            {SORTS.map((option) => (
              <option key={option.key} value={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="control"
          onClick={() => setDescending((v) => !v)}
          aria-label={descending ? "Sort ascending" : "Sort descending"}
          title={copy("screens.sort")}
        >
          {descending ? "↓" : "↑"}
        </button>
        <button
          type="button"
          className="control"
          onClick={() => {
            if (!signedIn) {
              requireSignUp("Export this screen");
              return;
            }
            const scope = stage ? `${file.screen}-${stage}` : file.screen;
            downloadCsv(`${scope}-${file.as_of}.csv`, toCsv(setups));
          }}
          title={copy("screens.export")}
        >
          Export
        </button>
      </div>

      <p className="muted footnote">{file.description}</p>

      {setups.length === 0 && (
        <div className="card muted footnote">
          Nothing is on this screen right now. That is a normal reading, not a fault —
          the filters are deliberately narrow.
        </div>
      )}

      {view === "grid" ? (
        <div className="grid-auto">
          {setups.map((setup) => (
            <StockCard key={`${setup.screen}-${setup.symbol}`} setup={setup}
                       bars={bars[setup.symbol]} />
          ))}
        </div>
      ) : (
        <div className="scroll-x card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Ticker</th><th>RS</th><th>Close</th><th>vs pivot</th>
                <th>Base</th><th>Tighten</th><th>Dry-up</th><th>Stage</th>
              </tr>
            </thead>
            <tbody>
              {setups.map((setup) => (
                <tr key={`${setup.screen}-${setup.symbol}`}>
                  <td className="text">
                    <Link href={`/stocks/${setup.symbol}`}>
                      <span className="mono">{setup.symbol}</span>{" "}
                      <span className="dim caption">{setup.name}</span>
                    </Link>
                  </td>
                  <td>{rsText(setup.rs_rating)}</td>
                  <td>{price(setup.close)}</td>
                  <td><PriceChange value={setup.now_vs_pivot_pct} /></td>
                  <td>{setup.base_weeks?.toFixed(1) ?? "—"}w</td>
                  <td>{ratio(setup.tightening_atr_ratio)}</td>
                  <td>{ratio(setup.volume_dryup_ratio)}</td>
                  <td className="text"><StageBadge stage={setup.stage} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
