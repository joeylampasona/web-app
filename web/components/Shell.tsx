"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Drawer } from "vaul";
import { LEGAL, TAGLINE } from "@/lib/copy";
import { AccountButton } from "./AccountButton";
import { ThemeToggle } from "./ThemeToggle";

interface Destination {
  href: string;
  title: string;
  blurb: string;
}

const TABS: {
  key: string; label: string; glyph: string; match: string;
  href?: string; destinations?: Destination[];
}[] = [
  {
    key: "screens", label: "Screens", glyph: "▦", match: "/screens",
    destinations: [
      { href: "/screens/vcp", title: "VCP", blurb: "A leader pauses and the swings tighten." },
      { href: "/screens/blue_sky", title: "Blue sky", blurb: "Resting at the highest price it has ever traded." },
      { href: "/screens/multi_year", title: "Multi-year / deep comeback", blurb: "A lid that has held for a year or more." },
      { href: "/screens/ipo", title: "IPO base", blurb: "A recent listing building its first real base." },
      { href: "/screens/combine", title: "Combine screens", blurb: "Tick several and see the union." },
      { href: "/screens/custom", title: "Create your own", blurb: "Move every dial yourself." },
      { href: "/learn", title: "How the screens work", blurb: "The shape, the concepts and the funnel." },
      { href: "/learn/backtest", title: "Backtest", blurb: "Test the rules on years of data." },
    ],
  },
  {
    key: "market", label: "Market", glyph: "◳", match: "/market",
    destinations: [
      { href: "/market/breakouts", title: "All breakouts today", blurb: "Every name that cleared its pivot." },
      { href: "/market/followthrough", title: "Did it work?", blurb: "What happened to the breakouts we showed." },
      { href: "/market/breadth", title: "Breadth", blurb: "How much of the market is participating." },
      { href: "/market/rotation", title: "Rotation", blurb: "Strength now against momentum since last month." },
      { href: "/market/sectors", title: "Sector strength", blurb: "Strongest and weakest, heating and cooling." },
      { href: "/market/map", title: "The map", blurb: "Every industry sized by market value." },
      { href: "/market/high-iv", title: "High IV", blurb: "Rich options pricing around a dated event." },
    ],
  },
  { key: "search", label: "Search", glyph: "⌕", match: "/search", href: "/search" },
  {
    key: "watchlist", label: "Watchlist", glyph: "☆", match: "/watchlist",
    destinations: [
      { href: "/watchlist", title: "Your watchlist", blurb: "Up to 50 tickers, bucketed by stage." },
    ],
  },
  {
    key: "learn", label: "Learn", glyph: "◎", match: "/learn",
    destinations: [
      { href: "/learn", title: "How it works", blurb: "The anatomy of a breakout, screen by screen." },
      { href: "/learn/backtest", title: "Backtest", blurb: "Settings, result and the trades." },
      { href: "/learn/reading", title: "Reading", blurb: "Guides and case studies." },
      { href: "/legal", title: "Disclaimer", blurb: "What the numbers mean, and what they do not." },
    ],
  },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [openTab, setOpenTab] = useState<string | null>(null);
  const active = TABS.find((t) => pathname.startsWith(t.match))?.key ?? "screens";

  return (
    <>
      <header
        style={{
          position: "sticky", top: 0, zIndex: 30,
          background: "var(--surface-0)",
          borderBottom: "0.5px solid var(--border)",
          padding: "var(--pad-md) var(--pad-lg)",
        }}
      >
        <div className="between" style={{ maxWidth: 780, margin: "0 auto" }}>
          <Link href="/screens" className="grow">
            <div className="row" style={{ gap: "var(--gap-sm)" }}>
              <span
                aria-hidden
                style={{
                  width: 10, height: 10, borderRadius: 2,
                  background: "var(--brand)", display: "inline-block",
                }}
              />
              <strong style={{ fontWeight: 500 }}>Base &amp; Breakout</strong>
            </div>
            <div className="caption dim">{TAGLINE}</div>
          </Link>
          <div className="row" style={{ gap: "var(--gap-sm)" }}>
            <ThemeToggle />
            <AccountButton />
          </div>
        </div>
      </header>

      <main>{children}</main>

      <footer
        style={{
          borderTop: "0.5px solid var(--border)",
          padding: "var(--pad-lg)",
          paddingBottom: 120,
        }}
      >
        <div className="stack" style={{ maxWidth: 780, margin: "0 auto",
                                        gap: "var(--gap-xs)" }}>
          <p className="caption dim" style={{ margin: 0 }}>{LEGAL}</p>
          <Link href="/legal" className="caption dim" style={{ textDecoration: "underline" }}>
            What that means, in full
          </Link>
        </div>
      </footer>

      <nav
        aria-label="Primary"
        style={{
          position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 40,
          background: "var(--surface-1)",
          borderTop: "0.5px solid var(--border)",
          display: "grid", gridTemplateColumns: "repeat(5, 1fr)",
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        {TABS.map((tab) => {
          const isCentre = tab.key === "search";
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              aria-current={isActive ? "page" : undefined}
              onClick={() => (tab.href ? router.push(tab.href) : setOpenTab(tab.key))}
              style={{
                minHeight: "var(--h-control)",
                display: "flex", flexDirection: "column", alignItems: "center",
                justifyContent: "center", gap: 2, padding: "var(--gap-sm) 0",
                background: "none", border: "none", cursor: "pointer",
                color: isActive ? "var(--brand)" : "var(--text-muted)",
              }}
            >
              <span
                aria-hidden
                style={
                  isCentre
                    ? {
                        width: 30, height: 30, borderRadius: "var(--radius-pill)",
                        background: "var(--brand)", color: "var(--on-brand)",
                        display: "grid", placeItems: "center", marginTop: -14,
                      }
                    : { fontSize: 15 }
                }
              >
                {tab.glyph}
              </span>
              <span className="caption">{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {TABS.filter((t) => t.destinations).map((tab) => (
        <Drawer.Root
          key={tab.key}
          open={openTab === tab.key}
          onOpenChange={(open) => setOpenTab(open ? tab.key : null)}
        >
          <Drawer.Portal>
            <Drawer.Overlay style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)" }} />
            <Drawer.Content
              style={{
                position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 60,
                background: "var(--surface-2)",
                borderTop: "0.5px solid var(--border-strong)",
                borderRadius: "var(--radius-card) var(--radius-card) 0 0",
                padding: "var(--pad-lg) var(--pad-lg) var(--pad-xl)",
                maxHeight: "80vh", overflowY: "auto",
              }}
            >
              <div
                aria-hidden
                style={{
                  width: 36, height: 4, borderRadius: "var(--radius-pill)",
                  background: "var(--border-stronger)", margin: "0 auto var(--pad-lg)",
                }}
              />
              <Drawer.Title className="eyebrow">{tab.label}</Drawer.Title>
              <div className="stack" style={{ gap: "var(--gap-sm)" }}>
                {tab.destinations!.map((destination) => (
                  <Link
                    key={destination.href}
                    href={destination.href}
                    onClick={() => setOpenTab(null)}
                    className="card"
                    style={{ padding: "var(--pad-md) var(--pad-lg)", minHeight: "var(--h-control)" }}
                  >
                    <div>{destination.title}</div>
                    <div className="caption dim">{destination.blurb}</div>
                  </Link>
                ))}
              </div>
            </Drawer.Content>
          </Drawer.Portal>
        </Drawer.Root>
      ))}
    </>
  );
}
