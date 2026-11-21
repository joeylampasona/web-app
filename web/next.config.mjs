/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The pipeline writes the JSON tree; nothing in the web layer queries a
  // database. On Vercel the build script drops it at web/out, which is inside
  // the project root and therefore part of the deployment. Locally it lives at
  // the repository root. Both are traced so the server functions can read it.
  // The share cards are drawn on the server from the stylesheet's colours
  // and from font files beside the code, read by path at request time, so
  // both are named here rather than left to be noticed.
  outputFileTracingIncludes: {
    "/**": ["./out/**", "../out/**"],
    "/share/**": ["./assets/fonts/**", "./styles/tokens.css"],
  },
};

export default nextConfig;
