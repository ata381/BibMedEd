import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { installMockApi } from "./mock-api";

const routes = [
  { path: "/", heading: "Welcome to BibMedEd", title: /Bibliometric Analysis for Medical Education/ },
  { path: "/projects/new", heading: "New project", title: /New project/ },
  { path: "/projects/1/search", heading: "Precision Search Strategy", title: /Search strategy/ },
  { path: "/projects/1/results", heading: "Results Review", title: /Results review/ },
  { path: "/projects/1/dashboard", heading: "Analysis Overview", title: /Analysis dashboard/ },
  { path: "/projects/1/export", heading: "Export your dataset", title: /Export project/ },
];

for (const theme of ["light", "dark"] as const) {
  for (const route of routes) {
    test(`${route.path} has no WCAG A/AA violations or page overflow in ${theme} mode`, async ({ page }) => {
      await installMockApi(page);
      await page.addInitScript((themeChoice) => localStorage.setItem("bibmeded:theme", themeChoice), theme);
      await page.goto(route.path);
      await expect(page.locator("html")).toHaveClass(new RegExp(theme));
      await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
      await expect(page).toHaveTitle(route.title);

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(formatViolations(results.violations)).toEqual([]);

      const overflows = await findViewportOverflows(page);
      expect(overflows).toEqual([]);
    });
  }
}

test("all focusable controls meet the WCAG 2.2 minimum target size", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/search");

  const undersized = await page.locator("a, button, input, textarea, select, [tabindex]:not([tabindex='-1'])").evaluateAll((elements) =>
    elements
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const intentionallyClipped = element.classList.contains("sr-only");
        const hiddenByAncestor = rect.width === 0 && rect.height === 0;
        return !intentionallyClipped && !hiddenByAncestor && style.display !== "none" && style.visibility !== "hidden" && (rect.width < 24 || rect.height < 24);
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return `${element.tagName.toLowerCase()}#${element.id}.${element.className}: ${Math.round(rect.width)}x${Math.round(rect.height)}`;
      }),
  );

  expect(undersized).toEqual([]);
});

function formatViolations(violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]) {
  return violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    help: violation.help,
    targets: violation.nodes.map((node) => node.target.join(" ")),
  }));
}

async function findViewportOverflows(page: Page) {
  return page.locator("body *").evaluateAll((elements) => {
    const viewportWidth = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth <= viewportWidth + 1) return [];
    return elements
      .filter((element) => {
        const style = getComputedStyle(element);
        if (style.position === "fixed" || style.position === "sticky") return false;
        const rect = element.getBoundingClientRect();
        return rect.left < -1 || rect.right > viewportWidth + 1;
      })
      .slice(0, 20)
      .map((element) => `${element.tagName.toLowerCase()}.${element.className}`);
  });
}
