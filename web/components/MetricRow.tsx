import { Tooltip } from "./Tooltip";

export function MetricRow({
  label, value, help, tone,
}: {
  label: string;
  value: string;
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
