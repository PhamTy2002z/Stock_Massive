const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep production E2E builds away from a developer's active `.next` tree.
  // Docker and normal builds keep Next's default unless the harness opts in.
  distDir: Reflect.get(process, "env").E2E_NEXT_DIST_DIR || ".next",

  // Enable standalone output for Docker production builds
  output: "standalone",

  // Pin the tracing root to this checkout. Left to inference, Next.js picks the
  // outermost pnpm-lock.yaml it can find — in a git worktree that is the main
  // repo's, which shifts the standalone layout and breaks the e2e server copy
  // step in playwright.config.ts.
  outputFileTracingRoot: path.join(__dirname, "../.."),

  // Nothing here renders through `next/image` — favicons come from our own
  // proxy and previews are `blob:` URLs, both plain `<img>`. Turning the
  // optimizer off closes `/_next/image`, a public endpoint that fetches and
  // decodes images on the server and has carried remote-code-execution bugs.
  images: { unoptimized: true },

  poweredByHeader: false,

  // One set for every route, including the Route Handlers, so a Settings page
  // cannot be framed for clickjacking and no response is MIME-sniffed.
  //
  // The CSP is partial on purpose: no `default-src` or `script-src`, because
  // Next's own inline bootstrap, the motion boot script in `app/layout.tsx` and
  // the inline styles React and the chart write would all need nonces or hashes
  // first. `img-src` still matters without them: every legitimate image is
  // same-origin (the favicon proxy, attachments) or a local `blob:`/`data:`
  // preview, so an answer cannot load a tracking pixel from a third party.
  async headers() {
    const csp = [
      "img-src 'self' data: blob:",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; ")
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ]
  },

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
