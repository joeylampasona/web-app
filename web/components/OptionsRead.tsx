import type { OptionsRead as Read } from "@/lib/types";
import { ReadOn, shortDay } from "./CarriedOver";

/**
 * The Market Desk's read of one company's option chain.
 *
 * The desk reads about seventy chains a night: the names its brief ranked,
 * the week's reporters, a few index funds. For those it sends the thirty-day
 * implied volatility, the move the at-the-money straddle prices, how puts
 * and calls split, and where the open interest is thickest. A company it did
 * not read has no card here, which is most of them and says nothing about
 * the company.
 *
 * Kept apart from this site's own gamma panel on purpose. That one is built
 * from the whole cleared book and reports concentration. This is the desk's
 * summary, with the desk's definitions, and each line says what it measures.
 */
function strike(v: number): string {
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function away(v: number | null | undefined): string {
  if (v == null) return "";
  return ` (${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}% from the price)`;
}

function day(iso: string | null | undefined): string | null {
  return shortDay(iso);
}

export function OptionsRead({ read }: { read: Read | null | undefined }) {
  if (!read) return null;
  const has = (v: number | null | undefined): v is number => v != null && Number.isFinite(v);
  const lines = [read.iv30, read.exp_move_pct, read.pc_oi, read.pc_vol,
                 read.call_wall, read.put_wall, read.max_pain].some(has);
  if (!lines) return null;
  const ranked = has(read.iv_rank);
  const readOn = day(read.d);

  return (
    <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
      {read.stale && (
        <p className="footnote book-note" style={{ margin: 0 }}>
          <ReadOn day={read.d} about="this edition" />{" "}
          The Market Desk last read this chain{readOn ? ` on ${readOn}` : " on an earlier night"}.
          The figures below are from that night.
        </p>
      )}
      {has(read.iv30) && (
        <p className="footnote" style={{ margin: 0 }}>
          Implied volatility over thirty days {read.stale ? "was" : "is"}{" "}
          <strong className="num">{read.iv30.toFixed(1)}%</strong>
          {ranked ? (
            <>, which ranks <strong className="num">{Math.round(read.iv_rank as number)}</strong> of
              100 between the lowest and highest of the desk&rsquo;s
              {has(read.iv_days) ? ` ${read.iv_days}` : ""} stored reads.</>
          ) : (
            <>. <span className="dim">A rank follows after 20 reads
              {has(read.iv_days) ? ` (${read.iv_days} so far)` : ""}.</span></>
          )}
        </p>
      )}
      {has(read.exp_move_pct) && (
        <p className="footnote" style={{ margin: 0 }}>
          Options {read.stale ? "priced" : "price"} a{" "}
          <strong className="num">±{read.exp_move_pct.toFixed(1)}%</strong> move
          {day(read.exp_move_expiry) ? <> by {day(read.exp_move_expiry)}</> : null}: the
          at-the-money straddle at that expiry, as a share of the price.
        </p>
      )}
      {(has(read.pc_oi) || has(read.pc_vol)) && (
        <p className="footnote" style={{ margin: 0 }}>
          Puts to calls:{" "}
          {has(read.pc_oi) && <><strong className="num">{read.pc_oi.toFixed(2)}</strong> by open interest</>}
          {has(read.pc_oi) && has(read.pc_vol) && ", "}
          {has(read.pc_vol) && <><strong className="num">{read.pc_vol.toFixed(2)}</strong> by that session&rsquo;s volume</>}.
          Above one is more puts than calls.
        </p>
      )}
      {(has(read.call_wall) || has(read.put_wall) || has(read.max_pain)) && (
        <p className="footnote" style={{ margin: 0 }}>
          {has(read.call_wall) && (
            <>The most call open interest above the price sits at{" "}
              <strong className="num">{strike(read.call_wall)}</strong>{away(read.call_wall_pct)}. </>
          )}
          {has(read.put_wall) && (
            <>The most put open interest below it sits at{" "}
              <strong className="num">{strike(read.put_wall)}</strong>{away(read.put_wall_pct)}. </>
          )}
          {has(read.max_pain) && (
            <>Max pain, the strike where the most options would expire worthless
              at the next monthly expiry, is <strong className="num">{strike(read.max_pain)}</strong>.</>
          )}
        </p>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        From the Market Desk&rsquo;s chain read{readOn ? ` on ${readOn}` : ""}: open
        interest from the clearing house, quotes from Yahoo. A reading of the
        option book, not a call on the stock.
        {ranked && (
          <> The desk changed how it computes thirty-day implied volatility on
            Nov 26, 2026, so the rank mixes two calculations until its window
            of stored reads turns over.</>
        )}
      </p>
    </div>
  );
}
