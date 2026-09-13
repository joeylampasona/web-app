import { CopyKey, copy } from "@/lib/copy";
import { Tooltip } from "./Tooltip";

/**
 * Cautions use --warn, never --brand. A caution is not chrome, and amber is
 * already spent on the pivot.
 */
export function FlagBadge({ flag }: { flag: string }) {
  const glyph = flag === "squat" ? "⚑" : "×";
  const label = flag === "squat" ? "squat" : "failed poke";
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
