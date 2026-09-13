"use client";

import { AuthProvider } from "@/lib/auth";
import { SignUpSheet } from "@/components/SignUpSheet";
import { Shell } from "@/components/Shell";
import { StockDrawerProvider } from "@/components/StockDrawer";
import { BarsProvider } from "@/lib/useBars";
import { WatchlistProvider } from "@/lib/useWatchlist";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <WatchlistProvider>
        <BarsProvider>
          <StockDrawerProvider>
            <Shell>{children}</Shell>
            <SignUpSheet />
          </StockDrawerProvider>
        </BarsProvider>
      </WatchlistProvider>
    </AuthProvider>
  );
}
