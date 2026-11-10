import Link from "next/link";
import { screenClass } from "@/lib/screenColour";
import { ScreenGlyph } from "./ScreenGlyph";

/**
 * Every screen's live stages on one shared scale.
 *
 * Each screen used to fill its own card, so a screen with twelve names looked
 * as full as one with six hundred. Here every bar is measured against the
 * busiest screen: a long bar means more names. Grey is forming, the
 * highlighter is a fresh breakout, ink is climbing; the counts beside the bar
 * say the same in numbers.
 */
interface ScreenMeta {
  key: string; name: string; total: number; stages: Record<string, number>;
}

export function ScreensScale({ screens }: { screens: ScreenMeta[] }) {
  const rows = screens.map((s) => ({
    ...s,
    forming: s.stages.forming ?? 0,
    fresh: s.stages.fresh_breakout ?? 0,
    climbing: s.stages.climbing ?? 0,
  }));
  const max = Math.max(...rows.map((r) => r.forming + r.fresh + r.climbing), 1);
  const half = Math.ceil(rows.length / 2);
  const w = (n: number) => `${(n / max) * 100}%`;
  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="scale-cols">
        {[rows.slice(0, half), rows.slice(half)].map((col, i) => (
          <div key={i}>
            {col.map((s) => (
              <Link key={s.key} href={`/screens/${s.key}`} className="scale-row"
                    aria-label={`${s.name}: ${s.forming} forming, ${s.fresh} fresh breakouts, ${s.climbing} climbing`}>
                <span className={`screen-icon ${screenClass(s.key)}`} aria-hidden>
                  <ScreenGlyph href={`/screens/${s.key}`} />
                </span>
                <span className="label-caps" style={{ textTransform: "none", fontSize: 15 }}>{s.name}</span>
                <span className="scale-bar" aria-hidden>
                  {s.forming > 0 && <span className="f" style={{ width: w(s.forming) }} />}
                  {s.fresh > 0 && <span className="b" style={{ width: w(s.fresh) }} />}
                  {s.climbing > 0 && <span className="c" style={{ width: w(s.climbing) }} />}
                </span>
                <span className="num caption" style={{ textAlign: "right" }}>
                  {s.forming} · {s.fresh} · {s.climbing}
                </span>
              </Link>
            ))}
          </div>
        ))}
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        <span className="scale-key" style={{ background: "var(--border-strong)" }} aria-hidden /> forming
        {" · "}
        <span className="scale-key" style={{ background: "var(--brand)" }} aria-hidden /> fresh breakout
        {" · "}
        <span className="scale-key" style={{ background: "var(--text-primary)" }} aria-hidden /> climbing.
        Every bar shares one scale, so a long bar means more names, not a
        fuller screen.
      </p>
    </div>
  );
}
