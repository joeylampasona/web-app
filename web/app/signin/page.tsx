"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

/**
 * Signing in, as a page rather than a bottom sheet.
 *
 * It was a sheet, and a sheet is `position: fixed; bottom: 0`, which on iOS is
 * a fight with the on-screen keyboard that this lost twice. The first attempt
 * left the email field underneath the keyboard. The second lifted the sheet by
 * the keyboard's height and overshot, putting the button under the status bar
 * with the rest of the form somewhere off-screen — a fix that needed a device I
 * do not have in order to tell whether it had worked.
 *
 * A page needs none of that. It is ordinary document flow, so the browser
 * scrolls the focused field into view the way it does on every other site, and
 * there is no viewport arithmetic to get wrong. The installed home-screen app
 * and Safari behave the same because neither is being argued with.
 *
 * Every gate on the site calls requireSignUp(), which now brings the reader
 * here and remembers where they were.
 */
function SignIn() {
  const router = useRouter();
  const params = useSearchParams();
  const {
    configured, ready, signedIn, linkState, sendLink, verifyCode, resetLink,
  } = useAuth();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");

  const reason = params.get("reason") || "Sign up";
  const next = params.get("next") || "/screens";

  // Signing in is the whole point of this page, so leaving is the success case.
  useEffect(() => {
    if (ready && signedIn) router.replace(next);
  }, [next, ready, router, signedIn]);

  const sending = linkState.kind === "sending";
  const sent = linkState.kind === "sent";

  return (
    <div className="page stack" style={{ gap: "var(--pad-lg)", maxWidth: 460 }}>
      <div>
        <div className="eyebrow">{sent ? "Check your email" : "Account"}</div>
        <h1 style={{ fontSize: "var(--size-h2)" }}>{sent ? "Enter the code" : reason}</h1>
      </div>

      {!configured ? (
        <>
          <p className="muted footnote" style={{ margin: 0 }}>
            Accounts are not switched on for this deploy, so there is nothing to
            sign up to yet.
          </p>
          <div className="row" style={{ gap: "var(--gap-sm)" }}>
            <Link href="/auth/check" className="control">What is missing</Link>
            <Link href={next} className="control">Back</Link>
          </div>
        </>
      ) : sent ? (
        <>
          <p className="muted footnote" style={{ margin: 0 }}>
            A six-digit code is on its way to{" "}
            <span className="mono">{linkState.email}</span>. Type it in here — it works
            in this window, which a link does not. The code lasts an hour and nothing
            is saved until you use it.
          </p>
          <form
            onSubmit={(event) => { event.preventDefault(); void verifyCode(code); }}
            className="stack"
            style={{ gap: "var(--gap-sm)" }}
          >
            <label className="stack" style={{ gap: "var(--gap-xs)" }}>
              <span className="footnote muted">Code</span>
              <input
                className="control mono"
                required
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]*"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
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
              The same email carries a link too, if you would rather tap it — but a link
              signs you in to the browser, not to the app on your home screen.
            </p>
          </form>
        </>
      ) : (
        <>
          <p className="muted footnote" style={{ margin: 0 }}>
            Watchlists, saved custom screens, export and the base X-ray need an account.
            Everything else on the site is open.
          </p>
          <form
            onSubmit={(event) => { event.preventDefault(); void sendLink(email); }}
            className="stack"
            style={{ gap: "var(--gap-sm)" }}
          >
            <label className="stack" style={{ gap: "var(--gap-xs)" }}>
              <span className="footnote muted">Email</span>
              <input
                type="email"
                className="control"
                required
                autoFocus
                autoComplete="email"
                inputMode="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  // The last address was refused; this one has not been tried.
                  if (linkState.kind === "error") resetLink();
                }}
                style={{ width: "100%" }}
              />
            </label>
            <div className="row" style={{ gap: "var(--gap-sm)" }}>
              <button type="submit" className="control primary grow" disabled={sending}>
                {sending ? "Sending…" : "Email me a code"}
              </button>
              <Link href={next} className="control">Not now</Link>
            </div>
            {linkState.kind === "error" && (
              <p className="footnote" style={{ color: "var(--warn)", margin: 0 }}>
                {linkState.message}{" "}
                <Link href="/auth/check" style={{ textDecoration: "underline" }}>
                  Check the setup
                </Link>
                .
              </p>
            )}
            <p className="caption dim" style={{ margin: 0 }}>
              No password. An account holds your email address, your watchlist and your
              saved screens.
            </p>
          </form>
        </>
      )}
    </div>
  );
}

export default function SignInPage() {
  // useSearchParams needs a boundary, and the fallback is one line of text
  // rather than a spinner: this page is reached deliberately and resolves fast.
  return (
    <Suspense fallback={<div className="page muted footnote">One moment.</div>}>
      <SignIn />
    </Suspense>
  );
}
