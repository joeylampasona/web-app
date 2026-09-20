"use client";

import { useAuth } from "@/lib/auth";

/** Wraps what needs an account rather than a subscription: watchlist,
 *  saved screens, export. The X-ray used to be here, and that was the
 *  problem — this component refuses to render, which is not the same as
 *  the data being absent, and for the X-ray the data was in the public
 *  file the whole time. Anything whose data is worth withholding belongs
 *  behind `Locked` and the gated store, not here. */
export function AuthGate({
  reason, children, blurb,
}: {
  reason: string;
  blurb: string;
  children?: React.ReactNode;
}) {
  const { ready, signedIn, requireSignUp } = useAuth();
  // Until the stored session has been read, neither answer is true yet, and
  // flashing "account needed" at someone who is signed in reads as a fault.
  if (!ready) return null;
  if (signedIn) return <>{children}</>;
  return (
    <div className="card stack" style={{ alignItems: "flex-start" }}>
      <div className="eyebrow">Account needed</div>
      <h3>{reason}</h3>
      <p className="muted footnote" style={{ margin: 0 }}>{blurb}</p>
      <button type="button" className="control primary" onClick={() => requireSignUp(reason)}>
        Sign up
      </button>
    </div>
  );
}
