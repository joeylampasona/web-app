"use client";

import { AuthProvider } from "@/lib/auth";
import { Shell } from "@/components/Shell";
import { StockDrawerProvider } from "@/components/StockDrawer";
import { BarsProvider } from "@/lib/useBars";
import { QuotesProvider } from "@/lib/useQuotes";
import { WatchlistProvider } from "@/lib/useWatchlist";
import type { TapeData } from "@/lib/tape";

export function Providers({ children, tape }: {
  children: React.ReactNode; tape: TapeData | null;
}) {
  return (
    <AuthProvider>
      <WatchlistProvider>
        <BarsProvider>
          <QuotesProvider>
            <StockDrawerProvider>
              <Shell tape={tape}>{children}</Shell>
            </StockDrawerProvider>
          </QuotesProvider>
        </BarsProvider>
      </WatchlistProvider>
    </AuthProvider>
  );
}
