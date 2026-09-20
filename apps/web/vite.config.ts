import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@alignerstudio/contracts": new URL(
        "../../packages/contracts/src/index.ts",
        import.meta.url,
      ).pathname,
      "@alignerstudio/math": new URL(
        "../../packages/math/src/index.ts",
        import.meta.url,
      ).pathname,
      "@alignerstudio/types": new URL(
        "../../packages/types/src/index.ts",
        import.meta.url,
      ).pathname,
    },
  },
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
