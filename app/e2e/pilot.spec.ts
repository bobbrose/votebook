import { expect, lookUp, test } from "./fixtures";

test("F1: look up a ZIP, see conditional items, and narrow (AC-01, AC-02, AC-06, AC-07)", async ({ page }) => {
  await lookUp(page, "80001");
  const titles = await page.locator(".item-title").allTextContents();
  expect(titles[0]).toBe("United States Senator");
  expect(titles).toContain("State Representative - District 2");
  await expect(page.getByText("Depends on your district: State House District 1")).toBeVisible();
  await page.getByRole("button", { name: "Narrow my ballot" }).click();
  await page.getByLabel("State House district").selectOption("co-house-1");
  await page.getByRole("button", { name: "Done" }).click();
  expect(await page.locator(".item-title").allTextContents()).not.toContain("State Representative - District 2");
});

test("F2: decide a measure and write a note; both survive a reload (AC-12, AC-15, AC-16, AC-21)", async ({ page }) => {
  await lookUp(page, "80001");
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "No" }).click();
  await page.getByLabel("My note").fill("ask about cost");
  await expect(page.locator(".progress-count")).toHaveText("1 of 9 decided");
  await page.waitForTimeout(500);
  await page.reload();
  await expect(page.locator(".segmented label.selected")).toHaveText("No");
  await expect(page.getByLabel("My note")).toHaveValue("ask about cost");
});

test("F4: write out, toggle, and print without page chrome (AC-17 to AC-20)", async ({ page }) => {
  await lookUp(page, "80001");
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "Yes" }).click();
  await page.goto("/#/write-out");
  await expect(page.locator(".plan")).toContainText("Amendment 1 ... Yes");
  await page.getByLabel("Include undecided").check();
  await expect(page.locator(".plan")).toContainText("United States Senator ... Undecided");
  await expect(page.getByText(/received/).first()).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".progress")).toBeHidden();
  await expect(page.getByRole("button", { name: "Print" })).toBeHidden();
  await expect(page.locator(".plan")).toBeVisible();
});

test("F6: private session stores nothing, even after a reload (AC-23)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /shared computer/ }).click();
  await page.getByLabel("ZIP code").fill("80001");
  await page.getByRole("button", { name: "Look up" }).click();
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "Yes" }).click();
  await expect(page.getByText("Closing this tab erases your choices.")).toBeVisible();
  await page.waitForTimeout(500);
  const dbs = async () => page.evaluate(async () => (await indexedDB.databases()).map((d) => d.name));
  expect(await dbs()).not.toContain("ballot-explorer");
  // A reload keeps the tab in private session and still stores nothing.
  page.on("dialog", (d) => d.accept());
  await page.reload();
  await expect(page.getByText("Private session: nothing is kept on this computer.").first()).toBeVisible();
  await page.getByLabel("ZIP code").fill("80001");
  await page.getByRole("button", { name: "Look up" }).click();
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "No" }).click();
  await page.waitForTimeout(500);
  expect(await dbs()).not.toContain("ballot-explorer");
});

// Mobile browsers do not reliably show leave-page prompts (tech-spec C5), so this checks desktop Chromium.
test("F6: private session asks before closing a tab with work in it (AC-46)", async ({ browser, browserName, baseURL }) => {
  test.skip(browserName !== "chromium", "beforeunload prompts are checked in desktop Chromium");
  const context = await browser.newContext({ baseURL, isMobile: false, hasTouch: false, viewport: { width: 1000, height: 800 } });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: /shared computer/ }).click();
  await page.getByLabel("ZIP code").fill("80001");
  await page.getByRole("button", { name: "Look up" }).click();
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "Yes" }).click();
  await expect(page.getByText("Closing this tab erases your choices.")).toBeVisible();
  await page.waitForTimeout(300); // the handler is registered in an effect just after the first choice
  let prompted = false;
  page.on("dialog", async (d) => { prompted = d.type() === "beforeunload"; await d.dismiss(); });
  await page.close({ runBeforeUnload: true });
  await expect.poll(() => prompted).toBe(true);
  await context.close();
});

test("F7: Clear everything leaves nothing after a reload (AC-22)", async ({ page }) => {
  await lookUp(page, "80001");
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "Yes" }).click();
  await page.waitForTimeout(500);
  await page.goto("/#/data");
  await page.getByRole("button", { name: "Clear everything" }).click();
  await page.getByRole("button", { name: "Delete" }).click();
  await page.reload();
  await expect(page.getByText(/Continue your ballot/)).toHaveCount(0);
  const dbs = await page.evaluate(async () => (await indexedDB.databases()).map((d) => d.name));
  expect(dbs).not.toContain("ballot-explorer");
});

test("F8: a ZIP outside Colorado shows the state's site and no ballot (AC-03)", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("ZIP code").fill("84101");
  await page.getByRole("button", { name: "Look up" }).click();
  await expect(page.getByText(/covers Colorado ballots only/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Utah voter information/ })).toHaveAttribute("href", "https://vote.gov/register/utah");
  await expect(page.locator(".item-row")).toHaveCount(0);
});

test("360 px: no horizontal scrolling on any screen (AC-39)", async ({ page }) => {
  await lookUp(page, "80001");
  for (const route of ["/#/", "/#/ballot", "/#/item/amendment-1", "/#/item/alpha-council", "/#/write-out", "/#/data", "/#/privacy"]) {
    await page.goto(route);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, route).toBeLessThanOrEqual(0);
  }
});

test("the progress bar stays visible while scrolling (AC-42)", async ({ page }) => {
  await lookUp(page, "80001");
  await page.evaluate(() => window.scrollTo(0, 2000));
  await page.waitForTimeout(200);
  const box = await page.locator(".progress").boundingBox();
  expect(box!.y).toBeLessThanOrEqual(1);
  await expect(page.locator(".progress-count")).toBeInViewport();
});
