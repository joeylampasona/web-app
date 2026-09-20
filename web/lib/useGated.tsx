"use client";

import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { client } from "./supabase";

/**
 * Fetch one gated document, or find out you are not entitled to it.
 *
 * The entitlement decision is not here and cannot be. This asks the server,
 * which passes the reader's own token to Postgres, where a policy decides row
 * by row. So the worst a bug in this file can do is fail to show something the
 * reader had already paid for — never the reverse. Nothing in the browser is
 * trusted to unlock anything, which is why the locked state renders from the
 * public file rather than from a hidden copy of the gated one.
 *
 * `state` is deliberately four values rather than a boolean. "Still asking"
 * and "you may not have this" look identical to a boolean and read completely
 * differently on a page: one is a spinner, the other is an offer, and showing
 * the offer for half a second to somebody who has already subscribed is the
 * sort of thing that makes a paid product feel broken.
 */
export type GatedState<T> =
  | { state: "loading"; data: null }
  | { state: "locked"; data: null }
  | { state: "ready"; data: T }
  | { state: "error"; data: null; detail: string };

export function useGated<T>(path: string | null): GatedState<T> {
  const { signedIn, ready: authReady } = useAuth();
  const [result, setResult] = useState<GatedState<T>>({ state: "loading", data: null });

  useEffect(() => {
    if (!path) {
      setResult({ state: "locked", data: null });
      return;
    }
    if (!authReady) return;

    const supabase = client();
    // No project configured, or nobody signed in. Both are "locked" rather
    // than "error": neither is a fault, and an error message would be telling
    // a reader that something went wrong when nothing did.
    if (!supabase || !signedIn) {
      setResult({ state: "locked", data: null });
      return;
    }

    let alive = true;
    setResult({ state: "loading", data: null });

    (async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!alive) return;
      if (!session) {
        setResult({ state: "locked", data: null });
        return;
      }
      try {
        const response = await fetch(
          `/api/gated?path=${encodeURIComponent(path)}`,
          { headers: { Authorization: `Bearer ${session.access_token}` } },
        );
        if (!alive) return;
        // 404 is what the route returns both for "no such document" and for
        // "not yours", on purpose — a 403 would confirm the path exists and
        // that it was guessed correctly. Either way the reader is offered the
        // subscription, which is the right response to both.
        if (response.status === 404) {
          setResult({ state: "locked", data: null });
          return;
        }
        if (!response.ok) {
          setResult({ state: "error", data: null, detail: `HTTP ${response.status}` });
          return;
        }
        const body = await response.json();
        if (!alive) return;
        setResult({ state: "ready", data: body.payload as T });
      } catch {
        if (!alive) return;
        setResult({ state: "error", data: null, detail: "the request failed" });
      }
    })();

    return () => { alive = false; };
  }, [path, signedIn, authReady]);

  return result;
}
