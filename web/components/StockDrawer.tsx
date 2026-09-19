"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Drawer } from "vaul";
import type { StockFile } from "@/lib/types";
import { StockDetail } from "./StockDetail";

/** The drawer opens from any ticker anywhere. The full page is the deep link. */
const StockDrawerContext = createContext<{ open: (symbol: string) => void } | null>(null);

export function StockDrawerProvider({ children }: { children: React.ReactNode }) {
  const [symbol, setSymbol] = useState<string | null>(null);
  const [stock, setStock] = useState<StockFile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setStock(null);
    setError("");
    fetch(`/api/stock?symbol=${symbol}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((payload) => !cancelled && setStock(payload as StockFile))
      .catch(() => !cancelled && setError("We have nothing published for that ticker."));
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const value = useMemo(() => ({ open: (next: string) => setSymbol(next) }), []);

  return (
    <StockDrawerContext.Provider value={value}>
      {children}
      <Drawer.Root open={symbol !== null} onOpenChange={(open) => !open && setSymbol(null)}>
        <Drawer.Portal>
          <Drawer.Overlay style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)" }} />
          {/* The sheet itself never scrolls. It is a fixed-height column: a grab
              handle that stays put, and one scrolling pane beneath it.

              Scrolling and dismissing are the same gesture on a phone — drag
              down — and the sheet has to choose. When the whole sheet was the
              scroller it chose dismiss every time, so a stock page that now
              holds a chart, peers, catalysts, the market sweep, headlines,
              insiders and the X-ray could not be read past the first screenful.
              Separating them gives the drag handle to dismiss and the pane to
              scroll. overscroll-behavior: contain stops a scroll that reaches
              the bottom of the pane from carrying on into the page behind. */}
          <Drawer.Content
            style={{
              position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 60,
              background: "var(--surface-2)",
              borderTop: "0.5px solid var(--border-strong)",
              borderRadius: "var(--radius-card) var(--radius-card) 0 0",
              maxHeight: "92vh", overflow: "hidden",
              display: "flex", flexDirection: "column",
            }}
          >
            <div style={{ flexShrink: 0, padding: "var(--pad-lg) var(--pad-lg) 0" }}>
              <div
                aria-hidden
                style={{
                  width: 36, height: 4, borderRadius: "var(--radius-pill)",
                  background: "var(--border-stronger)", margin: "0 auto var(--pad-lg)",
                }}
              />
              <Drawer.Title className="eyebrow">{symbol ?? ""}</Drawer.Title>
            </div>
            <div
              style={{
                flex: 1, minHeight: 0, overflowY: "auto",
                overscrollBehavior: "contain", WebkitOverflowScrolling: "touch",
                padding: "var(--gap-sm) var(--pad-lg) var(--pad-xl)",
                // Below the home indicator on a phone, or the last row is
                // under it and cannot be tapped.
                paddingBottom: "calc(var(--pad-xl) + env(safe-area-inset-bottom))",
              }}
            >
              {error && <p className="muted footnote">{error}</p>}
              {!stock && !error && <p className="muted footnote">Loading…</p>}
              {stock && <StockDetail stock={stock} />}
            </div>
          </Drawer.Content>
        </Drawer.Portal>
      </Drawer.Root>
    </StockDrawerContext.Provider>
  );
}

export function useStockDrawer() {
  return useContext(StockDrawerContext);
}

export function TickerLink({
  symbol, children, className, style,
}: {
  symbol: string;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const drawer = useStockDrawer();
  return (
    <button
      type="button"
      className={className ? `ticker-link ${className}` : "ticker-link"}
      // cursor and text-align do not conflict with anything a caller passes,
      // so they stay inline. background, border and padding moved to the
      // zero-specificity .ticker-link rule -- inline they silently overrode
      // every className a caller gave this button.
      style={{ cursor: "pointer", textAlign: "left", ...style }}
      onClick={() => drawer?.open(symbol)}
    >
      {children}
    </button>
  );
}
