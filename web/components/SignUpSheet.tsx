"use client";

import { useState } from "react";
import { Drawer } from "vaul";
import { useAuth } from "@/lib/auth";

/**
 * One email field and one button. Supabase sends a one-time link; clicking it
 * signs the reader in. Nothing here collects or stores a password.
 */
export function SignUpSheet() {
  const {
    configured, promptOpen, promptReason, closePrompt, linkState, sendLink, resetLink,
  } = useAuth();
  const [email, setEmail] = useState("");
  const sending = linkState.kind === "sending";

  return (
    <Drawer.Root
      open={promptOpen}
      onOpenChange={(open) => { if (!open) { closePrompt(); resetLink(); } }}
    >
      <Drawer.Portal>
        <Drawer.Overlay style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)" }} />
        <Drawer.Content
          style={{
            position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 60,
            background: "var(--surface-2)",
            borderTop: "0.5px solid var(--border-strong)",
            borderRadius: "var(--radius-card) var(--radius-card) 0 0",
            padding: "var(--pad-xl)",
          }}
        >
          <Drawer.Title style={{ fontSize: "var(--size-h3)", fontWeight: 500 }}>
            {linkState.kind === "sent" ? "Check your email" : promptReason || "Sign up"}
          </Drawer.Title>

          {linkState.kind === "sent" ? (
            <>
              <Drawer.Description className="muted footnote" style={{ marginTop: "var(--gap-sm)" }}>
                A one-time link is on its way to{" "}
                <span className="mono">{linkState.email}</span>. Open it on this device and
                you are in. The link expires in an hour, and nothing is saved until you
                click it.
              </Drawer.Description>
              <div className="row" style={{ marginTop: "var(--pad-lg)", gap: "var(--gap-sm)" }}>
                <button type="button" className="control grow" onClick={resetLink}>
                  Use a different address
                </button>
                <button type="button" className="control" onClick={closePrompt}>Close</button>
              </div>
            </>
          ) : (
            <>
              <Drawer.Description className="muted footnote" style={{ marginTop: "var(--gap-sm)" }}>
                Watchlists, saved custom screens, export and the base X-ray need an
                account. Everything else on the site is open.
              </Drawer.Description>

              {configured ? (
                <form
                  onSubmit={(event) => { event.preventDefault(); void sendLink(email); }}
                  className="stack"
                  style={{ marginTop: "var(--pad-lg)", gap: "var(--gap-sm)" }}
                >
                  <label className="stack" style={{ gap: "var(--gap-xs)" }}>
                    <span className="footnote muted">Email</span>
                    <input
                      type="email"
                      className="control"
                      required
                      autoComplete="email"
                      inputMode="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(event) => {
                        setEmail(event.target.value);
                        // The last address was refused. This one has not been
                        // tried yet, so the refusal must not still be on screen
                        // underneath it.
                        if (linkState.kind === "error") resetLink();
                      }}
                      style={{ width: "100%" }}
                    />
                  </label>
                  <div className="row" style={{ gap: "var(--gap-sm)" }}>
                    <button type="submit" className="control primary grow" disabled={sending}>
                      {sending ? "Sending…" : "Email me a link"}
                    </button>
                    <button type="button" className="control" onClick={closePrompt}>
                      Not now
                    </button>
                  </div>
                  {linkState.kind === "error" && (
                    <p className="footnote" style={{ color: "var(--warn)", margin: 0 }}>
                      {linkState.message}
                    </p>
                  )}
                  <p className="caption dim" style={{ margin: 0 }}>
                    No password. An account holds your email address, your watchlist and
                    your saved screens.
                  </p>
                </form>
              ) : (
                <>
                  <div className="row" style={{ marginTop: "var(--pad-lg)", gap: "var(--gap-sm)" }}>
                    <button type="button" className="control" onClick={closePrompt}>Close</button>
                  </div>
                  <p className="caption dim" style={{ marginTop: "var(--pad-md)", marginBottom: 0 }}>
                    Accounts are not switched on for this deploy, so there is nothing to
                    sign up to yet.
                  </p>
                </>
              )}
            </>
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
