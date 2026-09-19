"use client";

import { useState } from "react";
import Link from "next/link";
import { Drawer } from "vaul";
import { useAuth } from "@/lib/auth";
import { useKeyboardInset } from "@/lib/useKeyboardInset";

/**
 * An email field, then a six-digit field. Supabase mails the code; typing it
 * back here signs the reader in without the session ever having to survive a
 * trip through another app. That is the whole reason it is a code: an emailed
 * link opens in the browser, and the installed home-screen app has its own
 * storage, so a link can sign you into Safari and never into the app.
 *
 * Nothing here collects or stores a password.
 */
export function SignUpSheet() {
  const {
    configured, promptOpen, promptReason, closePrompt, linkState, sendLink,
    verifyCode, resetLink,
  } = useAuth();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const sending = linkState.kind === "sending";
  const keyboard = useKeyboardInset();

  return (
    <Drawer.Root
      open={promptOpen}
      onOpenChange={(open) => {
        if (!open) { closePrompt(); resetLink(); setCode(""); }
      }}
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
            // Lift clear of the on-screen keyboard. Without this the sheet stays
            // pinned to the bottom of the layout viewport and the keyboard is
            // drawn over the top of it, hiding the field being typed into.
            transform: keyboard ? `translateY(-${keyboard}px)` : undefined,
            transition: "transform 140ms ease-out",
            // On a short screen with the keyboard up there may be less room than
            // the sheet wants; let it scroll rather than push the button off.
            maxHeight: keyboard
              ? `calc(100dvh - ${keyboard}px - var(--pad-xl))` : undefined,
            overflowY: keyboard ? "auto" : undefined,
          }}
        >
          <Drawer.Title style={{ fontSize: "var(--size-h3)", fontWeight: 500 }}>
            {linkState.kind === "sent" ? "Enter the code" : promptReason || "Sign up"}
          </Drawer.Title>

          {linkState.kind === "sent" ? (
            <>
              <Drawer.Description className="muted footnote" style={{ marginTop: "var(--gap-sm)" }}>
                A six-digit code is on its way to{" "}
                <span className="mono">{linkState.email}</span>. Type it in here — it
                works in this window, which a link does not. The code lasts an hour and
                nothing is saved until you use it.
              </Drawer.Description>
              <form
                onSubmit={(event) => { event.preventDefault(); void verifyCode(code); }}
                className="stack"
                style={{ marginTop: "var(--pad-lg)", gap: "var(--gap-sm)" }}
              >
                <label className="stack" style={{ gap: "var(--gap-xs)" }}>
                  <span className="footnote muted">Code</span>
                  <input
                    className="control mono"
                    required
                    // A numeric keypad, and the one-time-code hint that lets iOS
                    // offer the digits straight from the message.
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="000000"
                    value={code}
                    onChange={(event) => {
                      setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
                    }}
                    style={{ width: "100%", letterSpacing: "0.3em",
                             fontSize: "var(--size-h3)" }}
                  />
                </label>
                <div className="row" style={{ gap: "var(--gap-sm)" }}>
                  <button type="submit" className="control primary grow"
                          disabled={linkState.checking || code.length < 6}>
                    {linkState.checking ? "Checking…" : "Sign me in"}
                  </button>
                  <button type="button" className="control"
                          onClick={() => { resetLink(); setCode(""); }}>
                    Back
                  </button>
                </div>
                {linkState.error && (
                  <p className="footnote" style={{ color: "var(--warn)", margin: 0 }}>
                    {linkState.error}
                  </p>
                )}
                <p className="caption dim" style={{ margin: 0 }}>
                  The same email carries a link too, if you would rather tap it — but a
                  link signs you in to the browser, not to the app on your home screen.
                </p>
              </form>
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
                      {sending ? "Sending…" : "Email me a code"}
                    </button>
                    <button type="button" className="control" onClick={closePrompt}>
                      Not now
                    </button>
                  </div>
                  {linkState.kind === "error" && (
                    <p className="footnote" style={{ color: "var(--warn)", margin: 0 }}>
                      {linkState.message}{" "}
                      <Link href="/auth/check" onClick={closePrompt}
                            style={{ textDecoration: "underline" }}>
                        Check the setup
                      </Link>
                      .
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
                    sign up to yet.{" "}
                    <Link href="/auth/check" onClick={closePrompt}
                          style={{ textDecoration: "underline" }}>
                      What is missing
                    </Link>
                    .
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
