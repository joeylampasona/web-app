"use client";

import Link from "next/link";
import { useQuote, useQuotesMeta } from "@/lib/useQuotes";
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

export function Tape({ data }: { data: TapeData }) {
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
      {data.items.map((item) => {
        const body = item.symbol ? <Quoted item={item} /> : <Fact item={item} />;
        return item.href
          ? <Link key={item.key} href={item.href}>{body}</Link>
          : <span key={item.key}>{body}</span>;
      })}
      <span className="k">{stamp}</span>
    </div>
  );
}
