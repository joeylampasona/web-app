"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useSubscription } from "@/lib/useSubscription";

/**
 * What stands where gated content would be.
 *
 * It says what is behind it and how much of it there is. A paywall that will
 * not say what it is withholding is asking to be paid on trust, and this site
 * is not in a position to ask for that — its own out-of-sample work found no
 * measurable edge in the structural half of these patterns, and it says so on
 * every screen.
 *
 * This decides what is *offered*, never what is served. The rows themselves
 * were never sent to this browser; the server would refuse them to anyone this
 * component decided to be generous to.
 */
export function Locked({
  what,
  shown,
  total,
  children,
}: {
  /** What the reader is not seeing, in plain words. */
  what: string;
  /** How much of it is on the page already. Omit when none of it is. */
  shown?: number;
  /** How much there is in total. */
  total?: number;
  children?: React.ReactNode;
}) {
  const { signedIn, ready: authReady, requireSignUp } = useAuth();
  const { ready, active } = useSubscription();

  // A subscriber who has landed here is looking at a fault, not an offer —
  // their content should have arrived. Say that, rather than inviting them to
  // buy what they have already bought.
  if (authReady && ready && active) {
    return (
      <div className="card stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">Not loaded</div>
        <p className="footnote muted" style={{ margin: 0 }}>
          Your subscription is active, but {what} did not arrive. Reloading
          usually fixes it. If it does not, the night's upload may not have run
          — the page would then be showing the free sample to everybody.
        </p>
      </div>
    );
  }

  const known = typeof shown === "number" && typeof total === "number" && total > shown;

  return (
    <div className="card stack" style={{ gap: "var(--gap-md)" }}>
      <div className="stack" style={{ gap: 4 }}>
        <div className="eyebrow">Part of a subscription</div>
        <p className="footnote muted" style={{ margin: 0 }}>
          {known
            ? `Showing ${shown!.toLocaleString()} of ${total!.toLocaleString()}. `
            : ""}
          {what} comes with a subscription.
        </p>
        {children}
      </div>

      {!authReady || !ready ? null : signedIn ? (
        <Link href="/settings" className="control primary"
              style={{ textAlign: "center" }}>
          See the plans
        </Link>
      ) : (
        <button type="button" className="control primary"
                onClick={() => requireSignUp("Subscribe to The Tape")}>
          Sign in to subscribe
        </button>
      )}

      <p className="caption dim" style={{ margin: 0 }}>
        7 days free. Your watchlist and saved screens stay yours either way.
      </p>
    </div>
  );
}
