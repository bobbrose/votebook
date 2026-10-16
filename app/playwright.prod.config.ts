// `npm run check:prod -- --url <url>`: the privacy and offline checks against a deployed site (hosting.md).
import { defineConfig, devices } from "@playwright/test";

const url = process.env.CHECK_URL;
if (!url) throw new Error("Set CHECK_URL, or run: npm run check:prod -- --url <url>");
const bypass = process.env.VERCEL_BYPASS_SECRET;

export default defineConfig({
  testDir: "e2e",
  grep: /@privacy|@offline/,
  reporter: [["list"]],
  retries: 1,
  use: {
    baseURL: url,
    viewport: { width: 360, height: 740 },
    // Reaches protected preview URLs. No x-vercel-set-bypass-cookie, so the no-cookies check stays valid.
    extraHTTPHeaders: bypass ? { "x-vercel-protection-bypass": bypass } : undefined,
  },
  projects: [{ name: "mobile-chromium", use: { ...devices["Pixel 5"], viewport: { width: 360, height: 740 } } }],
});
