import type { Meta } from "@/lib/types";

/**
 * When the pipeline ran on the offline fixture rather than live data, say so
 * everywhere, unmissably. A demo that looks like a market is worse than no demo.
 */
export function DataBanner({ meta }: { meta: Meta | null }) {
  if (!meta || meta.data_source !== "synthetic_demo") return null;
  return (
    <div
      className="footnote"
      style={{
        background: "var(--warn-bg)", color: "var(--warn)",
        border: `0.5px solid var(--warn-border)`,
        borderRadius: "var(--radius)",
        padding: "var(--pad-sm) var(--pad-md)",
        marginBottom: "var(--gap-lg)",
      }}
      role="status"
    >
      <strong style={{ fontWeight: 500 }}>Demo data.</strong>{" "}
      {meta.data_source_note ||
        "Prices here are a deterministic fixture, not real market data."}
    </div>
  );
}

export function NoData() {
  return (
    <div className="page">
      <div className="card stack">
        <div className="eyebrow">Nothing published yet</div>
        <h2>The pipeline has not written any data</h2>
        <p className="muted footnote" style={{ margin: 0 }}>
          Run <code className="mono">python -m cli universe --refresh</code> and then{" "}
          <code className="mono">python -m cli publish</code> from the repository root.
          The web layer reads the <code className="mono">out/</code> tree those commands
          write and never queries a database.
        </p>
      </div>
    </div>
  );
}
