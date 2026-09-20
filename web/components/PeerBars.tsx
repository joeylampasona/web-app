import Link from "next/link";
import { isRanked, rsText } from "@/lib/format";
import type { Rating } from "@/lib/types";

export interface Peer { symbol: string; name: string; rs_rating: Rating }

/**
 * Peers with their relative strength drawn, not just printed.
 *
 * The list was ten rows of "SYMBOL  87" — technically complete, and unreadable
 * as a group. The question a reader actually brings to a peer list is "is this
 * name the strong one here or the weak one", which is a comparison, and a
 * column of digits makes you do the comparison in your head ten times.
 *
 * The bar is the percentile itself, so it needs no scale: 99 is the full width
 * by definition. The subject stock is marked, because "how does it rank among
 * its peers" is the reason the list is on its page.
 */
/* The neutral fill is --text-muted, not --border-stronger. The track is a
   border colour, and painting the fill in another border colour makes the two
   the same swatch in light mode (#B8B6AE on #B8B6AE): every row renders as one
   uniform pill and the bar carries no information at all. */
function barColor(rating: number, isSelf: boolean): string {
  if (isSelf) return "var(--brand-ink)";
  if (rating >= 90) return "var(--gain)";
  if (rating <= 30) return "var(--loss)";
  return "var(--text-muted)";
}

export function PeerBars({ peers, self, empty }: {
  peers: Peer[];
  /** The stock whose page this is, so its own row can be marked. It may not
   *  be in the list at all — the publisher excludes it from some groups. */
  self: string;
  empty: string;
}) {
  if (peers.length === 0) return <span className="caption dim">{empty}</span>;
  return (
    <div className="stack" style={{ gap: 5 }}>
      {peers.map((peer) => {
        // Aliased through a local: `isRanked` narrows its argument, and the
        // narrowing does not survive a property access on a mutable field.
        const rs = peer.rs_rating;
        const ranked = isRanked(rs);
        const isSelf = peer.symbol === self;
        const width = ranked ? Math.max(2, Math.min(99, rs)) : 0;
        return (
          <Link
            key={peer.symbol}
            href={`/stocks/${peer.symbol}`}
            className="row"
            style={{ gap: "var(--gap-sm)", alignItems: "center" }}
            title={`${peer.name} — relative strength ${rsText(peer.rs_rating)}`}
          >
            <span className="mono footnote"
                  style={{ width: "4.2em", flexShrink: 0,
                           fontWeight: isSelf ? 600 : 400,
                           color: isSelf ? "var(--brand-ink)" : "var(--text-primary)" }}>
              {peer.symbol}
            </span>
            {/* alignItems: stretch, not the .row default of center — a centred
                flex row gives a child with no content zero height, which is how
                a bar like this silently renders as nothing. */}
            <span
              aria-hidden
              style={{
                display: "flex", alignItems: "stretch", flex: 1, height: 6,
                borderRadius: 3, overflow: "hidden",
                background: "var(--border-strong)", opacity: ranked ? 1 : 0.4,
              }}
            >
              <span style={{
                width: `${width}%`, height: "100%",
                background: ranked ? barColor(rs, isSelf) : "transparent",
              }} />
            </span>
            <span className="num caption dim" style={{ width: "2.2em", textAlign: "right" }}>
              {ranked ? rs : "—"}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
