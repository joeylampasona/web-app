"use client";

import { AuthProvider } from "@/lib/auth";
import { SignUpSheet } from "@/components/SignUpSheet";
import { Shell } from "@/components/Shell";
import { StockDrawerProvider } from "@/components/StockDrawer";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <StockDrawerProvider>
        <Shell>{children}</Shell>
        <SignUpSheet />
      </StockDrawerProvider>
    </AuthProvider>
  );
}
