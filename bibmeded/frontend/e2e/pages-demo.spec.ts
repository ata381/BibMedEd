import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test.skip(!process.env.PLAYWRIGHT_PAGES_DEMO, "Requires the static Pages build and no backend.");

test("the Pages sample runs without a backend and downloads the reporting files", async ({ page, baseURL }) => {
  if (!baseURL) throw new Error("Set PLAYWRIGHT_BASE_URL to the static demo URL.");
  test.setTimeout(45_000);
  const unexpectedRequests: string[] = [];
  const origin = new URL(baseURL).origin;
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== origin || request.method() !== "GET") {
      unexpectedRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await page.goto("projects/1/search/");
  await expect(page.getByText("Read-only demo")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Raw query" })).toHaveValue(/medical education/i, { timeout: 12_000 });
  await expect(page.getByRole("button", { name: "Execute Search" })).toBeDisabled();

  await page.goto("projects/1/results/");
  await expect(page.getByRole("heading", { name: "PRISMA flow" })).toBeVisible();
  await expect(page.getByText("Wrong population", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "View analysis" }).click();
  await expect(page).toHaveURL(/\/demo\/projects\/1\/dashboard\/$/);
  await page.getByRole("tab", { name: "Authors" }).click();
  await expect(page.getByRole("heading", { name: "Top Authors" })).toBeVisible();

  await page.goto("projects/1/export/");
  const [bundle] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download bundle" }).click(),
  ]);
  expect(bundle.suggestedFilename()).toBe("sample-bundle.zip");

  await page.getByRole("tab", { name: "Reporting" }).click();
  const diagram = page.getByRole("img", { name: /PRISMA 2020 flow diagram/ });
  await diagram.scrollIntoViewIfNeeded();
  await expect.poll(() => diagram.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);

  for (const [label, filename, heading] of [
    ["Download BIBLIO checklist", "sample-biblio.md", "# BIBLIO reporting worksheet"],
    ["Download PRISMA-S search appendix", "sample-prisma-s.txt", "PRISMA-S search appendix"],
  ]) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: label }).click(),
    ]);
    expect(download.suggestedFilename()).toBe(filename);
    expect(await readFile(await download.path(), "utf8")).toContain(heading);
  }
  expect(unexpectedRequests).toEqual([]);
});
