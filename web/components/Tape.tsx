"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuote, useQuotesMeta } from "@/lib/useQuotes";
import { useWatchlist } from "@/lib/useWatchlist";
import type { TapeData, TapeItem } from "@/lib/tape";

/**
 * The tape strip. One line, scrolls sideways on a phone, never wraps.
 *
 * A quoted symbol shows the delayed price when there is one, and the strip
 * says which it is at the end: a price with no time on it invites the reader
 * to assume it is current.
 */
function Quoted({ item }: { item: TapeItem }) {
  const quote = useQuote(item.symbol);
  const live = Boolean(quote && quote.last > 0);
  const value = live ? quote!.last.toFixed(2) : item.value;
  const change = live ? quote!.change_pct : item.changePct;
  return (
    <>
      <span className="k">{item.label}</span>{" "}
      <span className="v">{value}</span>
      {change != null && (
        <span className={change >= 0 ? "up" : "down"}>
          {" "}{change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
        </span>
      )}
    </>
  );
}

function Fact({ item }: { item: TapeItem }) {
  return (
    <>
      <span className="k">{item.label}</span>{" "}
      <span className="v">{item.value}</span>
      {item.detail && <span className={item.tone ?? ""}>{" "}{item.detail}</span>}
    </>
  );
}

interface WatchRow { symbol: string; close: number | null; change_pct: number | null; rs_rating: number | null }
/** How many of a reader's names the strip carries before the market's own. */
const WATCH_MAX = 14;

/** A signed-in reader's own names: last close and move, the delayed quote
 *  laid over it when the sweep covers the name. */
function Watched({ row }: { row: WatchRow }) {
  const quote = useQuote(row.symbol);
  const live = Boolean(quote && quote.last > 0);
  const value = live ? quote!.last : row.close;
  const change = live ? quote!.change_pct : row.change_pct;
  return (
    <Link href={`/stocks/${row.symbol}`}>
      <span className="v">{row.symbol}</span>
      {value != null ? <> {value.toFixed(2)}</> : row.rs_rating != null ? <span className="k"> RS {row.rs_rating}</span> : null}
      {change != null && (
        <span className={change >= 0 ? "up" : "down"}>
          {" "}{change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
        </span>
      )}
    </Link>
  );
}

function useWatchRows(): WatchRow[] {
  const { signedIn, ready, symbols } = useWatchlist();
  const [rows, setRows] = useState<WatchRow[]>([]);
  const key = signedIn && ready ? symbols.slice(0, WATCH_MAX).join(",") : "";
  useEffect(() => {
    if (!key) { setRows([]); return; }
    let alive = true;
    fetch(`/api/tape?symbols=${encodeURIComponent(key)}`)
      .then((r) => (r.ok ? r.json() : { rows: [] }))
      .then((body) => { if (alive) setRows(Array.isArray(body?.rows) ? body.rows : []); })
      .catch(() => { if (alive) setRows([]); });
    return () => { alive = false; };
  }, [key]);
  return rows;
}

export function Tape({ data }: { data: TapeData }) {
  const watched = useWatchRows();
  const { liveAt, liveSymbols, ready } = useQuotesMeta();
  if (!data.items.length) return null;
  const quoted = data.items.filter((i) => i.symbol).map((i) => i.symbol!);
  const covered = quoted.length > 0 && quoted.every((s) => liveSymbols.includes(s));
  const stamp = ready && liveAt && covered
    ? `Prices delayed, read ${new Date(liveAt).toLocaleTimeString("en-US",
        { hour: "numeric", minute: "2-digit" })}`
    : "Prices at the last close";
  return (
    <div className="tape" role="region" aria-label="The day in numbers">
      {data.items.filter((item) => item.symbol).map((item) => (
        <Link key={item.key} href={item.href ?? "/"}><Quoted item={item} /></Link>
      ))}
      {/* A signed-in reader's own names come before the market's counts:
          they are what that reader opened the page to check. */}
      {watched.length > 0 && (
        <>
          <Link href="/watchlist" className="tape-tag">Your list</Link>
          {watched.map((row) => <Watched key={row.symbol} row={row} />)}
          <span className="tape-tag" aria-hidden>Market</span>
        </>
      )}
      {data.items.filter((item) => !item.symbol).map((item) => (
        item.href
          ? <Link key={item.key} href={item.href}><Fact item={item} /></Link>
          : <span key={item.key}><Fact item={item} /></span>
      ))}
      <span className="k">{stamp}</span>
    </div>
  );
}
