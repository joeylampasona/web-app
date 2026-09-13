"use client";

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import type { Bar } from "./types";

/**
 * Charts, fetched when a card actually needs one.
 *
 * A screen holds up to three hundred cards, and sending every chart with the
 * page made one screen a 5MB download — fine on a laptop, ten to twenty seconds
 * on a phone, which is the device this site was built for. Most of that was
 * cards nobody scrolls to.
 *
 * Requests made in the same tick are batched into one call, because a fast
 * scroll would otherwise fire twenty. Anything already fetched is never fetched
 * again, and bars handed down from the server are seeded here so the cards
 * above the fold draw immediately with no flash.
 */
type Store = Record<string, Bar[]>;

interface BarsState {
  get: (symbol: string) => Bar[] | undefined;
  request: (symbol: string) => void;
}

const BarsContext = createContext<BarsState | null>(null);

const BATCH_MS = 40;
const BATCH_MAX = 60;

export function BarsProvider({
  seed, children,
}: {
  seed?: Store;
  children: React.ReactNode;
}) {
  const [store, setStore] = useState<Store>(seed ?? {});
  // Every symbol already fetched, in flight, or seeded — so nothing is asked
  // for twice however many cards want it.
  const claimed = useRef<Set<string>>(new Set(Object.keys(seed ?? {})));
  const queue = useRef<Set<string>>(new Set());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(async () => {
    timer.current = null;
    const batch = [...queue.current].slice(0, BATCH_MAX);
    batch.forEach((s) => queue.current.delete(s));
    if (!batch.length) return;
    try {
      const response = await fetch(`/api/bars?symbols=${batch.join(",")}`);
      if (!response.ok) throw new Error(String(response.status));
      const payload = (await response.json()) as { bars: Store };
      setStore((held) => ({ ...held, ...payload.bars }));
    } catch {
      // A chart that will not load leaves the card without one, which is what
      // the card already handles. Release the claim so a later scroll retries.
      batch.forEach((s) => claimed.current.delete(s));
    }
    if (queue.current.size) timer.current = setTimeout(flush, BATCH_MS);
  }, []);

  const request = useCallback((symbol: string) => {
    if (claimed.current.has(symbol)) return;
    claimed.current.add(symbol);
    queue.current.add(symbol);
    if (!timer.current) timer.current = setTimeout(flush, BATCH_MS);
  }, [flush]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const value = useMemo<BarsState>(
    () => ({ get: (symbol) => store[symbol], request }),
    [store, request],
  );
  return <BarsContext.Provider value={value}>{children}</BarsContext.Provider>;
}

/**
 * Bars for one symbol, and whether this card should currently draw a chart.
 *
 * `visible` goes both ways on purpose. A chart is a live object holding canvas
 * buffers, and a screen holds up to three hundred cards; scrolling through them
 * all built three hundred chart instances that were never torn down, and iOS
 * Safari killed the tab — "a problem repeatedly occurred" — long before the
 * bottom of the list. Charts are unmounted once they are well off screen, which
 * runs their cleanup and frees the canvas.
 *
 * The bars themselves stay cached, so scrolling back redraws instantly and
 * fetches nothing.
 */
export function useLazyBars(symbol: string, enabled = true) {
  const context = useContext(BarsContext);
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const element = ref.current;
    if (!element) return;
    // No IntersectionObserver (an old browser, or a test runner) means draw it
    // rather than leave a permanent hole.
    if (typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        if (entry) setVisible(entry.isIntersecting);
      },
      // Generous enough that the chart is already drawn before the card is on
      // screen, and that mounting and unmounting both happen well out of sight.
      { rootMargin: "800px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [enabled]);

  useEffect(() => {
    if (visible && context) context.request(symbol);
  }, [visible, symbol, context]);

  return { ref, visible, bars: context?.get(symbol) };
}
