/// <reference types="vitest/config" />
import { cpSync, existsSync, readFileSync, createReadStream, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import preact from "@preact/preset-vite";

export const ELECTION_DATE = "2026-11-03";
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

/**
 * Ballot data is never bundled. Dev serves /data from ../data (or app/dev-data with
 * `npm run dev:draft`). A production build copies only ../data and refuses draft or
 * unhashed files, so unverified data cannot be deployed (AC-27, AC-37).
 */
function ballotData(): Plugin {
  const devDir = process.env.BALLOT_DATA_DIR ? resolve(HERE, process.env.BALLOT_DATA_DIR) : join(ROOT, "data");
  return {
    name: "ballot-data",
    configureServer(server) {
      server.middlewares.use("/data", (req, res, next) => {
        const file = join(devDir, decodeURIComponent((req.url ?? "/").split("?")[0]));
        if (!file.startsWith(devDir) || !existsSync(file) || !statSync(file).isFile()) return next();
        res.setHeader("Content-Type", file.endsWith(".json") ? "application/json" : "text/plain");
        createReadStream(file).pipe(res);
      });
    },
    writeBundle(options) {
      const src = join(ROOT, "data", ELECTION_DATE);
      const counties = join(src, "counties.json");
      if (!existsSync(counties) || !existsSync(join(src, "hashes.txt"))) {
        throw new Error(`No verified data in ${src}. Run: python -m pipeline.build --election co-${ELECTION_DATE}`);
      }
      if (readFileSync(counties, "utf8").includes('"status":"draft"')) {
        throw new Error("Refusing to build with draft data.");
      }
      cpSync(src, join(options.dir!, "data", ELECTION_DATE), { recursive: true });
    },
  };
}

export default defineConfig({
  plugins: [preact(), ballotData()],
  build: { sourcemap: false, target: "es2022" },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/setup.ts"],
  },
});
