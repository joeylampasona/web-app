"use client";

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import { client, configured } from "./supabase";

/**
 * Auth gates exactly four things: the watchlist, saved custom screens, export
 * and the X-ray. Everything else is open.
 *
 * Sign-in is a magic link. Someone types an email, Supabase sends a one-time
 * link, clicking it lands on /auth/callback with a session. There is no
 * password to store, forget or leak, and this app never sees a credential.
 *
 * When no project is configured the whole thing degrades to the state it was in
 * before: `signedIn` false, `configured` false, and the sign-up sheet says so
 * rather than collecting an address it cannot send anything to.
 */
export type LinkState =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "sent"; email: string }
  | { kind: "error"; message: string };

export interface AuthState {
  configured: boolean;
  /** False until the stored session has been read, so gates do not flicker. */
  ready: boolean;
  signedIn: boolean;
  user: { id: string; email: string } | null;
  promptOpen: boolean;
  promptReason: string;
  requireSignUp: (reason: string) => void;
  closePrompt: () => void;
  linkState: LinkState;
  sendLink: (email: string) => Promise<void>;
  resetLink: () => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptReason, setPromptReason] = useState("");
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);
  const [ready, setReady] = useState(!configured);
  const [linkState, setLinkState] = useState<LinkState>({ kind: "idle" });

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
        setPromptOpen(false);
        setLinkState({ kind: "idle" });
      }
    });

    return () => {
      live = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  const requireSignUp = useCallback((reason: string) => {
    setPromptReason(reason);
    setLinkState({ kind: "idle" });
    setPromptOpen(true);
  }, []);

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
        options: { emailRedirectTo: callback },
      });
      setLinkState(
        error
          ? { kind: "error", message: explain(error.message, callback) }
          : { kind: "sent", email: address },
      );
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
      promptOpen,
      promptReason,
      requireSignUp,
      closePrompt: () => setPromptOpen(false),
      linkState,
      sendLink,
      resetLink: () => setLinkState({ kind: "idle" }),
      signOut,
    }),
    [linkState, promptOpen, promptReason, ready, requireSignUp, sendLink, signOut, user],
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
