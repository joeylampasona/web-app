"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./auth";
import { client } from "./supabase";

/**
 * Whether the reader is paid up, and how to become so.
 *
 * The answer comes from the database, never from anything the browser could
 * set for itself. The row is readable only by its owner and writable only by
 * Stripe's webhook, so the worst an edited client can do here is lie to its
 * own user about what they have bought — which changes nothing about what the
 * server will hand over.
 *
 * That matters because this hook must never be the thing that guards content.
 * It decides what the interface *offers*; the database decides what arrives.
 */
export type SubscriptionState = {
  /** False until the first read resolves, so nothing flickers between
   *  "subscribe" and "you already have this". */
  ready: boolean;
  active: boolean;
  status: string | null;
  trialEnd: string | null;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  /** Access granted by hand, with no payment behind it. Kept separate from
   *  `status`, which is Stripe's word and gets overwritten on every webhook —
   *  a comp written into that column would last until the next event. */
  comped: boolean;
};

const EMPTY: SubscriptionState = {
  ready: false, active: false, status: null,
  trialEnd: null, currentPeriodEnd: null, cancelAtPeriodEnd: false,
  comped: false,
};

// The same set the database's is_subscriber() accepts. Kept deliberately
// identical: an interface that disagrees with the policy would either offer a
// subscriber the chance to buy what they have, or show a lapsed one a section
// that then comes back empty.
const LIVE = new Set(["trialing", "active", "past_due"]);

export function useSubscription(): SubscriptionState & {
  refresh: () => void;
  startCheckout: (plan: "monthly" | "annual") => Promise<string | null>;
} {
  const { signedIn, ready: authReady } = useAuth();
  const [state, setState] = useState<SubscriptionState>(EMPTY);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!authReady) return;
    if (!signedIn) {
      setState({ ...EMPTY, ready: true });
      return;
    }
    const supabase = client();
    if (!supabase) {
      setState({ ...EMPTY, ready: true });
      return;
    }
    let alive = true;
    (async () => {
      const { data } = await supabase
        .from("subscriptions")
        .select("status, trial_end, current_period_end, cancel_at_period_end, comped")
        .maybeSingle();
      if (!alive) return;
      const status = data?.status ?? null;
      const ends = data?.current_period_end ?? null;
      const comped = Boolean(data?.comped);
      // A period that has already ended means Stripe has told us nothing since
      // it lapsed. Treat silence as expired, exactly as the policy does.
      const current = !ends || new Date(ends).getTime() > Date.now();
      setState({
        ready: true,
        // Same disjunction as is_subscriber(), in the same order. If these two
        // ever disagree the interface offers a subscription to somebody who
        // already has access, or hides a section that then arrives anyway.
        active: comped || Boolean(status && LIVE.has(status) && current),
        status,
        trialEnd: data?.trial_end ?? null,
        currentPeriodEnd: ends,
        cancelAtPeriodEnd: Boolean(data?.cancel_at_period_end),
        comped,
      });
    })();
    return () => { alive = false; };
  }, [signedIn, authReady, tick]);

  const refresh = useCallback(() => setTick((n) => n + 1), []);

  /** Ask the server for a Stripe Checkout URL. Returns null on failure, and
   *  the caller shows a message: a dead button is worse than a refusal. */
  const startCheckout = useCallback(async (plan: "monthly" | "annual") => {
    const supabase = client();
    if (!supabase) return null;
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    try {
      const response = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // The server identifies the buyer from this token and never from
          // the body, so there is nothing here worth tampering with.
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ plan }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        // Carried back so the panel can say what went wrong. One message for
        // every cause meant a misconfigured price and a signed-out reader
        // looked identical, and the first debugging round was spent in
        // devtools finding out which.
        const detail = body?.stripe
          ?? (Array.isArray(body?.missing) ? `missing ${body.missing.join(", ")}` : null)
          ?? body?.error
          ?? `HTTP ${response.status}`;
        throw new Error(String(detail));
      }
      return typeof body?.url === "string" ? body.url : null;
    } catch (problem) {
      throw problem instanceof Error ? problem : new Error("checkout failed");
    }
  }, []);

  return { ...state, refresh, startCheckout };
}
