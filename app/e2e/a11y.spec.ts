// Automated accessibility and layout checks (NFR-05 automated part, NFR-09; AC-36, AC-39).
import AxeBuilder from "@axe-core/playwright";
import { expect, lookUp, test, ZIPS } from "./fixtures";
import type { Page } from "@playwright/test";

async function check(page: Page, label: string) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`), label).toEqual([]);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, `${label}: horizontal scroll at 360 px`).toBeLessThanOrEqual(0);
}

test("@a11y every pilot screen has no axe violations and no horizontal scroll at 360 px", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("ZIP code").waitFor();
  await check(page, "home");

  await lookUp(page, ZIPS[0]);
  await check(page, "ballot");
  for (const card of await page.locator(".ballot-item").all()) await card.locator(".item-row").click();
  await check(page, "ballot, every card open");

  const first = page.locator(".ballot-item").first();
  await first.getByRole("link", { name: /Learn more/ }).click();
  await page.locator("h1").waitFor();
  await check(page, "item detail");

  for (const [path, label] of [["/#/write-out", "write-out"], ["/#/data", "your data"], ["/#/privacy", "privacy"], ["/#/basics", "voting basics"]]) {
    await page.goto(path);
    await page.locator("main").waitFor();
    await check(page, label);
  }
});
