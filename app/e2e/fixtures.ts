import { test as base, expect, type Page } from "@playwright/test";

/** Every e2e test fails on a request to any other origin (NFR-01, NFR-02). M4 adds the full privacy guard. */
export const test = base.extend<{ page: Page }>({
  page: async ({ page, baseURL }, use) => {
    const offOrigin: string[] = [];
    page.on("request", (r) => { if (!r.url().startsWith(baseURL!) && !r.url().startsWith("data:")) offOrigin.push(r.url()); });
    await use(page);
    expect(offOrigin, "requests to other origins").toEqual([]);
  },
});
export { expect };

export async function lookUp(page: Page, zip: string) {
  await page.goto("/");
  await page.getByLabel("ZIP code").fill(zip);
  await page.getByRole("button", { name: "Look up" }).click();
  await page.waitForSelector(".item-row");
}
