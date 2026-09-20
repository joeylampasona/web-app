"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import { client, configured } from "./supabase";

/**
 * Auth gates exactly four things: the watchlist, saved custom screens, export
 * Everything else is open.
 *
 * Sign-in is a numeric code, typed back into whichever copy of the site asked
 * for it. It used to be a link, and a link cannot sign anyone into the home
 * screen app: the manifest asks for `display: standalone`, which gives that app
 * its own storage container, and an emailed link always opens in the browser.
 * The session then exists in the browser and the app never sees it — not
 * flakily, but never. A code never leaves the window it was typed into, so it
 * works the same in Safari, in the installed app, and on a phone reading mail
 * on a laptop.
 *
 * The link still works for anyone who prefers it; /auth/callback still trades
 * one for a session. There is still no password to store, forget or leak, and
 * this app never sees a credential.
 *
 * When no project is configured the whole thing degrades to the state it was in
 * before: `signedIn` false, `configured` false, and the sign-up sheet says so
 * rather than collecting an address it cannot send anything to.
 */
export type LinkState =
  | { kind: "idle" }
  | { kind: "sending" }
  /** A code is out. `checking` is a code being verified; `error` is the last
   *  one having been refused, which must not throw the reader back to the email
   *  step — they would only have to type the same address again. */
  | { kind: "sent"; email: string; checking: boolean; error: string | null }
  | { kind: "error"; message: string };

export interface AuthState {
  configured: boolean;
  /** False until the stored session has been read, so gates do not flicker. */
  ready: boolean;
  signedIn: boolean;
  user: { id: string; email: string } | null;
  /** Why the reader was sent to sign in, shown as the page heading. */
  promptReason: string;
  requireSignUp: (reason: string) => void;
  linkState: LinkState;
  sendLink: (email: string) => Promise<void>;
  /** Trades a code for a session, in this window. */
  verifyCode: (code: string) => Promise<void>;
  resetLink: () => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

/**
 * How many digits a sign-in code can have.
 *
 * Supabase decides the real length — Authentication -> Providers -> Email ->
 * Email OTP Length, anywhere from 6 to 10 — and the browser has no way to ask
 * it. So accept the whole range rather than hard-coding one end of it. The
 * input used to cap at six and slice the rest away, which meant a project
 * configured for eight silently dropped two digits as you typed and then
 * reported the code as wrong. Truncating input is never the right failure:
 * take what the reader typed and let the server be the judge.
 */
export const CODE_MIN = 6;
export const CODE_MAX = 10;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [promptReason, setPromptReason] = useState("");
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);
  const [ready, setReady] = useState(!configured);
  const [linkState, setLinkState] = useState<LinkState>({ kind: "idle" });
  /** The address the outstanding code went to. */
  const sentTo = useRef("");

  useEffect(() => {
    const supabase = client();
    if (!supabase) return;
    let live = true;

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!live) return;
        setUser(toUser(data.session?.user));
      })
      // A session that cannot be read is a signed-out reader, not a reason to
      // leave every gate showing a placeholder for the rest of the visit.
      .catch(() => undefined)
      .finally(() => { if (live) setReady(true); });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(toUser(session?.user));
      setReady(true);
      if (session) {
        setLinkState({ kind: "idle" });
      }
    });

    return () => {
      live = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  /**
   * Every gate on the site funnels through here, so this is the one place that
   * decides what signing in looks like. It used to open a bottom sheet; a sheet
   * is fixed-position, which on iOS is a losing argument with the keyboard. It
   * is a page now, and the page carries where the reader was so they land back
   * on it rather than at the top of the site.
   */
  const requireSignUp = useCallback((reason: string) => {
    setPromptReason(reason);
    setLinkState({ kind: "idle" });
    const next = encodeURIComponent(pathname || "/screens");
    router.push(`/signin?reason=${encodeURIComponent(reason)}&next=${next}`);
  }, [pathname, router]);

  const sendLink = useCallback(async (email: string) => {
    const supabase = client();
    if (!supabase) {
      setLinkState({ kind: "error", message: "Accounts are not configured on this deploy." });
      return;
    }
    const address = email.trim();
    if (!address.includes("@")) {
      setLinkState({ kind: "error", message: "That does not look like an email address." });
      return;
    }
    setLinkState({ kind: "sending" });
    const callback = `${window.location.origin}/auth/callback`;
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email: address,
        // The same message carries both: the code for anyone typing it back in
        // here, the link for anyone who would rather tap it. Which one the
        // email actually shows is set by the project's email template.
        options: { emailRedirectTo: callback },
      });
      setLinkState(
        error
          ? { kind: "error", message: explain(error.message, callback) }
          : { kind: "sent", email: address, checking: false, error: null },
      );
      if (!error) sentTo.current = address;
    } catch {
      // A network failure or a project that no longer answers. Without this the
      // button sat on "Sending…" for ever, which reads as "working" and is not.
      setLinkState({
        kind: "error",
        message: "Could not reach the accounts service. Check the connection and "
          + "try again; if it keeps happening, open /auth/check.",
      });
    }
  }, []);

  const verifyCode = useCallback(async (code: string) => {
    const supabase = client();
    const digits = code.replace(/\D/g, "");
    // The address the code was sent to. Held in a ref rather than read back out
    // of state: a setState updater is not a getter, React does not promise to
    // run it when you call it, and asking the sheet for the address a second
    // time invites two copies that disagree.
    const address = sentTo.current;

    if (!supabase || !address) {
      setLinkState((was) => was.kind === "sent"
        ? { ...was, checking: false, error: "Accounts are not configured on this deploy." }
        : was);
      return;
    }
    if (digits.length < CODE_MIN || digits.length > CODE_MAX) {
      setLinkState((was) => was.kind === "sent"
        ? { ...was, checking: false,
            error: `A code is ${CODE_MIN} to ${CODE_MAX} digits. Check you copied all of it.` }
        : was);
      return;
    }
    setLinkState((was) => was.kind === "sent"
      ? { ...was, checking: true, error: null } : was);

    try {
      const { error } = await supabase.auth.verifyOtp({
        email: address, token: digits, type: "email",
      });
      if (error) {
        setLinkState((was) => was.kind === "sent"
          ? { ...was, checking: false, error: explainCode(error.message) }
          : was);
      }
      // On success onAuthStateChange closes the sheet and clears this.
    } catch {
      setLinkState((was) => was.kind === "sent"
        ? { ...was, checking: false,
            error: "Could not reach the accounts service. Try again." }
        : was);
    }
  }, []);

  const signOut = useCallback(async () => {
    const supabase = client();
    if (!supabase) return;
    await supabase.auth.signOut();
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      configured,
      ready,
      signedIn: Boolean(user),
      user,
      promptReason,
      requireSignUp,
      linkState,
      sendLink,
      verifyCode,
      resetLink: () => setLinkState({ kind: "idle" }),
      signOut,
    }),
    [linkState, promptReason, ready, requireSignUp, sendLink,
     signOut, user, verifyCode],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

function toUser(raw: { id: string; email?: string } | undefined) {
  return raw ? { id: raw.id, email: raw.email ?? "" } : null;
}

/**
 * Supabase's refusals are accurate and unreadable. Each one here has a cause a
 * reader or an operator can act on, so it is named rather than passed through.
 * Anything unrecognised is shown as-is: a message we do not understand is still
 * better than a message we have replaced with a guess.
 */
function explainCode(message: string): string {
  const text = message.toLowerCase();
  if (text.includes("expired") || text.includes("invalid")) {
    return "That code did not work. Codes last an hour and can only be used "
      + "once — ask for a fresh one if this was an old message.";
  }
  if (text.includes("rate") || text.includes("too many")) {
    return "Too many attempts. Wait a minute and try again.";
  }
  return message;
}

function explain(message: string, callback: string): string {
  const text = message.toLowerCase();
  if (text.includes("redirect")) {
    return `The accounts project will not send readers back to ${callback}. `
      + "Add that exact address under Authentication → URL Configuration → "
      + "Redirect URLs in Supabase.";
  }
  if (text.includes("rate limit") || text.includes("after") && text.includes("seconds")) {
    return "Too many links have been requested in the last hour. Supabase's "
      + "built-in mail server allows only a few, and resets hourly. Wait and "
      + "try again, or connect a real mail provider under Authentication → "
      + "Emails in Supabase.";
  }
  if (text.includes("signups not allowed") || text.includes("signup is disabled")) {
    return "New accounts are switched off on the accounts project. Turn them on "
      + "under Authentication → Sign In / Providers in Supabase.";
  }
  if (text.includes("invalid path")) {
    return "The accounts project address has a path on the end of it. It must be "
      + "just the project address and nothing after it — no /rest/v1/. Fix "
      + "NEXT_PUBLIC_SUPABASE_URL and redeploy.";
  }
  if (text.includes("invalid") && text.includes("email")) {
    return "That address was refused as invalid. Check it for a typo.";
  }
  if (text.includes("error sending") || text.includes("smtp")) {
    return "The accounts project accepted the request but could not send the "
      + "email. Its mail settings need attention — see Authentication → Emails "
      + "in Supabase.";
  }
  return message;
}
