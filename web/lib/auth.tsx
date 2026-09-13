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
    const { error } = await supabase.auth.signInWithOtp({
      email: address,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setLinkState(
      error
        ? { kind: "error", message: error.message }
        : { kind: "sent", email: address },
    );
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
