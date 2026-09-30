import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { installMockApi } from "./mock-api";

// Opt-in visual capture for README / docs assets. Skipped unless
// BIBMEDED_SCREENSHOT_DIR points at an output directory, so the normal
// e2e run stays fast and byte-for-byte deterministic.
const outputDir = process.env.BIBMEDED_SCREENSHOT_DIR;

const routes = [
  { path: "/", slug: "workspace", heading: /bibliometrics/i },
  { path: "/", slug: "workspace-empty", heading: /bibliometrics/i, emptyWorkspace: true },
  { path: "/projects/new", slug: "new-project", heading: /New project/ },
  { path: "/projects/1/search", slug: "search", heading: /search/i },
  { path: "/projects/1/results", slug: "results", heading: /Results/ },
  { path: "/projects/1/dashboard", slug: "dashboard", heading: /Analysis/ },
  { path: "/projects/1/export", slug: "export", heading: /Export/ },
];

test.describe("screenshots", () => {
  test.skip(!outputDir, "Set BIBMEDED_SCREENSHOT_DIR to capture screenshots");

  for (const theme of ["light", "dark"] as const) {
    for (const route of routes) {
      test(`${route.slug} (${theme})`, async ({ page }, testInfo) => {
        await installMockApi(page, { emptyWorkspace: route.emptyWorkspace });
        await page.addInitScript((choice) => localStorage.setItem("bibmeded:theme", choice), theme);
        await page.goto(route.path);
        await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(800);

        const dir = join(outputDir as string, testInfo.project.name);
        mkdirSync(dir, { recursive: true });
        await page.screenshot({ path: join(dir, `${route.slug}-${theme}.png`), fullPage: true });
      });
    }
  }
});
