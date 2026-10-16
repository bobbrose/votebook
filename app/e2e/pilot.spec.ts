import { expect, lookUp, test } from "./fixtures";

test("F1: look up a ZIP and research everything that could be on a ballot there (AC-01, AC-02, AC-07)", async ({ page }) => {
  await lookUp(page, "80001");
  const titles = await page.locator(".item-title").allTextContents();
  expect(titles[0]).toBe("United States Senator");
  expect(titles).toContain("State Representative - District 2");
  await expect(page.getByText("Depends on your district: State House District 1")).toBeVisible();
  await expect(page.getByText("Researching ZIP 80001.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Narrow my ballot" })).toHaveCount(0);
});

test("Searching the ballot filters it to matching cards", async ({ page }) => {
  await lookUp(page, "80001");
  const search = page.getByLabel("Search the ballot");
  await search.fill("blake");
  expect(await page.locator(".item-title").allTextContents()).toEqual(["United States Senator"]);
  await expect(page.getByText("Showing 1 of 10 items")).toBeVisible();
  await search.fill("charter");
  expect(await page.locator(".item-title").allTextContents()).toEqual(["City of Alpha Ballot Question 2A"]);
  await search.fill("zzz");
  await expect(page.getByText('Nothing on this ballot matches "zzz".')).toBeVisible();
  await search.fill("");
  await expect(page.locator(".item-title")).toHaveCount(10);
});

test("F2: decide a measure and write a note; both survive a reload (AC-12, AC-15, AC-16, AC-21)", async ({ page }) => {
  await lookUp(page, "80001");
  await page.getByText("Amendment 1", { exact: true }).click();
  await page.locator(".segmented label", { hasText: "No" }).click();
  await page.getByLabel("Notes").fill("ask about cost");
  await expect(page.locator(".progress-count")).toHaveText("1 of 10 decided");
  await page.waitForTimeout(500);
  await page.reload();
  // Collapsed after the reload: the row shows the choice and a check mark.
  const row = page.locator(".ballot-item", { hasText: "Amendment 1" });
  await expect(row.locator(".item-choice")).toHaveText("No");
  await expect(row.locator(".check")).toBeVisible();
  await row.locator(".item-row").click();
  await expect(page.locator(".segmented label.selected")).toHaveText("No");
  await expect(page.getByLabel("Notes")).toHaveValue("ask about cost");
});

test("Ballot rows open to decide in place; Learn more opens the full item and comes back", async ({ page }) => {
  await lookUp(page, "80001");
  const row = page.locator(".ballot-item", { hasText: "United States Senator" });
  await row.locator(".item-row").click();
  await expect(row.locator(".item-row")).toHaveAttribute("aria-expanded", "true");
  await row.locator("label.candidate").first().click();
  await expect(page.locator(".progress-count")).toHaveText("1 of 10 decided");
  await row.locator(".item-row").click();
  await expect(row.locator(".check")).toBeVisible();
  await expect(row.locator(".item-choice")).not.toHaveText("Undecided");
  await row.locator(".item-row").click();
  await row.getByRole("link", { name: /Learn more/ }).click();
  await expect(page.locator("h1")).toHaveText("United States Senator");
  await page.goBack();
  await expect(row.locator(".item-row")).toHaveAttribute("aria-expanded", "true");
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

test("Select all from a party sets those races; Clear clears them", async ({ page }) => {
  await lookUp(page, "80001");
  page.on("dialog", (d) => d.accept());
  const senate = page.locator(".ballot-item", { hasText: "United States Senator" }).locator(".item-choice");
  await page.getByLabel("Party").selectOption("Party B");
  await page.getByRole("button", { name: "Select all" }).click();
  await expect(senate).toHaveText("Blake Sample Party B");
  // Switching parties replaces the earlier picks.
  await page.getByLabel("Party").selectOption("Party A");
  await page.getByRole("button", { name: "Select all" }).click();
  await expect(senate).toHaveText("Avery Sample Party A");
  await page.getByRole("button", { name: "Clear" }).click();
  await expect(page.locator(".progress-count")).toHaveText("0 of 10 decided");
});
