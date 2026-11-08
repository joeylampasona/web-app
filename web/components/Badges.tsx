import { CopyKey, copy } from "@/lib/copy";
import { Tooltip } from "./Tooltip";

/**
 * Cautions use --warn, never --brand. A caution is not chrome, and amber is
 * already spent on the pivot.
 */
const FLAGS: Record<string, { glyph: string; label: string }> = {
  squat: { glyph: "⚑", label: "squat" },
  failed_poke: { glyph: "×", label: "failed poke" },
  // Its own glyph, not just its own colour — gain and loss are never colour
  // alone here and neither is a caution.
  cooling: { glyph: "↘", label: "cooling" },
};

export function FlagBadge({ flag }: { flag: string }) {
  const { glyph, label } = FLAGS[flag] ?? { glyph: "·", label: flag.replace(/_/g, " ") };
  return (
    <span className="badge badge--warn">
      <span aria-hidden>{glyph}</span>
      {label}
      <Tooltip label={label} text={copy(`flag.${flag}` as CopyKey)} />
    </span>
  );
}

export function EarningsBadge({ days }: { days: number }) {
  return (
    <span className="badge badge--warn">
      <span aria-hidden>{"⚡"}</span>
      earnings in {days}d
    </span>
  );
}

function ordinal(n: number): string {
  const tail = n % 100 >= 11 && n % 100 <= 13 ? "th"
    : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${tail}`;
}

/**
 * How long a name has been on this screen. Grey, not a colour: a name that
 * keeps qualifying is more of the same evidence, not a stronger signal.
 * Nothing on the first night counted, when every name would read as new.
 */
export function NightsBadge({ nights }: {
  nights: { run: number; of: number; window: number } | null | undefined;
}) {
  if (!nights || nights.window < 2) return null;
  const text = nights.run >= 2 ? `${ordinal(nights.run)} night running`
    : nights.of > 1 ? `${nights.of} of ${nights.window} nights`
    : "new to the screen";
  return (
    <span className="badge" title={`On this screen ${nights.of} of the last ${nights.window} sessions scanned, ${nights.run} in a row ending tonight.`}>
      {text}
    </span>
  );
}

export function ProvisionalBadge({ title }: { title?: string }) {
  return (
    <span className="badge badge--provisional" title={title}>
      provisional
    </span>
  );
}

export function QuadrantBadge({ quadrant }: { quadrant: string | null }) {
  if (!quadrant) return null;
  const labels: Record<string, string> = {
    powering_up: "Powering up", turning_up: "Turning up",
    cooling_off: "Cooling off", falling_back: "Falling back",
  };
  const colours: Record<string, string> = {
    powering_up: "var(--q-powering)", turning_up: "var(--q-turning)",
    cooling_off: "var(--q-cooling)", falling_back: "var(--q-falling)",
  };
  return (
    <span
      className="badge"
      style={{ color: colours[quadrant], background: "var(--surface-2)" }}
    >
      {labels[quadrant] ?? quadrant}
    </span>
  );
}

const STAGE_COLOURS: Record<string, string> = {
  forming: "var(--stage-forming)",
  fresh_breakout: "var(--stage-breakout)",
  climbing: "var(--stage-climbing)",
  played_out: "var(--stage-playedout)",
};

export function StageBadge({ stage, label }: { stage: string; label?: string }) {
  return (
    <span className="badge" style={{ color: STAGE_COLOURS[stage] ?? "var(--text-secondary)" }}>
      {label ?? stage.replace("_", " ")}
    </span>
  );
}

export { STAGE_COLOURS };
