"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { client } from "@/lib/supabase";
import { SITE_NAME } from "@/lib/copy";

/**
 * Stopping the email, without signing in.
 *
 * Requiring a login to unsubscribe is both hostile and non-compliant, and the
 * person clicking is often reading on a device that has never been signed in.
 * So this carries nothing but a random token and calls a database function
 * that takes only that token: it cannot be used to read an address, discover
 * whether one is registered, or change anything but the flags on the one row
 * whose token was supplied.
 *
 * It runs on arrival rather than behind a confirm button. A mail client that
 * pre-fetches links would trigger a confirm button anyway, and someone who
 * clicked "stop these emails" has already said what they want; making them say
 * it twice is a dark pattern with a compliance problem attached.
 */
type State =
  | { kind: "working" }
  | { kind: "done" }
  | { kind: "unknown" }
  | { kind: "error"; message: string };

function Unsubscribe() {
  const token = useSearchParams().get("t") || "";
  const [state, setState] = useState<State>({ kind: "working" });

  useEffect(() => {
    if (!token) {
      setState({ kind: "unknown" });
      return;
    }
    const supabase = client();
    if (!supabase) {
      setState({ kind: "error", message: "Accounts are not configured on this deploy." });
      return;
    }
    let cancelled = false;
    void (async () => {
      const { data, error } = await supabase.rpc("unsubscribe_by_token", { token });
      if (cancelled) return;
      if (error) setState({ kind: "error", message: error.message });
      else setState(data === true ? { kind: "done" } : { kind: "unknown" });
    })();
    return () => { cancelled = true; };
  }, [token]);

  return (
    <div className="page stack" style={{ gap: "var(--gap-lg)", maxWidth: 460 }}>
      <div>
        <div className="eyebrow">{SITE_NAME}</div>
        <h1 style={{ fontSize: "var(--size-h2)", marginBottom: "var(--gap-xs)" }}>
          {state.kind === "done" ? "That's stopped" : "Stopping your emails"}
        </h1>
      </div>

      {state.kind === "working" && (
        <p className="muted footnote" style={{ margin: 0 }}>One moment.</p>
      )}

      {state.kind === "done" && (
        <p className="muted footnote" style={{ margin: 0 }}>
          You will not get the weekly email again. Your account, watchlist and
          saved screens are untouched, and sign-in codes will still arrive — those
          are not marketing, they are how you get in.
        </p>
      )}

      {state.kind === "unknown" && (
        <p className="muted footnote" style={{ margin: 0 }}>
          That link does not match anything. It may have already been used, which
          means the emails are already stopped. If they keep arriving, open
          settings while signed in and switch the Sunday email off there.
        </p>
      )}

      {state.kind === "error" && (
        <p className="footnote" style={{ margin: 0, color: "var(--warn)" }}>
          Something went wrong: {state.message}. Nothing has changed, so try the
          link again, or switch it off in settings.
        </p>
      )}

      <div className="row" style={{ gap: "var(--gap-sm)" }}>
        <Link href="/settings" className="control">Settings</Link>
        <Link href="/" className="control">Open the site</Link>
      </div>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={<div className="page muted footnote">One moment.</div>}>
      <Unsubscribe />
    </Suspense>
  );
}
