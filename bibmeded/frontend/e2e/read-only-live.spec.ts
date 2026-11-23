import { expect, test } from "@playwright/test";

// Opt-in: runs against a real backend started with BIBMEDED_READ_ONLY=true and a
// frontend built with NEXT_PUBLIC_API_URL pointing at it. No API mocking.
test.skip(!process.env.PLAYWRIGHT_LIVE_READ_ONLY, "set PLAYWRIGHT_LIVE_READ_ONLY=1 to run against a live read-only backend");

test("live read-only demo serves the seeded sample without issuing writes", async ({ page }) => {
  const writes: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/") && !["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${request.url()}`);
    }
  });

  await page.goto("/");
  await expect(page.getByText("Read-only demo")).toBeVisible();
  await page.getByRole("link", { name: /Open project AI in Medical Education/ }).click();

  await expect(page.getByRole("heading", { name: "Results Review" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Excluded: "Equity and access/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Exclude 0-citation papers" })).toHaveCount(0);

  await page.getByRole("button", { name: "View analysis" }).click();
  await page.waitForLoadState("networkidle");
  expect(pageErrors).toEqual([]);
  await expect(page.getByRole("heading", { name: "Analysis Overview" })).toBeVisible();
  await expect(page.getByText("Marcus Chen Sample").first()).toBeAttached();

  const projectPath = new URL(page.url()).pathname.replace(/\/dashboard$/, "");
  await page.goto(`${projectPath}/export`);
  const downloads: string[] = [];
  page.on("download", (download) => downloads.push(download.suggestedFilename()));
  await page.getByRole("tab", { name: "Reporting" }).click();
  const diagram = page.getByRole("img", { name: /PRISMA 2020 flow diagram/ });
  await diagram.scrollIntoViewIfNeeded();
  await expect.poll(() => diagram.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  expect(downloads).toEqual([]);

  for (const [label, filename] of [
    ["Download BIBLIO checklist", /-biblio-.*\.md$/],
    ["Download PRISMA-S search appendix", /-prisma-s-.*\.txt$/],
  ] as const) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: label }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(filename);
  }

  await page.goto("/projects/new");
  await expect(page).toHaveURL(/\/$/);

  expect(writes).toEqual([]);
});
