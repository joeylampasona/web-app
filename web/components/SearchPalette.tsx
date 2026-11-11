"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { rsText } from "@/lib/format";
import type { LeadershipLayer } from "@/lib/types";
import { LAYER_LABELS, LayerChip } from "./Leadership";
import { PriceChange } from "./PriceChange";
import { Sparkline } from "./Sparkline";

/**
 * Search from any page: press "/" (or Ctrl/⌘ K), type, Enter.
 *
 * Search was a page, so looking a ticker up from a stock page was a tab, a
 * click and then the typing. A reader at a keyboard expects the slash key to
 * work wherever they are. Each result carries what the search page's rows
 * carry, plus where the stock sits against its industry, so often the answer
 * is in the list and the page never needs opening.
 *
 * It also finds the site's own pages by name, so "bread" goes to Breadth.
 */
interface Hit {
  symbol: string; name: string; industry: string; rs_rating: number | string;
  spark: number[] | null; close: number | null; change_pct: number | null;
  layer: LeadershipLayer | null; screens: number;
}
export interface PaletteDestination { href: string; title: string; blurb: string; section: string }

/** Lets the masthead's button open the same palette the key does. */
export const OPEN_SEARCH = "tape:open-search";

export function SearchPalette({ destinations, disabled }: {
  destinations: PaletteDestination[];
  /** The search page has its own box and its own "/" handler. */
  disabled?: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [total, setTotal] = useState(0);
  const [at, setAt] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  const close = useCallback(() => { setOpen(false); setQuery(""); setHits([]); setAt(0); }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const slash = event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
      const k = event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey);
      if (!slash && !k) return;
      if (disabled) return;
      if (slash) {
        const active = document.activeElement as HTMLElement | null;
        const tag = active?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || active?.isContentEditable) return;
      }
      event.preventDefault();
      setOpen(true);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_SEARCH, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_SEARCH, onOpen);
    };
  }, [disabled]);

  useEffect(() => { if (open) input.current?.focus(); }, [open]);

  const needle = query.trim();
  useEffect(() => {
    if (!needle) { setHits([]); setTotal(0); return; }
    let alive = true;
    // A short wait, so a ticker typed at speed is one request and not four.
    const timer = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(needle)}`)
        .then((r) => (r.ok ? r.json() : { rows: [] }))
        .then((body) => {
          if (!alive) return;
          setHits(Array.isArray(body?.rows) ? body.rows : []);
          setTotal(typeof body?.total === "number" ? body.total : 0);
          setAt(0);
        })
        .catch(() => { if (alive) setHits([]); });
    }, 110);
    return () => { alive = false; clearTimeout(timer); };
  }, [needle]);

  const pages = needle.length >= 2
    ? destinations.filter((d) => d.title.toLowerCase().includes(needle.toLowerCase())).slice(0, 4)
    : [];
  const count = hits.length + pages.length;

  const go = (index: number) => {
    const href = index < hits.length ? `/stocks/${hits[index].symbol}` : pages[index - hits.length]?.href;
    if (!href) return;
    close();
    router.push(href);
  };

  if (!open) return null;
  return (
    <div className="palette-veil" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Search">
        <div className="palette-input">
          <span aria-hidden className="mono">/</span>
          <input
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") { event.preventDefault(); close(); }
              else if (event.key === "ArrowDown") { event.preventDefault(); setAt((v) => Math.min(count - 1, v + 1)); }
              else if (event.key === "ArrowUp") { event.preventDefault(); setAt((v) => Math.max(0, v - 1)); }
              else if (event.key === "Enter") { event.preventDefault(); go(at); }
            }}
            placeholder="Ticker, company, industry or page"
            aria-label="Search"
            autoComplete="off"
            spellCheck={false}
          />
          <button type="button" className="caption dim" onClick={close}
                  style={{ background: "none", border: 0, cursor: "pointer" }}>esc</button>
        </div>

        {needle && count === 0 && (
          <p className="footnote muted" style={{ margin: 0, padding: "var(--pad-md) var(--pad-lg)" }}>
            Nothing matches. The universe is liquid US common stocks only: under $5,
            under $300M or thinly traded, and a name is not in it.
          </p>
        )}

        {count > 0 && (
          <div className="palette-list" role="listbox">
            {hits.map((hit, index) => (
              <button key={hit.symbol} type="button" role="option" aria-selected={at === index}
                      className="palette-row" onMouseEnter={() => setAt(index)} onClick={() => go(index)}>
                <span className="mono palette-symbol">{hit.symbol}</span>
                <span className="palette-name">
                  <span>{hit.name}</span>
                  <span className="caption dim"> · {hit.industry}</span>
                </span>
                <span className="palette-figures">
                  {hit.layer && hit.layer !== "unconfirmed" && (
                    <LayerChip layer={hit.layer} label={LAYER_LABELS[hit.layer]} />
                  )}
                  {hit.screens > 0 && (
                    <span className="badge badge--brand">{hit.screens} screen{hit.screens === 1 ? "" : "s"}</span>
                  )}
                  <Sparkline points={hit.spark} changePct={hit.change_pct} />
                  {hit.close != null && <span className="num">{hit.close.toFixed(2)}</span>}
                  <PriceChange value={hit.change_pct} className="footnote" />
                  <span className="num palette-rs" title="Relative strength rating">
                    RS {rsText(hit.rs_rating)}
                  </span>
                </span>
              </button>
            ))}
            {pages.map((page, i) => {
              const index = hits.length + i;
              return (
                <button key={page.href} type="button" role="option" aria-selected={at === index}
                        className="palette-row" onMouseEnter={() => setAt(index)} onClick={() => go(index)}>
                  <span className="label-caps palette-symbol" style={{ color: "var(--text-muted)" }}>Page</span>
                  <span className="palette-name">
                    <span>{page.title}</span>
                    <span className="caption dim"> · {page.section} · {page.blurb}</span>
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <div className="palette-foot caption dim">
          <span><kbd>↑</kbd> <kbd>↓</kbd> move</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>esc</kbd> close</span>
          {total > hits.length && <span className="grow" style={{ textAlign: "right" }}>
            first {hits.length} of {total}; keep typing to narrow</span>}
        </div>
      </div>
    </div>
  );
}
