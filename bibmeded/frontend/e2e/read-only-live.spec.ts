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

  const projectPath = new URL(page.url()).pathname.replace(/\/results$/, "");
  await page.goto(`${projectPath}/dashboard`);
  await page.waitForLoadState("networkidle");
  expect(pageErrors).toEqual([]);
  await expect(page.getByRole("heading", { name: "Analysis Overview" })).toBeVisible();
  await expect(page.getByText("Marcus Chen Sample").first()).toBeAttached();

  await page.goto("/projects/new");
  await expect(page).toHaveURL(/\/$/);

  expect(writes).toEqual([]);
});
