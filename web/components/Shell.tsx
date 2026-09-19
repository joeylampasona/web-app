"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Drawer } from "vaul";
import { LEGAL, SITE_NAME, TAGLINE } from "@/lib/copy";
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
      { href: "/screens/flat_base", title: "Flat base", blurb: "A shallow, level shelf near the highs." },
      { href: "/screens/cup_and_handle", title: "Cup and handle", blurb: "A rounded bottom, then a small pause below the lid." },
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
      { href: "/market/calendar", title: "The calendar", blurb: "Earnings, ex-dividends and splits, day by day." },
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
    <div className="shell">
      <SideNav tabs={TABS} pathname={pathname} active={active} />

      <div style={{ minWidth: 0 }}>
      <header
        style={{
          position: "sticky", top: 0, zIndex: 30,
          background: "var(--surface-0)",
          borderBottom: "0.5px solid var(--border)",
          // The viewport is viewportFit: "cover", so the page runs underneath
          // the status bar and the Dynamic Island. Without this the header sits
          // under them and its buttons cannot be tapped at all. The bottom nav
          // has always had the matching inset; the top never did.
          paddingTop: "calc(var(--pad-md) + env(safe-area-inset-top))",
          paddingBottom: "var(--pad-md)",
          paddingLeft: "calc(var(--pad-lg) + env(safe-area-inset-left))",
          paddingRight: "calc(var(--pad-lg) + env(safe-area-inset-right))",
        }}
      >
        <div className="between shell-width">
          <Link href="/screens" className="grow">
            <div className="row" style={{ gap: "var(--gap-sm)" }}>
              <span
                aria-hidden
                style={{
                  width: 10, height: 10, borderRadius: 2,
                  background: "var(--brand)", display: "inline-block",
                }}
              />
              <strong style={{ fontWeight: 500 }}>{SITE_NAME}</strong>
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
          paddingBottom: "var(--page-bottom)",
        }}
      >
        <div className="stack shell-width" style={{ gap: "var(--gap-xs)" }}>
          <p className="caption dim" style={{ margin: 0 }}>{LEGAL}</p>
          <Link href="/legal" className="caption dim" style={{ textDecoration: "underline" }}>
            What that means, in full
          </Link>
        </div>
      </footer>

      <nav
        aria-label="Primary"
        className="tabbar"
        style={{
          position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 40,
          background: "var(--surface-1)",
          borderTop: "0.5px solid var(--border)",
          display: "grid", gridTemplateColumns: "repeat(5, 1fr)",
          paddingBottom: "env(safe-area-inset-bottom)",
          paddingLeft: "env(safe-area-inset-left)",
          paddingRight: "env(safe-area-inset-right)",
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
            {/* Same shape as the stock sheet: a handle that stays put and one
                scrolling pane, so dragging dismisses and scrolling scrolls.
                This list was short enough to get away with it; it is eight
                destinations now and a small phone would have hit the same
                wall. */}
            <Drawer.Content
              style={{
                position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 60,
                background: "var(--surface-2)",
                borderTop: "0.5px solid var(--border-strong)",
                borderRadius: "var(--radius-card) var(--radius-card) 0 0",
                maxHeight: "80vh", overflow: "hidden",
                display: "flex", flexDirection: "column",
              }}
            >
              <div style={{ flexShrink: 0, padding: "var(--pad-lg) var(--pad-lg) 0" }}>
                <div
                  aria-hidden
                  style={{
                    width: 36, height: 4, borderRadius: "var(--radius-pill)",
                    background: "var(--border-stronger)", margin: "0 auto var(--pad-lg)",
                  }}
                />
                <Drawer.Title className="eyebrow">{tab.label}</Drawer.Title>
              </div>
              <div className="stack" style={{
                gap: "var(--gap-sm)", flex: 1, minHeight: 0, overflowY: "auto",
                overscrollBehavior: "contain", WebkitOverflowScrolling: "touch",
                padding: "var(--gap-sm) var(--pad-lg)",
                paddingBottom: "calc(var(--pad-xl) + env(safe-area-inset-bottom))",
              }}>
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
      </div>
    </div>
  );
}

/**
 * The same destinations as the tab bar, as a column.
 *
 * A row of thumb-reach tap targets along the bottom edge is the one part of a
 * phone layout that does not translate to a monitor — it is the furthest point
 * from where the eye and the pointer already are. So on a wide screen the tabs
 * become a sidebar and the sheets are not needed at all: there is room to show
 * a section's destinations in place, which is one fewer tap and one fewer thing
 * covering the page.
 *
 * Rendered always and hidden by CSS below 1024px, so there is no width probe in
 * JavaScript and nothing to flash or mismatch on hydration.
 */
function SideNav({ tabs, pathname, active }: {
  tabs: typeof TABS; pathname: string; active: string;
}) {
  // The section you are in is open; opening another closes it.
  const [open, setOpen] = useState<string | null>(null);
  const expanded = open ?? active;

  return (
    <aside className="sidenav" aria-label="Primary">
      {tabs.map((tab) => {
        const isActive = active === tab.key;
        const isOpen = expanded === tab.key && Boolean(tab.destinations);
        const row = (
          <span className="row" style={{ gap: "var(--gap-sm)" }}>
            <span aria-hidden style={{ width: 16, display: "inline-block" }}>{tab.glyph}</span>
            <span>{tab.label}</span>
          </span>
        );
        return (
          <div key={tab.key}>
            {tab.href ? (
              <Link href={tab.href} className="sidenav-item"
                    aria-current={isActive ? "page" : undefined}>
                {row}
              </Link>
            ) : (
              <button type="button" className="sidenav-item" data-active={isActive}
                      aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? "" : tab.key)}>
                {row}
              </button>
            )}
            {isOpen && tab.destinations!.map((destination) => (
              <Link
                key={destination.href}
                href={destination.href}
                className="sidenav-link"
                aria-current={pathname === destination.href ? "page" : undefined}
                title={destination.blurb}
              >
                {destination.title}
              </Link>
            ))}
          </div>
        );
      })}
    </aside>
  );
}
