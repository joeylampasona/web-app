import { longDate } from "@/lib/format";

export function FreshnessPill({ count, asOf }: { count: number; asOf: string }) {
  return (
    <div className="row wrap" style={{ gap: "var(--gap-sm)", marginBottom: "var(--gap-md)" }}>
      <span
        className="badge"
        style={{
          background: "var(--surface-2)", color: "var(--text-primary)",
          borderRadius: "var(--radius-pill)", padding: "4px var(--pad-md)",
        }}
      >
        <span className="num">{count}</span>&nbsp;broke out market-wide
      </span>
      <span className="caption dim">Updated · {longDate(asOf)}</span>
    </div>
  );
}
