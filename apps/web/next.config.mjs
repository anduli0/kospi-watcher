/** @type {import('next').NextConfig} */

// Where to proxy API calls. Local dev and the public prod server both run on this
// machine, so the API stays internal (127.0.0.1:18080) and is never exposed
// directly — the web proxies it same-origin (see rewrites below).
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:18080";

// A separate build dir for the public prod build (NEXT_DIST_DIR=.next-public) so a
// `next start` public server can run alongside a local `next dev` without the two
// clobbering each other's `.next`.
const DIST_DIR = process.env.NEXT_DIST_DIR ?? ".next";

const nextConfig = {
  reactStrictMode: true,
  distDir: DIST_DIR,
  // Legacy: still exposed for any server-side fallback in lib/api.ts.
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  },
  // Same-origin proxy: the browser calls /api/* and /health on the web origin,
  // and Next forwards them to the local API server-side. This removes any
  // hardcoded localhost from the client bundle and avoids CORS entirely, so the
  // app works behind any public tunnel exactly as it does locally.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` },
      { source: "/health", destination: `${API_PROXY_TARGET}/health` },
    ];
  },
};

export default nextConfig;
