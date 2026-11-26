import type { DealerGammaFile, DealerGammaRow } from "@/lib/types";
import { CarriedOver, shortDay } from "./CarriedOver";

/**
 * Dealer gamma for the index and the sector funds, from the Market Desk.
 *
 * A different reading from the board beneath it, and the difference is the
 * whole reason for the footnote. The board says where a company's option
 * book anchors gamma, which is arithmetic over open interest and assumes
 * nothing. This table signs it: calls positive, puts negative, on the
 * convention that dealers are long the calls and short the puts. Nobody
 * publishes who holds which side. It is printed because it is what people
 * mean by "gamma" for the index, and labelled as the desk's reading on an
 * assumption rather than as a fact about anyone's book.
 *
 * It arrives with its own date, and on a night that date is older than the
 * edition it says so instead of sitting beside tonight's prices as though it
 * were theirs.
 */
function dollars(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const n = Math.abs(value);
  if (n >= 1e9) return `${sign}$${(n / 1e9).toFixed(1)}bn`;
  if (n >= 1e6) return `${sign}$${(n / 1e6).toFixed(1)}m`;
  if (n >= 1e3) return `${sign}$${(n / 1e3).toFixed(0)}k`;
  return `${sign}$${n.toFixed(0)}`;
}

function level(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: value >= 1000 ? 0 : 2,
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  });
}

function Rows({ rows }: { rows: DealerGammaRow[] }) {
  return (
    <>
      {rows.map((row) => (
        <tr key={row.symbol}>
          <td className="text">
            <div>{row.label && row.label !== row.symbol ? row.label : row.symbol}</div>
            {row.label && row.label !== row.symbol && (
              <div className="caption dim mono">{row.symbol}</div>
            )}
          </td>
          <td className="num">{level(row.spot)}</td>
          <td className={`num ${row.net == null ? "" : row.net > 0 ? "gain" : row.net < 0 ? "loss" : ""}`}
              style={{ fontWeight: 600, whiteSpace: "nowrap" }}>
            {dollars(row.net)}
          </td>
          <td className="text">{row.regime ?? "—"}</td>
          <td className="num" style={{ whiteSpace: "nowrap" }}>
            {row.flip == null ? <span className="dim">none in the chain</span> : (
              <>
                {level(row.flip)}
                {row.flip_pct != null && (
                  <span className="caption dim">
                    {" "}{row.flip_pct > 0 ? "+" : ""}{row.flip_pct.toFixed(1)}%
                  </span>
                )}
              </>
            )}
          </td>
          <td className="num">{level(row.call_wall)}</td>
          <td className="num">{level(row.put_wall)}</td>
        </tr>
      ))}
    </>
  );
}

export function DealerGamma({ file }: { file: DealerGammaFile | null }) {
  if (!file) return null;
  const index = file.index ?? [];
  const sectors = file.sectors ?? [];
  if (index.length + sectors.length === 0) return null;
  const read = shortDay(file.read_on);

  return (
    <section className="stack" style={{ gap: "var(--gap-sm)", marginTop: "var(--gap-lg)" }}>
      <div className="eyebrow">Index and sectors</div>
      {file.stale && (
        <p className="footnote book-note" style={{ margin: 0 }}>
          <CarriedOver title="The Market Desk has not read these option chains since that night.">
            {read ? `Read ${read}` : "Earlier read"}
          </CarriedOver>{" "}
          These chains were last read {read ? `on ${read}` : "on an earlier night"}. The
          levels and the spot beside them are from that night, not from this edition.
        </p>
      )}
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th className="text">Market</th>
              <th>Spot</th>
              <th>Net per 1%</th>
              <th className="text">Regime</th>
              <th>Flip</th>
              <th>Call wall</th>
              <th>Put wall</th>
            </tr>
          </thead>
          <tbody>
            <Rows rows={index} />
            {index.length > 0 && sectors.length > 0 && (
              <tr>
                <td className="text label-caps" colSpan={7}
                    style={{ color: "var(--text-muted)", paddingTop: "var(--gap-md)" }}>
                  Sector funds
                </td>
              </tr>
            )}
            <Rows rows={sectors} />
          </tbody>
        </table>
      </div>
      <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
        The Market Desk&apos;s reading{!file.stale && read ? `, chains read ${read}` : ""}, not a
        measurement. Net is dollar gamma per 1% move with calls counted positive
        and puts negative, which assumes dealers are long the calls and short
        the puts. Open interest says how many contracts exist, not who holds
        which side. On that assumption a positive net damps moves and a negative
        one feeds them, the flip is where the signed total crosses zero, and the
        walls are the strikes holding the most call and put gamma.
      </p>
    </section>
  );
}
