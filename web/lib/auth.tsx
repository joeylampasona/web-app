"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

/**
 * Auth gates exactly four things: the watchlist, saved custom screens, export
 * and the X-ray. Everything else is open.
 *
 * The provider itself — Clerk or a Supabase magic link — is an open decision in
 * the brief and is deliberately not made here. This context is the seam: swap
 * `signedIn` and `user` for the real client and every gate on the site starts
 * working without touching a component.
 */
export interface AuthState {
  signedIn: boolean;
  user: { id: string; email: string } | null;
  promptOpen: boolean;
  promptReason: string;
  requireSignUp: (reason: string) => void;
  closePrompt: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptReason, setPromptReason] = useState("");

  const requireSignUp = useCallback((reason: string) => {
    setPromptReason(reason);
    setPromptOpen(true);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      signedIn: false,
      user: null,
      promptOpen,
      promptReason,
      requireSignUp,
      closePrompt: () => setPromptOpen(false),
    }),
    [promptOpen, promptReason, requireSignUp],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
