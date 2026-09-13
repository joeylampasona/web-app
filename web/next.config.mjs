/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The pipeline writes the JSON tree; nothing in the web layer queries a
  // database. On Vercel the build script drops it at web/out, which is inside
  // the project root and therefore part of the deployment. Locally it lives at
  // the repository root. Both are traced so the server functions can read it.
  outputFileTracingIncludes: {
    "/**": ["./out/**", "../out/**"],
  },
};

export default nextConfig;
