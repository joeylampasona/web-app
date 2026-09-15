"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { client, configured } from "@/lib/supabase";

/**
 * Where the magic link lands.
 *
 * This page used to hand the URL to the client's automatic handler, wait ten
 * seconds, and — if no session appeared — say the link had probably expired.
 * That sentence was a guess, and for the most common failure it was the wrong
 * guess: a link opened in a different browser from the one that asked for it
 * fails because the code verifier is not there, not because it expired. The
 * reader was told to ask for a fresh link, which fails in exactly the same way.
 *
 * So the exchange happens here, explicitly, and whatever comes back is what the
 * reader is told.
 */
interface Failure { headline: string; detail: string }

/** Supabase's errors are precise and unreadable. Each of these has a cause the
 *  reader can act on; anything else is shown as it came, because an error we do
 *  not recognise is still better than one we have invented. */
function readFailure(message: string): Failure {
  const text = message.toLowerCase();
  if (text.includes("code verifier") || text.includes("code_verifier")) {
    return {
      headline: "This link has to be opened in the browser that asked for it.",
      detail: "Sign-in links are tied to the browser that requested them, so a "
        + "link requested on a computer cannot be opened on a phone, and the "
        + "other way round. Ask for a link here, in this browser, and open it "
        + "here.",
    };
  }
  if (text.includes("expired")) {
    return {
      headline: "This link has expired.",
      detail: "Links last an hour. Ask for a fresh one and open it straight away.",
    };
  }
  if (text.includes("already") || text.includes("used") || text.includes("invalid request")) {
    return {
      headline: "This link has already been used.",
      detail: "Each link works once. Some mail apps and security scanners open "
        + "links before you do, which uses them up — if that keeps happening, "
        + "try opening the message on a different mail app.",
    };
  }
  return { headline: "That link did not sign you in.", detail: message };
}

export default function AuthCallback() {
  const router = useRouter();
  const [failure, setFailure] = useState<Failure | null>(null);

  useEffect(() => {
    const supabase = client();
    if (!supabase) {
      setFailure({
        headline: "Accounts are not switched on for this deploy.",
        detail: "Nothing is wrong with your link — there is no project behind "
          + "this deployment to sign you in to.",
      });
      return;
    }
    let live = true;
    const done = (f: Failure | null) => { if (live) { live = false; f ? setFailure(f) : router.replace("/watchlist"); } };

    (async () => {
      // Already signed in — an opened-twice link should not look like an error.
      const { data: existing } = await supabase.auth.getSession();
      if (existing.session) return done(null);

      const url = new URL(window.location.href);
      const hash = new URLSearchParams(url.hash.replace(/^#/, ""));
      const read = (key: string) => url.searchParams.get(key) ?? hash.get(key);

      // Supabase refused before the reader ever got here.
      const refused = read("error_description") || read("error");
      if (refused) return done(readFailure(refused));

      const code = read("code");
      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        return done(error ? readFailure(error.message) : null);
      }

      // The older link style puts the tokens straight in the fragment.
      const access_token = hash.get("access_token");
      const refresh_token = hash.get("refresh_token");
      if (access_token && refresh_token) {
        const { error } = await supabase.auth.setSession({ access_token, refresh_token });
        return done(error ? readFailure(error.message) : null);
      }

      done({
        headline: "This link carried no sign-in code.",
        detail: "That usually means the address was opened by hand, or the mail "
          + "app rewrote the link. Open the link in the email directly rather "
          + "than copying it.",
      });
    })().catch((error: unknown) => {
      done(readFailure(error instanceof Error ? error.message : String(error)));
    });

    return () => { live = false; };
  }, [router]);

  return (
    <div className="page stack">
      <div className="card stack" style={{ alignItems: "flex-start" }}>
        <div className="eyebrow">Signing you in</div>
        <h3>{failure ? failure.headline : "One moment"}</h3>
        {failure ? (
          <>
            <p className="muted footnote" style={{ margin: 0 }}>{failure.detail}</p>
            <div className="row" style={{ gap: "var(--gap-sm)" }}>
              <Link href="/screens" className="control">Back to the screens</Link>
              {configured && (
                <Link href="/auth/check" className="control">Check the setup</Link>
              )}
            </div>
          </>
        ) : (
          <p className="muted footnote" style={{ margin: 0 }}>
            Reading the link you just opened.
          </p>
        )}
      </div>
    </div>
  );
}
