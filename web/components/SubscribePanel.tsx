"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useSubscription } from "@/lib/useSubscription";
import { longDate } from "@/lib/format";

const MONTHLY = "$4.99";
const ANNUAL = "$50";
const TRIAL_DAYS = 7;

/**
 * The two plans, and what happens when you pick one.
 *
 * Deliberately plain about what is being bought. This site's own out-of-sample
 * work found no measurable edge in the structural parts of these patterns,
 * only in relative strength, and it says so on every screen — so a subscribe
 * panel that implied otherwise would be contradicting the product in the one
 * place where money changes hands.
 */
export function SubscribePanel() {
  const { signedIn, ready: authReady, requireSignUp } = useAuth();
  const { ready, active, status, trialEnd, currentPeriodEnd, cancelAtPeriodEnd,
          comped, startCheckout } = useSubscription();
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  if (!authReady || !ready) return null;

  if (comped) {
    return (
      <div className="card stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">Your access</div>
        <p className="footnote" style={{ margin: 0 }}>
          You have permanent access to everything. Nothing to pay and nothing
          to renew.
        </p>
      </div>
    );
  }

  if (active) {
    return (
      <div className="card stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">Your subscription</div>
        <p className="footnote" style={{ margin: 0 }}>
          {status === "trialing"
            ? `You are on the free trial${trialEnd ? `, until ${longDate(trialEnd.slice(0, 10))}` : ""}.`
            : status === "past_due"
              ? "Your last payment did not go through. Access continues while "
                + "Stripe retries it."
              : "Active."}
        </p>
        {currentPeriodEnd && (
          <p className="caption dim" style={{ margin: 0 }}>
            {cancelAtPeriodEnd
              ? `Ends ${longDate(currentPeriodEnd.slice(0, 10))} and will not renew.`
              : `Renews ${longDate(currentPeriodEnd.slice(0, 10))}.`}
          </p>
        )}
      </div>
    );
  }

  const choose = async (plan: "monthly" | "annual") => {
    if (!signedIn) {
      requireSignUp("Subscribe to The Tape");
      return;
    }
    setProblem(null);
    setBusy(plan);
    let url: string | null = null;
    try {
      url = await startCheckout(plan);
    } catch (failure) {
      setBusy(null);
      // The reason, not a shrug. These are configuration faults and they are
      // read by whoever is setting this up, which right now is the only
      // person who can see them.
      setProblem(failure instanceof Error
        ? `Could not start checkout — ${failure.message}`
        : "Could not start checkout.");
      return;
    }
    if (!url) {
      setBusy(null);
      setProblem("Could not start checkout. Try again in a moment.");
      return;
    }
    window.location.href = url;
  };

  return (
    <div className="card stack" style={{ gap: "var(--gap-md)" }}>
      <div>
        <div className="eyebrow">Subscribe</div>
        <p className="footnote muted" style={{ margin: 0 }}>
          Everything here shows you some of itself for nothing: ten names per
          stage on every screen, the five deepest option books, the benchmark's
          seasonal grid, what analysts rate a company, the most recent base it
          built. A subscription is the rest of each — the full lists, every
          strike, the sector grids, the price targets and estimates, and every
          base on one chart.
        </p>
      </div>

      <div className="grid-2">
        <button type="button" className="control stack"
                style={{ height: "auto", padding: "var(--pad-md)", gap: 2 }}
                disabled={busy !== null} onClick={() => choose("monthly")}>
          <span className="num" style={{ fontSize: "var(--size-h3)" }}>{MONTHLY}</span>
          <span className="caption dim">a month</span>
        </button>
        <button type="button" className="control primary stack"
                style={{ height: "auto", padding: "var(--pad-md)", gap: 2 }}
                disabled={busy !== null} onClick={() => choose("annual")}>
          <span className="num" style={{ fontSize: "var(--size-h3)" }}>{ANNUAL}</span>
          <span className="caption">a year · two months free</span>
        </button>
      </div>

      <p className="caption dim" style={{ margin: 0 }}>
        {TRIAL_DAYS} days free first. Cancel any time, in Stripe, and keep
        access until the period you have paid for ends. Your watchlist and
        saved screens stay yours whether you subscribe or not.
      </p>

      {/* The figures above are the price, not the charge. Stripe adds sales
          tax from the buyer's address, so the first real payment can be a few
          percent more than the number they pressed — a small surprise, but a
          surprise about money, which is the kind people remember. */}
      <p className="caption dim" style={{ margin: 0 }}>
        Tax is added where it applies, worked out from your address, so the
        charge can come to a little more than the figure above.
      </p>

      {busy && <p className="caption dim" style={{ margin: 0 }}>Opening Stripe…</p>}
      {problem && (
        <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>{problem}</p>
      )}
    </div>
  );
}
