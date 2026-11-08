import { Tooltip } from "./Tooltip";

export function MetricRow({
  label, value, help, tone,
}: {
  label: string;
  /** A node, not only a string: the "now vs pivot" row swaps in a live
   *  figure during the session and has to mark that it is delayed. */
  value: React.ReactNode;
  help: string;
  tone?: "gain" | "loss" | "flat";
}) {
  return (
    <div className="metric-row">
      <span className="row" style={{ gap: "var(--gap-sm)" }}>
        <span className="label">{label}</span>
        <Tooltip label={label} text={help} />
      </span>
      <span className={`value ${tone ?? ""}`.trim()}>{value}</span>
    </div>
  );
}

/**
 * The same reading as a tile, three to a row. Six full-width rows made a card
 * a third taller than its chart; the tiles keep every number and its help, with
 * the short label on the tile and the long one in the help's heading.
 */
export function MetricTile({
  label, short, value, help, tone,
}: {
  label: string;
  short?: string;
  value: React.ReactNode;
  help: string;
  tone?: "gain" | "loss" | "flat";
}) {
  return (
    <div className="metric-tile">
      <span className="row" style={{ gap: 4 }}>
        <span className="label" title={label}>{short ?? label}</span>
        <Tooltip label={label} text={help} />
      </span>
      <span className={`value ${tone ?? ""}`.trim()}>{value}</span>
    </div>
  );
}
