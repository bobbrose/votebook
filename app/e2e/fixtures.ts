import { test as base, expect, type Page, type Request } from "@playwright/test";

export interface Seen { url: string; body: string }

/**
 * Every e2e test records every request the page and its service worker make, and fails on any request
 * to another origin (NFR-01, NFR-02, AC-32). Tests read `requests` for stricter checks.
 */
export const test = base.extend<{ page: Page; requests: Seen[] }>({
  requests: async ({}, use) => { await use([]); },
  page: async ({ page, context, baseURL, requests }, use) => {
    const origin = new URL(baseURL!).origin;
    const offOrigin: string[] = [];
    const record = (r: Request) => {
      const url = r.url();
      if (url.startsWith("data:")) return;
      requests.push({ url, body: r.postData() ?? "" });
      if (new URL(url).origin !== origin) offOrigin.push(url);
    };
    context.on("request", record);   // includes requests from the service worker
    await use(page);
    expect(offOrigin, "requests to other origins").toEqual([]);
  },
});
export { expect };

/** ZIPs for the privacy checks: two ZIPs in different counties. check:prod sets real ones. */
export const ZIPS = (process.env.CHECK_ZIPS ?? "80001,80003").split(",");

export async function lookUp(page: Page, zip: string) {
  await page.goto("/");
  await page.getByLabel("ZIP code").fill(zip);
  await page.getByRole("button", { name: "Look up" }).click();
  await page.waitForSelector(".item-row");
}
