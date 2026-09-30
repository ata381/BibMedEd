import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installMockApi } from "./mock-api";

const QUICK_START = "https://ata381.github.io/BibMedEd/deploy/#quick-start";

test("read-only demo shows the banner and hides project mutations", async ({ page }) => {
  await installMockApi(page, { readOnly: true });
  await page.goto("/");

  await expect(page.getByText("Read-only demo")).toBeVisible();
  await expect(page.getByRole("link", { name: /Quick Start/ })).toHaveAttribute("href", QUICK_START);
  await expect(page.getByRole("link", { name: "Open project AI in Medical Education — Sample Project" })).toBeVisible();
  await expect(page.getByRole("link", { name: "New project" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Delete project/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Explore sample project" })).toHaveCount(0);
});

test("read-only demo redirects the new-project form home", async ({ page }) => {
  await installMockApi(page, { readOnly: true });
  await page.goto("/projects/new");
  await expect(page).toHaveURL(/\/$/);
});

test("read-only demo disables screening controls", async ({ page }) => {
  const { writeRequests } = await installMockApi(page, { readOnly: true });
  await page.goto("/projects/1/results");

  await expect(page.getByRole("heading", { name: "Results Review" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Included: "Simulation-based feedback/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Exclude 0-citation papers" })).toHaveCount(0);
  expect(writeRequests).toEqual([]);
});

test("read-only demo keeps the search button disabled", async ({ page }) => {
  await installMockApi(page, { readOnly: true });
  await page.goto("/projects/1/search");
  await expect(page.getByRole("button", { name: "Execute Search" })).toBeDisabled();
});

test("read-only dashboard never falls back to running analyses", async ({ page }) => {
  const { writeRequests } = await installMockApi(page, { readOnly: true, missingAnalyses: ["keywords"] });
  await page.goto("/projects/1/dashboard");

  await expect(page.getByRole("heading", { name: "Analysis Overview" })).toBeVisible();
  expect(writeRequests).toEqual([]);
});

test("writable dashboard still runs a missing analysis", async ({ page }) => {
  const { writeRequests } = await installMockApi(page, { missingAnalyses: ["keywords"] });
  await page.goto("/projects/1/dashboard");

  await expect(page.getByRole("heading", { name: "Analysis Overview" })).toBeVisible();
  expect(writeRequests).toEqual(["POST /api/projects/1/analysis/keywords"]);
});

test("an unreachable config endpoint fails closed", async ({ page }) => {
  await installMockApi(page, { configUnavailable: true });
  await page.goto("/projects/1/search");

  await expect(page.getByText("Read-only demo")).toBeVisible();
  await expect(page.getByRole("button", { name: "Execute Search" })).toBeDisabled();
});

test("writable instances show no banner", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/search");

  await expect(page.getByRole("button", { name: "Execute Search" })).toBeEnabled();
  await expect(page.getByText("Read-only demo")).toHaveCount(0);
});

for (const theme of ["light", "dark"] as const) {
  test(`read-only banner has no WCAG A/AA violations in ${theme} mode`, async ({ page }) => {
    await installMockApi(page, { readOnly: true });
    await page.addInitScript((themeChoice) => localStorage.setItem("bibmeded:theme", themeChoice), theme);
    await page.goto("/projects/1/results");
    await expect(page.getByText("Read-only demo")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  });
}
