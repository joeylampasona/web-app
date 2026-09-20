import type { Criteria } from "@/lib/types";

/**
 * How many of the published checks line up, and which.
 *
 * Deliberately not a percentage. "78% confident" asserts a probability, and
 * this site has none to offer: its own out-of-sample work found no measurable
 * edge in the structural parts of these patterns, only in relative strength.
 * A count carries the same information without the claim.
 *
 * The segments are the point. Two setups can both read "6 of 9" and be
 * completely different things — one missing its 200-day line, another missing
 * only the volume dry-up — and the tally alone hides that. The compact form
 * shows the shape; the full form names every check.
 */
export function CriteriaMeter({
  criteria, detailed = false,
}: {
  criteria: Criteria | null | undefined;
  detailed?: boolean;
}) {
  if (!criteria || criteria.total === 0) return null;
  const { met, total, checks } = criteria;

  if (!detailed) {
    return (
      <span
        className="row caption dim"
        style={{ gap: "var(--gap-xs)", alignItems: "center" }}
        title={checks.filter((c) => c.met).map((c) => c.label).join(", ")}
      >
        <span aria-hidden className="row" style={{ gap: 2 }}>
          {checks.map((check) => (
            <span
              key={check.key}
              style={{
                width: 5, height: 9, borderRadius: 1,
                background: check.met ? "var(--brand)" : "var(--border-stronger)",
              }}
            />
          ))}
        </span>
        <span className="num">{met} of {total}</span>
        <span>checks</span>
      </span>
    );
  }

  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <p className="footnote muted" style={{ margin: 0 }}>
        <span className="num">{met}</span> of <span className="num">{total}</span>{" "}
        published checks currently line up. This is a count, not a probability —
        nothing on this site measures how often a setup works.
      </p>
      <div className="stack" style={{ gap: 2 }}>
        {checks.map((check) => (
          <div key={check.key} className="row caption"
               style={{ gap: "var(--gap-sm)", alignItems: "center" }}>
            <span
              aria-hidden
              style={{
                width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                background: check.met ? "var(--gain)" : "var(--border-stronger)",
              }}
            />
            <span style={{ color: check.met ? "var(--text-primary)" : "var(--text-muted)" }}>
              {check.label}
            </span>
          </div>
        ))}
      </div>
      {total < 9 && (
        <p className="caption dim" style={{ margin: 0 }}>
          {9 - total} check{9 - total === 1 ? " is" : "s are"} not listed because
          this stock has too little history to judge {9 - total === 1 ? "it" : "them"} —
          a 200-day average needs 200 sessions. They are left out of the total
          rather than counted as failures.
        </p>
      )}
    </div>
  );
}
