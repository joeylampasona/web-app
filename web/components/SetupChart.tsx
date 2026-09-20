"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Contraction, Bar } from "@/lib/types";
import type { MaPlan } from "@/lib/movingAverages";
import type { ShapeGeometry } from "@/lib/types";

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
  movingAverages, shape,
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
  /** The fitted formation, on the shape screens only. Draws the two
   *  trendlines and marks the swings they were fitted through, so the reader
   *  can see the structure the screen claims rather than take it on trust. */
  shape?: ShapeGeometry | null;
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
  const [overlay, setOverlay] = useState<{
    boxes: (Box & { x1: number; x2: number; y1: number; y2: number })[];
    /** The swings the formation's lines were fitted through, already in pixels.
     *  Drawn here rather than as chart markers because the library's markers
     *  come at one fixed size, which on a card this small is a dot bigger than
     *  the candles it is annotating. */
    swings: { x: number; y: number; side: "upper" | "lower" }[];
    width: number;
  }>({ boxes: [], swings: [], width: 0 });

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

      // The formation itself. Two straight segments between the endpoints the
      // publisher computed, never refitted here: the browser has the same
      // bars but not the same swing detection, and a second opinion about
      // where the line goes is exactly how an overlay ends up not touching
      // the highs it claims to be drawn through.
      if (shape?.lines) {
        const boundary = shape.direction === "short"
          ? token("--loss") : token("--gain");
        for (const side of ["upper", "lower"] as const) {
          const line = shape.lines[side];
          if (!line) continue;
          // The line that the break happens through is the one that matters,
          // so it is drawn solid and the other dashed. For a long shape that
          // is the ceiling; for a short one, the floor.
          const isBoundary = shape.direction === "short"
            ? side === "lower" : side === "upper";
          const series = chart.addLineSeries({
            color: isBoundary ? boundary : token("--text-muted"),
            lineWidth: isBoundary ? 2 : 1,
            lineStyle: isBoundary ? lw.LineStyle.Solid : lw.LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          series.setData([
            { time: line.from.date, value: line.from.price },
            { time: line.to.date, value: line.to.price },
          ] as never);
        }
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
      // lightweight-charts requires markers in ascending time order and
      // silently drops the whole set otherwise, which is how an overlay
      // disappears without any error to explain it.
      if (markers.length) {
        markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
        candles.setMarkers(markers as never);
      }

      // Frame the formation when there is one. fitContent shows every bar
      // passed in, which for a four-session flag means the thing the chart
      // exists to show occupies the last few pixels and is unreadable. The
      // window is padded generously to the left so the move the formation is
      // a pause in stays on screen — a flag without its pole is just a gap.
      const framed = (() => {
        if (!shape?.lines?.upper) return false;
        const startIdx = bars.findIndex((b) => b.time === shape.lines!.upper!.from.date);
        if (startIdx < 0) return false;
        const span = bars.length - startIdx;
        const from = bars[Math.max(0, startIdx - Math.max(20, span * 2))];
        if (!from) return false;
        try {
          chart.timeScale().setVisibleRange({
            from: from.time as never, to: bars[bars.length - 1].time as never,
          });
          return true;
        } catch {
          return false;
        }
      })();
      if (!framed) chart.timeScale().fitContent();
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

        const swings: { x: number; y: number; side: "upper" | "lower" }[] = [];
        for (const side of ["upper", "lower"] as const) {
          for (const point of shape?.lines?.[side]?.touches ?? []) {
            const x = scale.timeToCoordinate(point.date as never);
            const y = candles.priceToCoordinate(point.price);
            if (x === null || y === null) continue;
            swings.push({ x, y, side });
          }
        }
        setOverlay({ boxes: projected, swings, width });
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
  }, [bars, pivot, boxes, breakoutDate, flags, drawnHeight, onReady,
      movingAverages, shape]);

  return (
    <div style={{ position: "relative" }} aria-label={`${symbol} price chart`}>
      <div ref={container} style={{ width: "100%", height: drawnHeight }} />
      <svg
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
        width="100%"
        height={drawnHeight}
        aria-hidden
      >
        {/* The tops and bottoms the two trendlines were fitted through. Hollow,
            so a candle underneath still reads; offset off the extreme so the
            ring sits beside the wick rather than on it. */}
        {overlay.swings.map((swing, index) => (
          <circle
            key={`swing-${index}`}
            cx={swing.x}
            cy={swing.y + (swing.side === "upper" ? -4 : 4)}
            r={2.5}
            fill="none"
            stroke="var(--text-muted)"
            strokeWidth={1}
          />
        ))}
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
