import { fileURLToPath } from "node:url"
import { defineConfig } from "vitest/config"

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    // Every test mocks the Supabase client — the suite never touches the network
    // or needs real keys, so it runs the same locally and in CI.
    restoreMocks: true,
    unstubEnvs: true,
  },
})
