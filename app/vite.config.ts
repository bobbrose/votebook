/// <reference types="vitest/config" />
import { createHash } from "node:crypto";
import { cpSync, createReadStream, existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import preact from "@preact/preset-vite";

export const ELECTION_DATE = "2026-11-03";
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

const ELECTION_DIR = join("data", ELECTION_DATE);

/** Files listed in a pipeline hashes.txt must match their SHA-256 (AC-37). */
function checkHashes(dir: string) {
  for (const line of readFileSync(join(dir, "hashes.txt"), "utf8").split("\n").filter(Boolean)) {
    const [hash, name] = line.split(/\s+/);
    const got = createHash("sha256").update(readFileSync(join(dir, name))).digest("hex");
    if (got !== hash) throw new Error(`Data file ${name} does not match hashes.txt`);
  }
}

/**
 * Ballot data is never bundled. Dev serves /data from ../data (or app/dev-data with
 * `npm run dev:draft`). A production build copies only ../data and refuses draft or
 * unhashed files, so unverified data cannot be deployed (AC-27, AC-37). E2E tests build
 * with the fictional fixture data instead (E2E_DATA_DIR), which is refused on Vercel.
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
      if (process.env.E2E_DATA_DIR && process.env.VERCEL) throw new Error("E2E_DATA_DIR is for tests only.");
      const base = process.env.E2E_DATA_DIR ? resolve(HERE, process.env.E2E_DATA_DIR) : join(ROOT, "data");
      const src = join(base, ELECTION_DATE);
      const counties = join(src, "counties.json");
      if (!existsSync(counties) || !existsSync(join(src, "hashes.txt"))) {
        throw new Error(`No verified data in ${src}. Run: python -m pipeline.build --election co-${ELECTION_DATE}`);
      }
      if (readFileSync(counties, "utf8").includes('"status":"draft"')) {
        throw new Error("Refusing to build with draft data.");
      }
      checkHashes(src);
      cpSync(src, join(options.dir!, ELECTION_DIR), { recursive: true });
      writeServiceWorker(options.dir!);
    },
  };
}

function walk(dir: string, base = dir): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? walk(full, base) : [relative(base, full).split(sep).join("/")];
  });
}

/** sw.js lists every file in the deploy; its VERSION hashes them all, so any change installs a new cache (C7). */
function writeServiceWorker(out: string) {
  const files = walk(out).filter((f) => f !== "sw.js" && !f.startsWith(`${ELECTION_DIR}/schema/`) && !f.endsWith("hashes.txt"));
  const all = createHash("sha256");
  for (const f of files.sort()) all.update(f).update(readFileSync(join(out, f)));
  const urls = files.map((f) => (f === "index.html" ? "/" : `/${f}`));
  const body = `const VERSION = ${JSON.stringify(all.digest("hex").slice(0, 16))};\n`
    + `const FILES = ${JSON.stringify(urls)};\n` + readFileSync(join(HERE, "sw", "sw.js"), "utf8");
  writeFileSync(join(out, "sw.js"), body);
}

/** Subresource Integrity on every script and stylesheet tag in index.html (NFR-02, tech-spec C8). */
function integrity(): Plugin {
  return {
    name: "subresource-integrity",
    apply: "build",
    enforce: "post",
    transformIndexHtml: {
      order: "post",
      handler(html, ctx) {
        const bundle = ctx.bundle ?? {};
        const sri = (path: string) => {
          const item = bundle[path.replace(/^\//, "")];
          if (!item) throw new Error(`No bundle file for ${path}; cannot add integrity`);
          const src = item.type === "chunk" ? item.code : item.source;
          return `sha384-${createHash("sha384").update(src).digest("base64")}`;
        };
        return html
          .replace(/<script([^>]*?)src="([^"]+)"([^>]*)><\/script>/g, (_m, a, src, b) => `<script${a}src="${src}"${b} integrity="${sri(src)}"></script>`)
          .replace(/<link([^>]*?)href="([^"]+\.(?:css|js))"([^>]*)>/g, (_m, a, href, b) => `<link${a}href="${href}"${b} integrity="${sri(href)}">`);
      },
    },
  };
}

/** `vite preview` sends the same headers as Vercel, read from vercel.json, so e2e tests run under them. */
function vercelHeaders(): Plugin {
  const rules = (JSON.parse(readFileSync(join(HERE, "vercel.json"), "utf8")).headers as
    { source: string; headers: { key: string; value: string }[] }[])
    .map((r) => ({ re: new RegExp(`^${r.source}$`), headers: r.headers }));
  return {
    name: "vercel-headers",
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = (req.url ?? "/").split("?")[0];
        for (const r of rules) if (r.re.test(path)) for (const h of r.headers) res.setHeader(h.key, h.value);
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [preact(), ballotData(), integrity(), vercelHeaders()],
  build: { sourcemap: false, target: "es2022" },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/setup.ts"],
  },
});
