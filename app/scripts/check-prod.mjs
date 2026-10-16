#!/usr/bin/env node
// Usage: npm run check:prod -- --url https://example.vercel.app [--zips 80302,80524]
// Runs the @privacy and @offline e2e checks against a deployed site. Real Colorado ZIPs by default.
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const get = (flag) => { const i = args.indexOf(flag); return i >= 0 ? args[i + 1] : undefined; };
const url = get("--url");
if (!url) {
  console.error("Usage: npm run check:prod -- --url <deployed url> [--zips 80302,80524]");
  process.exit(2);
}
const env = { ...process.env, CHECK_URL: url.replace(/\/$/, ""), CHECK_ZIPS: get("--zips") ?? "80302,80524" };
const r = spawnSync("npx", ["playwright", "test", "-c", "playwright.prod.config.ts"], { stdio: "inherit", env });
process.exit(r.status ?? 1);
