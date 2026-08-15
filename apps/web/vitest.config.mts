import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  // The component tests are .tsx, and nothing else here would tell the
  // transformer that. The plugin compiles them the way Next.js does, so a
  // component behaves in a test the way it does in the app.
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // `server-only` is a guard resolved by export condition: an empty module
      // under `react-server`, a throwing one otherwise. Vitest sets no such
      // condition and gets the throwing side, so importing a route handler dies
      // at the import. Pointed straight at the empty build — by file, because
      // the package's `exports` map offers no subpath to ask for it.
      "server-only": fileURLToPath(
        new URL("./node_modules/server-only/empty.js", import.meta.url),
      ),
    },
  },
  test: {
    // Node by default, because most of these tests are plain functions. The
    // component tests ask for a DOM per file with a `@vitest-environment`
    // docblock, so a browser environment is only paid for where one is used.
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["./vitest.setup.ts"],
  },
})
