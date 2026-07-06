/** @type {import('next').NextConfig} */

// Where to proxy API calls. Local dev and the public prod server both run on this
// machine, so the API stays internal (127.0.0.1:18080) and is never exposed
// directly — the web proxies it same-origin (see rewrites below).
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:18080";

// A separate build dir for the public prod build (NEXT_DIST_DIR=.next-public) so a
// `next start` public server can run alongside a local `next dev` without the two
// clobbering each other's `.next`.
const DIST_DIR = process.env.NEXT_DIST_DIR ?? ".next";

// Static-snapshot mode: the always-on cloud build for GitHub Pages. It has no
// live backend — pages read pre-generated JSON snapshots (see lib/api.ts). Next
// then emits a fully static site (`output: "export"`) under `out/`, served from
// a project subpath (basePath, e.g. "/kospi-watcher"). The live PC build leaves
// STATIC unset and keeps the same-origin API proxy, so it is unchanged.
const STATIC = process.env.NEXT_PUBLIC_STATIC_SNAPSHOT === "1";
// Accept the base path with or without a leading slash (Git Bash on Windows
// mangles a leading-slash env value into a path), then normalize to "/name".
const RAW_BASE = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/^\/+|\/+$/g, "");
const BASE_PATH = RAW_BASE ? `/${RAW_BASE}` : "";

/** @type {import('next').NextConfig} */
const staticConfig = {
  reactStrictMode: true,
  distDir: DIST_DIR,
  output: "export",
  basePath: BASE_PATH || undefined,
  assetPrefix: BASE_PATH || undefined,
  trailingSlash: true, // Pages serves /route/ as /route/index.html
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_STATIC_SNAPSHOT: "1",
    NEXT_PUBLIC_BASE_PATH: BASE_PATH,
  },
};

/** @type {import('next').NextConfig} */
const liveConfig = {
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

export default STATIC ? staticConfig : liveConfig;
