"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { client, configured, projectUrl, projectUrlProblem } from "@/lib/supabase";

/**
 * Why sign-up is not working, on the deploy you are standing on.
 *
 * Accounts depend on three things lining up, and two of them live outside this
 * repository: the environment variables have to reach *this* deployment, and
 * this deployment's callback address has to be on the accounts project's
 * allow list. A preview build and a production build are different deployments
 * on different addresses, so one can work while the other does not.
 *
 * Nothing here is secret. The project address is public by design and the key
 * is never printed — only whether one arrived.
 */
type Reach =
  | { kind: "checking" }
  | { kind: "ok" }
  | { kind: "failed"; detail: string }
  | { kind: "skipped" };

export default function AuthCheck() {
  const [origin, setOrigin] = useState("");
  const [reach, setReach] = useState<Reach>({ kind: "checking" });

  useEffect(() => {
    setOrigin(window.location.origin);
    if (!client() || !projectUrl) {
      setReach({ kind: "skipped" });
      return;
    }
    let live = true;

    // This used to call getSession(), which reads the browser's own storage and
    // succeeds without touching the network. It therefore reported "the project
    // answers: yes" for an address that answered nothing at all — a check that
    // could only pass. This asks the address itself.
    fetch(`${new URL(projectUrl).origin}/auth/v1/health`, { method: "GET" })
      .then(() => { if (live) setReach({ kind: "ok" }); })
      .catch((error: unknown) => {
        if (live) {
          setReach({
            kind: "failed",
            detail: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => { live = false; };
  }, []);

  const callback = origin ? `${origin}/auth/callback` : "…";
  const problem = projectUrlProblem(projectUrl);

  return (
    <div className="page stack" style={{ gap: "var(--pad-xl)" }}>
      <div>
        <h1 style={{ fontSize: "var(--size-h2)" }}>Accounts check</h1>
        <p className="muted footnote" style={{ marginTop: "var(--gap-xs)" }}>
          What this deployment knows about sign-in. Everything below is public.
        </p>
      </div>

      <Row
        label="This deployment"
        value={origin || "…"}
        note="Preview and production are separate deployments. A setting applied
              to one does not apply to the other."
      />

      <Row
        ok={configured}
        label="Account settings reached this build"
        value={configured ? "Yes" : "No"}
        note={configured
          ? "Both variables were present when this deployment was built."
          : "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY did not "
            + "reach this build. In Vercel, set both under Settings → "
            + "Environment Variables, tick every environment you want them in "
            + "— Production and Preview are separate — and then redeploy. These "
            + "are read at build time, so a deployment made before they were "
            + "added will not have them however the settings read now."}
      />

      {configured && (
        <Row
          ok={problem === null}
          label="Accounts project"
          value={projectUrl ?? "—"}
          note={problem
            ? `${problem} In Vercel, edit NEXT_PUBLIC_SUPABASE_URL, tick every `
              + "environment, and redeploy — this is read when the site is built, "
              + "so the running deployment keeps the old value until you do."
            : "Public by design, and the right shape: the project address with "
              + "nothing after it. The key is not shown here and is not needed "
              + "to diagnose this."}
        />
      )}

      {configured && (
        <Row
          ok={reach.kind === "ok" ? true : reach.kind === "failed" ? false : undefined}
          label="The project answers"
          value={
            reach.kind === "ok" ? "Yes"
              : reach.kind === "failed" ? "No"
                : reach.kind === "skipped" ? "Not checked"
                  : "Checking…"
          }
          note={reach.kind === "failed"
            ? `The address above did not respond: ${reach.detail}. A paused `
              + "project, a mistyped address and a blocked request all look "
              + "like this from inside a browser."
            : "The address above answered a real request over the network, so "
              + "the project exists and is awake."}
        />
      )}

      {configured && (
        <Row
          label="Address the emailed link must return to"
          value={callback}
          note="Copy this exactly into Supabase under Authentication → URL
                Configuration → Redirect URLs. If it is missing, the link is
                still sent, but clicking it drops the reader somewhere else —
                usually the Site URL, which is why a link can appear to do
                nothing. Every address the site is served on needs its own
                entry."
        />
      )}

      <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
        <div className="eyebrow">If all four are fine and no email arrives</div>
        <p className="muted footnote" style={{ margin: 0 }}>
          Supabase&rsquo;s built-in mail server is meant for testing: it sends only
          a few messages an hour, and some projects restrict it to addresses on
          the project team. Hitting that limit shows as an error on the sign-up
          sheet. Connecting your own mail provider under Authentication &rarr;
          Emails removes both limits.
        </p>
      </div>

      <Link href="/screens" className="control">Back to the screens</Link>
    </div>
  );
}

function Row({ label, value, note, ok }: {
  label: string; value: string; note: string; ok?: boolean;
}) {
  return (
    <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="between">
        <div className="eyebrow">{label}</div>
        {ok !== undefined && (
          // Never colour alone: the word carries the verdict.
          <span className="caption" style={{ color: ok ? "var(--gain)" : "var(--warn)" }}>
            {ok ? "✓ ready" : "✗ needs attention"}
          </span>
        )}
      </div>
      <div className="mono footnote" style={{ wordBreak: "break-all" }}>{value}</div>
      <p className="caption dim" style={{ margin: 0 }}>{note}</p>
    </div>
  );
}
