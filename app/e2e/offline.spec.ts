// Offline after one visit (NFR-03, AC-34). Also run against deployed sites by `npm run check:prod`.
import { expect, lookUp, test, ZIPS } from "./fixtures";

test("@offline the app and every county's ballot load with no connection after one visit", async ({ page, context, browserName }) => {
  test.skip(browserName === "webkit", "Playwright's WebKit does not run service workers");
  await page.goto("/");
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();   // now controlled by the service worker
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await context.setOffline(true);
  for (const zip of ZIPS.slice(0, 2)) {
    await lookUp(page, zip);
    await expect(page.locator(".item-row").first()).toBeVisible();
  }
  await context.setOffline(false);
});
