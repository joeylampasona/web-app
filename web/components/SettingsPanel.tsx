"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useWatchlist } from "@/lib/useWatchlist";
import { useEmailPrefs } from "@/lib/useEmailPrefs";
import {
  readChoice, resolve, setChoice, subscribe, systemTheme, type ThemeChoice,
} from "@/lib/theme";

/**
 * Settings.
 *
 * Everything here is either a switch that does something or a fact about what
 * is stored. No preferences that are really just unbuilt features, and no
 * toggles that quietly do nothing -- an inert switch is worse than an absent
 * one, because it is trusted.
 *
 * The "what is kept" section is written plainly rather than linking straight
 * to the disclaimer. Someone opening settings wants to know what this site
 * holds about them, and that answer is four lines long, so it goes here.
 */

const CHOICES: { key: ThemeChoice; label: string; blurb: string }[] = [
  { key: "system", label: "Match my device", blurb: "Follows your phone or computer, including at sunset." },
  { key: "dark", label: "Dark", blurb: "The default." },
  { key: "light", label: "Light", blurb: "Better in direct sun." },
];

function Section({
  title, blurb, children,
}: {
  title: string; blurb?: string; children: React.ReactNode;
}) {
  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div>
        <h2 style={{ fontSize: "var(--size-h3)", margin: 0 }}>{title}</h2>
        {blurb && (
          <p className="muted footnote" style={{ margin: "var(--gap-xs) 0 0 0", maxWidth: "62ch" }}>
            {blurb}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}

function Appearance() {
  const [choice, setLocal] = useState<ThemeChoice>("system");
  const [device, setDevice] = useState<string>("");

  // Rendered on the server too, where there is no localStorage and no device
  // preference, so the real answer only arrives after mount.
  useEffect(() => {
    const sync = () => { setLocal(readChoice()); setDevice(systemTheme()); };
    sync();
    return subscribe(sync);
  }, []);

  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {CHOICES.map((option) => {
          const active = choice === option.key;
          return (
            <button
              key={option.key}
              type="button"
              className={active ? "control primary" : "control"}
              aria-pressed={active}
              onClick={() => setChoice(option.key)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        {CHOICES.find((c) => c.key === choice)?.blurb}
        {choice === "system" && device && ` Your device is asking for ${device} right now.`}
      </p>
    </div>
  );
}

function Account() {
  const { configured, ready, signedIn, user, signOut } = useAuth();
  const { symbols, ready: listReady } = useWatchlist();

  if (!ready) return <p className="muted footnote" style={{ margin: 0 }}>One moment.</p>;

  if (!configured) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        Accounts are not switched on for this deploy.{" "}
        <Link href="/auth/check" style={{ textDecoration: "underline" }}>
          What is missing
        </Link>
        .
      </p>
    );
  }

  if (!signedIn) {
    return (
      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        <p className="muted footnote" style={{ margin: 0 }}>
          You are not signed in. An account holds your watchlist and your saved
          screens, and nothing else.
        </p>
        <div className="row" style={{ gap: "var(--gap-sm)" }}>
          <Link href="/signin?reason=Sign%20in&next=%2Fsettings" className="control primary">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
        <div className="footnote muted">Signed in as</div>
        <div className="mono" style={{ wordBreak: "break-all" }}>{user?.email}</div>
        {listReady && (
          <div className="caption dim">
            {symbols.length} {symbols.length === 1 ? "ticker" : "tickers"} on your watchlist.
          </div>
        )}
      </div>
      <div className="row" style={{ gap: "var(--gap-sm)" }}>
        <button type="button" className="control" onClick={() => void signOut()}>
          Sign out
        </button>
        <Link href="/watchlist" className="control">Your watchlist</Link>
      </div>
    </div>
  );
}

function Digest() {
  const { configured, ready: authReady, signedIn } = useAuth();
  const { ready, weeklyDigest, saving, error, configured: table, setWeeklyDigest } =
    useEmailPrefs();

  if (!authReady || !ready) return null;

  if (!configured || !signedIn) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        The weekly email needs an account, so there is somewhere to send it and
        somewhere to record that you asked for it.
      </p>
    );
  }

  if (!table) {
    return (
      <p className="footnote" style={{ margin: 0, color: "var(--warn)" }}>
        Email preferences are not set up on this project yet — the schema file
        has not been run since the table was added.
      </p>
    );
  }

  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="row" style={{ gap: "var(--gap-sm)" }}>
        <button
          type="button"
          className={weeklyDigest ? "control primary" : "control"}
          aria-pressed={weeklyDigest}
          disabled={saving}
          onClick={() => setWeeklyDigest(!weeklyDigest)}
        >
          {saving ? "Saving…" : weeklyDigest ? "Subscribed" : "Send me the Sunday email"}
        </button>
        {weeklyDigest && !saving && (
          <button type="button" className="control"
                  onClick={() => setWeeklyDigest(false)}>
            Stop
          </button>
        )}
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        {weeklyDigest
          ? "The market's condition, what is set up across the screens, and the "
            + "week's dated events. The same letter goes to everyone — nothing "
            + "in it comes from your account. Every one carries a link that "
            + "stops them without signing in."
          : "Nothing is sent unless you ask. We never pass your address on."}
      </p>
      {error && (
        <p className="footnote" style={{ margin: 0, color: "var(--warn)" }}>
          That did not save: {error}
        </p>
      )}
    </div>
  );
}

export function SettingsPanel({
  asOf, provider, universeCount, benchmark, live,
}: {
  asOf: string | null;
  provider: string;
  universeCount: number;
  benchmark: string;
  live: boolean;
}) {
  return (
    <div className="stack" style={{ gap: "var(--gap-xl)" }}>
      <Section
        title="Appearance"
        blurb="Applies to this browser only, and takes effect immediately."
      >
        <Appearance />
      </Section>

      <Section title="Account">
        <Account />
      </Section>

      <Section
        title="Email"
        blurb="One letter on Sundays, about the week ahead. Off unless you turn it on."
      >
        <Digest />
      </Section>

      <Section
        title="What this site keeps"
        blurb="All of it, in four lines."
      >
        <ul className="stack footnote muted"
            style={{ gap: "var(--gap-xs)", margin: 0, paddingLeft: "1.1rem" }}>
          <li>Your email address, so the account has a name.</li>
          <li>Your watchlist — up to 50 tickers.</li>
          <li>Any screens you saved, with the dial settings you chose.</li>
          <li>Your theme, in this browser only. It never leaves the device.</li>
        </ul>
        <p className="caption dim" style={{ margin: 0 }}>
          No prices you looked at, no pages you visited, nothing sold to anybody.
          Switching the Sunday email off stops all mail except the sign-in codes,
          which are how you get in rather than something we send you.
          {/* This said "email the address in the disclaimer" and there is no
              address on the disclaimer, or anywhere else on the site — an
              instruction pointing at nothing. It goes back when a contact
              address exists and has been tested. */}
        </p>
      </Section>

      <Section
        title="The data"
        blurb="Where the numbers on this site come from, and how old they are."
      >
        <div className="stack" style={{ gap: "var(--gap-xs)" }}>
          <Row label="Last session" value={asOf ?? "—"} />
          <Row label="Names followed" value={String(universeCount)} />
          <Row label="Benchmark" value={benchmark} />
          <Row label="Price source" value={live ? provider : `${provider} (demo fixture)`} />
        </div>
        {!live && (
          <p className="footnote" style={{ color: "var(--warn)", margin: 0 }}>
            This build is running on a deterministic fixture. The tickers and
            prices are invented.
          </p>
        )}
        <p className="caption dim" style={{ margin: 0 }}>
          Prices are end of day. Nothing here is live, and nothing here is
          investment advice.{" "}
          <Link href="/legal" style={{ textDecoration: "underline" }}>
            The full disclaimer
          </Link>
          .
        </p>
      </Section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="between footnote" style={{ gap: "var(--gap-sm)" }}>
      <span className="muted">{label}</span>
      <span className="mono" style={{ textAlign: "right" }}>{value}</span>
    </div>
  );
}
