/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The pipeline writes out/ at the repository root. Nothing in the web layer
  // queries a database; the one exception is the custom backtest API route.
  outputFileTracingIncludes: {
    "/**": ["../out/**"],
  },
};

export default nextConfig;
