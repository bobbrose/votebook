// Privacy guard (M4, T-16, T-17). Also run against deployed sites by `npm run check:prod`.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, lookUp, test, ZIPS, type Seen } from "./fixtures";

const HERE = dirname(fileURLToPath(import.meta.url));
const NOTE = "ask my neighbor about this one";
const EXPECTED_HEADERS = (JSON.parse(readFileSync(join(HERE, "..", "vercel.json"), "utf8")).headers as
  { source: string; headers: { key: string; value: string }[] }[]).find((r) => r.source === "/(.*)")!.headers;

/** Look up a ZIP, decide the first item, write a note. */
async function useTheBallot(page: import("@playwright/test").Page, zip: string) {
  await lookUp(page, zip);
  const card = page.locator(".ballot-item").first();
  await card.locator(".item-row").click();
  await card.locator(".item-panel input").first().check({ force: true });
  await card.getByLabel("Notes").fill(NOTE);
  await page.waitForTimeout(600);   // past the autosave debounce
}

const paths = (seen: Seen[]) => [...new Set(seen.map((s) => new URL(s.url).pathname))].sort();

test("@privacy no request carries the ZIP, a choice or a note (NFR-01, AC-32)", async ({ page, requests }) => {
  await useTheBallot(page, ZIPS[0]);
  await page.reload();
  await page.waitForSelector(".item-row");
  for (const r of requests) {
    for (const secret of [ZIPS[0], NOTE, "neighbor"]) {
      expect(r.url, "request URL").not.toContain(secret);
      expect(r.body, "request body").not.toContain(secret);
    }
    expect(r.body, `${r.url} sends a body`).toBe("");
  }
});

test("@privacy two ZIPs in different counties request the same files (AC-40)", async ({ browser, baseURL }) => {
  const lists: string[][] = [];
  for (const zip of ZIPS.slice(0, 2)) {
    const context = await browser.newContext({ baseURL, serviceWorkers: "block" });
    const page = await context.newPage();
    const seen: Seen[] = [];
    context.on("request", (r) => seen.push({ url: r.url(), body: "" }));
    await useTheBallot(page, zip);
    lists.push(paths(seen));
    await context.close();
  }
  expect(lists[1]).toEqual(lists[0]);
});

test("@privacy no cookies, and the security headers are set (AC-33)", async ({ page, context, request }) => {
  await useTheBallot(page, ZIPS[0]);
  expect(await context.cookies()).toEqual([]);
  for (const path of ["/", "/sw.js", "/data/2026-11-03/counties.json"]) {
    const res = await request.get(path);
    expect(res.status(), path).toBe(200);
    expect(res.headers()["set-cookie"], `${path} sets a cookie`).toBeUndefined();
    for (const h of EXPECTED_HEADERS) expect(res.headers()[h.key.toLowerCase()], `${path} ${h.key}`).toBe(h.value);
  }
});

test("@privacy every script is from this site, with integrity; no inline scripts (NFR-02)", async ({ page }) => {
  await lookUp(page, ZIPS[0]);
  const scripts = await page.$$eval("script", (els) => els.map((e) => ({ src: e.getAttribute("src"), integrity: e.getAttribute("integrity"), inline: e.textContent?.trim() ?? "" })));
  expect(scripts.length).toBeGreaterThan(0);
  for (const s of scripts) {
    expect(s.src, "inline script").toMatch(/^\/assets\/[\w-]+\.js$/);
    expect(s.integrity, `${s.src} integrity`).toMatch(/^sha384-/);
    expect(s.inline).toBe("");
  }
  const styles = await page.$$eval('link[rel="stylesheet"]', (els) => els.map((e) => e.getAttribute("integrity")));
  for (const i of styles) expect(i).toMatch(/^sha384-/);
});

test("@privacy served data files match the published hashes (NFR-07)", async ({ request }) => {
  const list = await (await request.get("/data/2026-11-03/hashes.txt")).text();
  for (const line of list.split("\n").filter(Boolean)) {
    const [hash, name] = line.split(/\s+/);
    const body = await (await request.get(`/data/2026-11-03/${name}`)).body();
    expect(createHash("sha256").update(body).digest("hex"), name).toBe(hash);
  }
});
