"use client";

import { Drawer } from "vaul";
import { useAuth } from "@/lib/auth";

export function SignUpSheet() {
  const { promptOpen, promptReason, closePrompt } = useAuth();
  return (
    <Drawer.Root open={promptOpen} onOpenChange={(open) => !open && closePrompt()}>
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
            {promptReason || "Sign up"}
          </Drawer.Title>
          <Drawer.Description className="muted footnote" style={{ marginTop: "var(--gap-sm)" }}>
            Watchlists, saved custom screens, export and the base X-ray need an
            account. Everything else on the site is open.
          </Drawer.Description>
          <div className="row" style={{ marginTop: "var(--pad-lg)", gap: "var(--gap-sm)" }}>
            <button type="button" className="control primary grow">Sign up</button>
            <button type="button" className="control" onClick={closePrompt}>
              Not now
            </button>
          </div>
          <p className="caption dim" style={{ marginTop: "var(--pad-md)", marginBottom: 0 }}>
            Accounts are not wired up yet — the provider is still being chosen.
          </p>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
