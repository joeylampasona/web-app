"use client";

import { AuthProvider } from "@/lib/auth";
import { Shell } from "@/components/Shell";
import { StockDrawerProvider } from "@/components/StockDrawer";
import { BarsProvider } from "@/lib/useBars";
import { QuotesProvider } from "@/lib/useQuotes";
import { WatchlistProvider } from "@/lib/useWatchlist";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <WatchlistProvider>
        <BarsProvider>
          <QuotesProvider>
            <StockDrawerProvider>
              <Shell>{children}</Shell>
            </StockDrawerProvider>
          </QuotesProvider>
        </BarsProvider>
      </WatchlistProvider>
    </AuthProvider>
  );
}
