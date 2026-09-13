"use client";

import { compactMoney, rsText } from "@/lib/format";
import type { GroupRow } from "@/lib/types";
import { PriceChange } from "./PriceChange";
import { StageBadge } from "./Badges";
import { TickerLink } from "./StockDrawer";

/**
 * The brief leaves this layout open. It is the simplest thing that answers the
 * questions the map and the rotation scatter raise when you drill in: how strong
 * is the group, which way is it moving, and who is in it.
 */
export function GroupDetail({ group }: { group: GroupRow }) {
  const members = group.members_detail ?? [];
  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <div className="grid-2">
        <Stat label="RS rating" value={group.rs_rating === null ? "—" : String(group.rs_rating)} />
        <Stat label="Average member RS" value={group.avg_member_rs.toFixed(1)} />
        <Stat label="Leaders (RS 80+)" value={String(group.leaders)} />
        <Stat label="Fresh breakouts" value={String(group.fresh_breakouts)} />
      </div>

      <div className="card">
        <div className="footnote muted">RS change</div>
        <div className="row wrap" style={{ gap: "var(--pad-lg)", marginTop: "var(--gap-sm)" }}>
          {([["1 week", group.rs_change_w1], ["1 month", group.rs_change_m1],
             ["3 months", group.rs_change_m3]] as const).map(([label, value]) => (
            <span key={label}>
              <span className="caption dim">{label} </span>
              <PriceChange value={value} digits={1} unit=" pts" />
            </span>
          ))}
        </div>
        <div className="caption dim" style={{ marginTop: "var(--gap-sm)" }}>
          {group.members} names · {compactMoney(group.market_value)} combined market value
        </div>
      </div>

      <section>
        <div className="eyebrow">Members</div>
        <div className="scroll-x card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr><th>Ticker</th><th>RS</th><th>Δ 1m</th><th>On a screen</th></tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.symbol}>
                  <td className="text">
                    <TickerLink symbol={member.symbol}>
                      <span className="mono">{member.symbol}</span>{" "}
                      <span className="caption dim">{member.name}</span>
                    </TickerLink>
                  </td>
                  <td>{rsText(member.rs_rating)}</td>
                  <td><PriceChange value={member.rs_change_m1} digits={0} unit="" /></td>
                  <td className="text">
                    {member.stage ? <StageBadge stage={member.stage} /> :
                      <span className="caption dim">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="footnote muted">{label}</div>
      <div className="num" style={{ fontSize: "var(--size-h2)" }}>{value}</div>
    </div>
  );
}
