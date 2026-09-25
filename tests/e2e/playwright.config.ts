import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  timeout: 90_000,
  retries: 0,
  use: {
    baseURL: process.env.P8_WEB_URL ?? "http://127.0.0.1:5173",
    headless: true,
  },
});
