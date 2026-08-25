import { defineConfig, devices } from "@playwright/test"

/**
 * The end-to-end streaming acceptance (#92), and the path it runs through.
 *
 * Two servers, started by Playwright and torn down with it: a **real FastAPI**
 * (`apps/api/tests/e2e/server.py` — the production app with the model replaced
 * by a Turn the test drives) and a **real Next production build** pointed at it
 * over `INTERNAL_API_URL`. The browser talks only to Next.
 *
 * That third hop is the entire point. Unit tests on either side of the proxy
 * prove the two halves; they cannot prove that an intermediary streams, because
 * with both halves in one process there is no intermediary. A harness that
 * buffers looks identical to one that is hung, and only bytes arriving early on
 * a real socket tell them apart (ADR-0013).
 *
 * **Production build, not `next dev`.** The buffering this test exists to catch
 * is a property of the build that ships, and a dev server is not it.
 *
 * How to run it, and what it needs, is in `docs/streaming-topology.md`.
 */

const API_PORT = Number(process.env.E2E_API_PORT ?? 8010)
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3010)

const API_ORIGIN = `http://127.0.0.1:${API_PORT}`
const WEB_ORIGIN = `http://127.0.0.1:${WEB_PORT}`
const E2E_DIST_DIR = ".next-e2e"

export default defineConfig({
  testDir: "./e2e",
  // One worker: the harness drives a single Turn through control endpoints, and
  // two specs steering it at once would each see the other's events.
  workers: 1,
  fullyParallel: false,
  // Generous, because one property under test is a fifteen-second heartbeat.
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI ? "list" : "line",
  use: {
    baseURL: WEB_ORIGIN,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        ".venv/bin/python -m uvicorn tests.e2e.server:app " +
        `--host 127.0.0.1 --port ${API_PORT} --log-level warning`,
      cwd: "../api",
      url: `${API_ORIGIN}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        // The scheduler would start a collection cycle against a live provider,
        // and the probe would spend money on a route that does not exist. The
        // transport under test needs neither.
        SCHEDULER_ENABLED: "false",
        LLM_CAPABILITY_PROBE_ENABLED: "false",
        // The service the endpoints read is installed by the harness with a
        // funded configuration of its own; this only keeps Budget Validation
        // from refusing to boot over the placeholder route.
        ALPHA_DESK_ENABLED: "false",
        CORS_ORIGINS: `${WEB_ORIGIN},${API_ORIGIN}`,
      },
    },
    {
      // The standalone server, assembled exactly as `Dockerfile.prod` does —
      // build, then copy the static assets and `public/` beside `server.js`.
      // `next start` is not what the image runs, and Next says so out loud when
      // `output: "standalone"` is configured.
      command:
        "bash scripts/run-e2e-web-server.sh",
      cwd: ".",
      url: WEB_ORIGIN,
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
      env: {
        PORT: String(WEB_PORT),
        // What the image sets, and the reason the proxy's origin check reads
        // the request's own host: bound to 0.0.0.0, `nextUrl.origin` says
        // `http://0.0.0.0:3010` for every request whatever the browser asked
        // for.
        HOSTNAME: "0.0.0.0",
        // The route handler's internal hop — the one `docker-compose.prod.yml`
        // has to configure so a deployment does not fall back to the public
        // build-time URL.
        INTERNAL_API_URL: `${API_ORIGIN}/api/v1`,
        // Build-time, and therefore part of the build this test drives.
        NEXT_PUBLIC_API_URL: `${API_ORIGIN}/api/v1`,
        NODE_ENV: "production",
        E2E_NEXT_DIST_DIR: E2E_DIST_DIR,
      },
    },
  ],
})

export { API_ORIGIN, WEB_ORIGIN }
