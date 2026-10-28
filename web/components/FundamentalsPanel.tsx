import { compactMoney } from "@/lib/format";
import type { Fundamentals } from "@/lib/types";

/**
 * The business behind the chart, from the company's own filings.
 *
 * Trailing twelve months, summed from the last four quarters in its XBRL
 * filings; growth is the latest quarter against the same quarter a year
 * earlier. Context for a chart page, not a screen: nothing here decides
 * whether a stock is on one. Net debt is deliberately left out. Companies tag
 * debt in too many ways (a carmaker's finance arm, an insurer's float) for one
 * reading to be safe, and a wrong net debt is worse than none.
 */
function pct(v: number | null | undefined, signed = false): string {
  if (v == null) return "—";
  return `${signed && v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function times(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v < 10 ? v.toFixed(2) : v.toFixed(1)}×`;
}

function tone(v: number | null | undefined): string | undefined {
  if (v == null || v === 0) return undefined;
  return v > 0 ? "var(--gain)" : "var(--loss)";
}

function Cell({ label, value, note, color }: {
  label: string; value: string; note?: string; color?: string;
}) {
  return (
    <div className="card" style={{ padding: "var(--pad-sm) var(--pad-md)" }}>
      <div className="caption muted">{label}</div>
      <div className="num" style={{ fontSize: "var(--size-h3)", color }}>{value}</div>
      {note && <div className="caption dim">{note}</div>}
    </div>
  );
}

function day(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}

export function FundamentalsPanel({ f }: { f: Fundamentals | null | undefined }) {
  if (!f) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        No figures in US GAAP filings for this company. Most foreign listings
        report under international standards, which this does not read.
      </p>
    );
  }
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="grid-3">
        <Cell label="Revenue" value={compactMoney(f.revenue_ttm)}
              note={f.revenue_growth == null ? undefined : `${pct(f.revenue_growth, true)} year on year`} />
        <Cell label="Operating margin" value={pct(f.op_margin)}
              note={f.gross_margin == null ? undefined : `gross ${pct(f.gross_margin)}`}
              color={tone(f.op_margin)} />
        <Cell label="Net margin" value={pct(f.net_margin)} color={tone(f.net_margin)} />
        <Cell label="Free cash flow" value={f.fcf_ttm == null ? "—" : compactMoney(f.fcf_ttm)}
              note={f.fcf_yield == null ? undefined : `${pct(f.fcf_yield)} of market cap`}
              color={tone(f.fcf_ttm)} />
        <Cell label="Price to sales" value={times(f.price_to_sales)} />
        <Cell label="Price to earnings" value={times(f.price_to_earnings)}
              note={f.price_to_earnings == null && (f.net_income_ttm ?? 0) <= 0
                ? "not meaningful on a loss" : undefined} />
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        Twelve months to {day(f.period_end)}, the four latest quarters in the
        company&rsquo;s SEC filings, with the fiscal fourth quarter worked out
        from the annual report. Revenue growth is the latest quarter against
        the same quarter a year earlier.
      </p>
    </div>
  );
}
