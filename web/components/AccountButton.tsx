"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";

/**
 * Signed out this is the sign-up prompt. Signed in it is the way back out —
 * with the address on screen, because on a shared device the only way to know
 * whose watchlist you are looking at is to be told.
 */
export function AccountButton() {
  const { configured, ready, signedIn, user, requireSignUp, signOut } = useAuth();
  const [open, setOpen] = useState(false);

  // Before the stored session has been read, neither label is true yet.
  if (!ready) return <span style={{ minHeight: 36, width: 72 }} aria-hidden />;

  if (!signedIn) {
    return (
      <button
        type="button"
        className="control primary footnote"
        style={{ minHeight: 36 }}
        onClick={() => requireSignUp("Sign up")}
      >
        {configured ? "Sign up" : "About accounts"}
      </button>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        className="control footnote"
        style={{ minHeight: 36 }}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Account
      </button>
      {open && (
        <div
          className="card stack"
          style={{
            position: "absolute", right: 0, top: "calc(100% + var(--gap-xs))",
            zIndex: 50, minWidth: 220, gap: "var(--gap-sm)",
            background: "var(--surface-2)",
          }}
        >
          <span className="caption dim" style={{ wordBreak: "break-all" }}>
            {user?.email}
          </span>
          <button
            type="button"
            className="control footnote"
            onClick={() => { setOpen(false); void signOut(); }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
