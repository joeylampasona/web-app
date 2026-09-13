"use client";

import { AuthProvider } from "@/lib/auth";
import { SignUpSheet } from "@/components/SignUpSheet";
import { Shell } from "@/components/Shell";
import { StockDrawerProvider } from "@/components/StockDrawer";
import { WatchlistProvider } from "@/lib/useWatchlist";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <WatchlistProvider>
        <StockDrawerProvider>
          <Shell>{children}</Shell>
          <SignUpSheet />
        </StockDrawerProvider>
      </WatchlistProvider>
    </AuthProvider>
  );
}
