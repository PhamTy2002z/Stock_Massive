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
