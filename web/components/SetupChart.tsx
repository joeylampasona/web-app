"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Contraction, Bar } from "@/lib/types";
import type { MaPlan } from "@/lib/movingAverages";

/**
 * The chart semantics are constant across every chart on the site: a dashed
 * amber pivot with its price at the left edge, dashed grey boxes on prior
 * contractions each labelled with its duration in weeks, a filled amber box on
 * the current base, a gain triangle on a confirmed breakout, a warn flag at a
 * failed poke, and a volume histogram tinted by direction underneath.
 *
 * A reader learns what the dashed amber line means once and never relearns it.
 *
 * A stock with no setup passes pivot null and no contractions, and gets the
 * same chart without the overlays that would be a lie on it: no pivot line,
 * because it has no pivot. The price and volume are the price and volume
 * either way, and a searched stock deserves to see them.
 */

type Box = { from: string; to: string; top: number; bottom: number; label?: string };

/** A chart asked to size itself picks a height from its own width, held
 *  between these so it stays readable on a phone and does not run off the
 *  bottom of a laptop screen. Rounded to a step so a slow drag across a few
 *  hundred pixels does not rebuild the chart at every intermediate width. */
const RESPONSIVE = { ratio: 0.52, min: 260, max: 460, step: 20 } as const;

/** The stock page is server-rendered, where a layout effect has nothing to
 *  measure and React rightly complains about one. Measuring before paint still
 *  matters in the browser, so the hook is chosen per environment. */
const useMeasureEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

/** What a responsive chart reserves before it has measured itself. */
export const MIN_CHART_HEIGHT = RESPONSIVE.min;

function heightFor(width: number): number {
  const raw = Math.min(RESPONSIVE.max, Math.max(RESPONSIVE.min, width * RESPONSIVE.ratio));
  return Math.round(raw / RESPONSIVE.step) * RESPONSIVE.step;
}

// Colours are read from the tokens at paint time, so no component ever writes
// a colour down. A missing token fails visibly rather than silently picking
// some other colour.
function token(name: string, fallback = "transparent"): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name);
  return value.trim() || fallback;
}

export function SetupChart({
  bars, pivot, contractions, breakoutDate, flags, symbol, height = 210, onReady,
  movingAverages,
}: {
  bars: Bar[];
  /** Null when the stock is not on a screen: there is no pivot to draw. */
  pivot: number | null;
  contractions: Contraction[];
  breakoutDate: string | null;
  flags: string[];
  symbol: string;
  /** A number fixes the height. "responsive" sizes the chart from its own
   *  width, which is what a page given over to a single stock wants. */
  height?: number | "responsive";
  /** Hands back a screenshot function so a card can put the chart in an image. */
  onReady?: (screenshot: (() => HTMLCanvasElement | null) | null) => void;
  /** Which averages to draw, decided by `planMovingAverages` so this chart and
   *  the key beneath it cannot disagree about what is on screen. Card charts
   *  leave it out and stay as they were — four extra lines on a chart the size
   *  of a business card is noise. */
  movingAverages?: MaPlan | null;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState<number | null>(null);
  const responsive = height === "responsive";
  const drawnHeight = responsive ? (measured ?? RESPONSIVE.min) : height;

  // Measured before paint, so a responsive chart is built once at the right
  // size rather than built small and then rebuilt.
  useMeasureEffect(() => {
    if (!responsive) return;
    const element = container.current;
    if (!element) return;
    const apply = () => setMeasured(heightFor(element.clientWidth));
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(element);
    return () => observer.disconnect();
  }, [responsive]);
  const [overlay, setOverlay] = useState<{ boxes: (Box & { x1: number; x2: number; y1: number; y2: number })[]; width: number }>(
    { boxes: [], width: 0 },
  );

  const boxes = useMemo<Box[]>(() => {
    if (!contractions.length || pivot === null) return [];
    const base: Box = {
      from: contractions[0].start,
      to: contractions[contractions.length - 1].end,
      top: pivot,
      bottom: Math.min(...contractions.map((c) => c.low)),
      label: "current base",
    };
    const priors: Box[] = contractions.slice(0, -1).map((c) => ({
      from: c.start, to: c.end, top: c.high, bottom: c.low,
      label: `${c.weeks.toFixed(1)}w`,
    }));
    return [base, ...priors];
  }, [contractions, pivot]);

  useEffect(() => {
    const element = container.current;
    if (!element || bars.length === 0) return;
    let disposed = false;
    let cleanup = () => {};

    (async () => {
      const lw = await import("lightweight-charts");
      if (disposed || !container.current) return;

      const chart = lw.createChart(element, {
        height: drawnHeight,
        layout: {
          background: { color: "transparent" },
          textColor: token("--chart-axis"),
          fontFamily: token("--font-mono", "monospace"),
          fontSize: 10,
        },
        grid: {
          vertLines: { color: token("--chart-grid") },
          horzLines: { color: token("--chart-grid") },
        },
        rightPriceScale: { borderColor: token("--border"), scaleMargins: { top: 0.08, bottom: 0.32 } },
        timeScale: { borderColor: token("--border"), rightOffset: 4, fixLeftEdge: true },
        crosshair: { mode: lw.CrosshairMode.Normal },
        handleScale: { axisPressedMouseMove: false },
      });

      const candles = chart.addCandlestickSeries({
        upColor: token("--gain"), downColor: token("--loss"),
        wickUpColor: token("--gain"), wickDownColor: token("--loss"),
        borderVisible: false,
      });
      candles.setData(
        bars.map((b) => ({
          time: b.time, open: b.open, high: b.high, low: b.low, close: b.close,
        })) as never,
      );

      const volumes = chart.addHistogramSeries({
        priceScaleId: "volume",
        priceFormat: { type: "volume" },
      });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.76, bottom: 0 } });
      volumes.setData(
        bars.map((b, i) => ({
          time: b.time,
          value: b.volume,
          color: i > 0 && b.close < bars[i - 1].close
            ? token("--chart-vol-down")
            : token("--chart-vol-up"),
        })) as never,
      );

      // Moving averages. The plan is already in slowest-first order, so a fast
      // line crossing a slow one is drawn on top of it rather than hidden
      // underneath, and each line is heavier as its window lengthens.
      for (const { window, values, weight } of movingAverages?.drawn ?? []) {
        const points = bars
          .map((b, i) => ({ time: b.time, value: values[i] }))
          .filter((p) => p.value !== null && p.value !== undefined);
        if (points.length < 2) continue;
        const line = chart.addLineSeries({
          color: token(`--chart-ma-${window}`),
          lineWidth: weight,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        line.setData(points as never);
      }

      if (pivot !== null) {
        candles.createPriceLine({
          price: pivot,
          color: token("--chart-pivot"),
          lineWidth: 1,
          lineStyle: lw.LineStyle.Dashed,
          axisLabelVisible: true,
          title: "pivot",
        });
      }

      const markers: { time: string; position: string; color: string; shape: string; text: string }[] = [];
      if (breakoutDate && bars.some((b) => b.time === breakoutDate)) {
        markers.push({
          time: breakoutDate, position: "aboveBar", color: token("--gain"),
          shape: "arrowUp", text: "breakout",
        });
      }
      if (flags.includes("failed_poke") && pivot !== null) {
        const poke = [...bars].reverse().find((b) => b.high > pivot && b.close <= pivot);
        if (poke) {
          markers.push({
            time: poke.time, position: "aboveBar", color: token("--warn"),
            shape: "circle", text: "⚑",
          });
        }
      }
      if (markers.length) candles.setMarkers(markers as never);

      chart.timeScale().fitContent();
      onReady?.(() => {
        try {
          return chart.takeScreenshot();
        } catch {
          return null;
        }
      });

      const project = () => {
        const width = element.clientWidth;
        const scale = chart.timeScale();
        const projected = boxes
          .map((box) => {
            const x1 = scale.timeToCoordinate(box.from as never);
            const x2 = scale.timeToCoordinate(box.to as never);
            const y1 = candles.priceToCoordinate(box.top);
            const y2 = candles.priceToCoordinate(box.bottom);
            if (x1 === null || x2 === null || y1 === null || y2 === null) return null;
            return { ...box, x1, x2, y1, y2 };
          })
          .filter(Boolean) as (Box & { x1: number; x2: number; y1: number; y2: number })[];
        setOverlay({ boxes: projected, width });
      };

      project();
      chart.timeScale().subscribeVisibleTimeRangeChange(project);
      const observer = new ResizeObserver(() => {
        chart.applyOptions({ width: element.clientWidth });
        project();
      });
      observer.observe(element);

      cleanup = () => {
        onReady?.(null);
        observer.disconnect();
        chart.remove();
      };
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [bars, pivot, boxes, breakoutDate, flags, drawnHeight, onReady, movingAverages]);

  return (
    <div style={{ position: "relative" }} aria-label={`${symbol} price chart`}>
      <div ref={container} style={{ width: "100%", height: drawnHeight }} />
      <svg
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
        width="100%"
        height={drawnHeight}
        aria-hidden
      >
        {overlay.boxes.map((box, index) => {
          const current = index === 0;
          return (
            <g key={`${box.from}-${box.to}-${index}`}>
              <rect
                x={Math.min(box.x1, box.x2)}
                y={Math.min(box.y1, box.y2)}
                width={Math.max(2, Math.abs(box.x2 - box.x1))}
                height={Math.max(2, Math.abs(box.y2 - box.y1))}
                fill={current ? "var(--chart-base-fill)" : "none"}
                stroke={current ? "var(--chart-base-line)" : "var(--chart-prior-base)"}
                strokeWidth={current ? 1 : 0.75}
                strokeDasharray={current ? undefined : "3 3"}
                rx={2}
              />
              {!current && box.label && (
                <text
                  x={Math.min(box.x1, box.x2) + 3}
                  y={Math.min(box.y1, box.y2) - 3}
                  fill="var(--chart-prior-base)"
                  fontSize="9"
                  fontFamily="var(--font-mono)"
                >
                  {box.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
