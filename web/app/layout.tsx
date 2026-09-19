import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { SITE_NAME, TAGLINE } from "@/lib/copy";

/**
 * The address the site is served from, so relative preview-image URLs resolve.
 * Vercel supplies VERCEL_URL per deployment; the explicit variable wins so a
 * custom domain can override it, and localhost is the fallback for development.
 */
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_NAME,
  description: TAGLINE,
  // A pasted link used to render as a grey rectangle with a domain in it. The
  // banner is a supplied image rather than a generated one, so it is named here
  // instead of by app/opengraph-image.
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: SITE_NAME,
    description: TAGLINE,
    images: [{ url: "/og.jpg", width: 1200, height: 630, alt: SITE_NAME }],
  },
  twitter: { card: "summary_large_image", title: SITE_NAME,
             description: TAGLINE, images: ["/og.jpg"] },
  manifest: "/manifest.webmanifest",
  // Without this the browser guesses at /favicon.ico, which does not exist,
  // and every page load carries a 404 that hides real ones in the console.
  icons: { icon: "/icon.png", apple: "/apple-touch-icon.png" },
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: SITE_NAME },
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
