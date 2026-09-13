"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { client, configured } from "@/lib/supabase";

/**
 * Where the magic link lands. The Supabase client reads the code out of the URL
 * and trades it for a session on its own; this page waits for that to finish,
 * then gets out of the way.
 *
 * A link that has expired or been opened twice fails here rather than silently
 * dropping the reader on the home page signed out.
 */
export default function AuthCallback() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const supabase = client();
    if (!supabase) {
      setMessage("Accounts are not switched on for this deploy.");
      return;
    }
    let live = true;

    const stop = window.setTimeout(() => {
      if (live) setMessage("That link did not sign you in. It may have expired, or already been used.");
    }, 10000);

    const finish = () => {
      if (!live) return;
      live = false;
      window.clearTimeout(stop);
      router.replace("/watchlist");
    };

    supabase.auth.getSession().then(({ data }) => {
      if (data.session) finish();
    });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) finish();
    });

    return () => {
      live = false;
      window.clearTimeout(stop);
      subscription.subscription.unsubscribe();
    };
  }, [router]);

  return (
    <div className="page stack">
      <div className="card stack" style={{ alignItems: "flex-start" }}>
        <div className="eyebrow">Signing you in</div>
        <h3>{message ?? "One moment"}</h3>
        {message ? (
          <>
            <p className="muted footnote" style={{ margin: 0 }}>
              {configured
                ? "Ask for a fresh link and open it on this device."
                : "Nothing is wrong with your link — there is no project behind this deploy."}
            </p>
            <Link href="/screens" className="control">Back to the screens</Link>
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
