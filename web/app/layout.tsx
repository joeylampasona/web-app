import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { TAGLINE } from "@/lib/copy";

export const metadata: Metadata = {
  title: "Base & Breakout",
  description: TAGLINE,
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Base & Breakout" },
  other: { "apple-mobile-web-app-capable": "yes" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // The page canvas, --surface-0. Browser chrome cannot read a CSS variable.
  themeColor: "#0C0D12",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Dark is shipped as the initial state; ThemeToggle respects
  // prefers-color-scheme on first load only.
  return (
    <html lang="en" data-theme="dark">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
