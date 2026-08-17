const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker production builds
  output: "standalone",

  // Pin the tracing root to this checkout. Left to inference, Next.js picks the
  // outermost pnpm-lock.yaml it can find — in a git worktree that is the main
  // repo's, which shifts the standalone layout and breaks the e2e server copy
  // step in playwright.config.ts.
  outputFileTracingRoot: path.join(__dirname, "../.."),

  // Preview-only: proxy /api/v1 to the running API container so the browser
  // stays same-origin. The API's CORS_ORIGINS only allows localhost:3000, and
  // this preview runs on 3001. Opt in with PREVIEW_API_PROXY_TARGET.
  async rewrites() {
    const target = process.env.PREVIEW_API_PROXY_TARGET
    if (!target) return []
    return [{ source: "/api/v1/:path*", destination: `${target}/:path*` }]
  },
};

module.exports = nextConfig;
