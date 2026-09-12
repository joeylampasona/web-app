"use client";

import { AuthProvider } from "@/lib/auth";
import { SignUpSheet } from "@/components/SignUpSheet";
import { Shell } from "@/components/Shell";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
      <SignUpSheet />
    </AuthProvider>
  );
}
