import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { installMockApi } from "./mock-api";

const PROJECT_NAME = "AI in Medical Education — Sample Project";

async function openDeleteDialog(page: Page) {
  await page.goto("/");
  const trigger = page.getByRole("button", { name: `Delete project ${PROJECT_NAME}` });
  await trigger.click();
  const dialog = page.getByRole("alertdialog", { name: "Delete this project?" });
  await expect(dialog).toBeVisible();
  return { trigger, dialog };
}

async function openBulkExcludeDialog(page: Page) {
  await page.goto("/projects/1/results");
  await expect(page.getByRole("heading", { name: "Results Review" })).toBeVisible();
  const trigger = page.getByRole("button", { name: "Exclude 0-citation papers" });
  await trigger.click();
  const dialog = page.getByRole("alertdialog", { name: "Exclude uncited publications?" });
  await expect(dialog).toBeVisible();
  return { trigger, dialog };
}

async function openDiscardRawQueryDialog(page: Page) {
  await page.goto("/projects/1/search");
  await page.getByRole("button", { name: "Advanced Query (Raw)" }).click();
  await page.getByRole("textbox", { name: "Raw query" }).fill("custom[tiab] AND edits[tiab]");
  const trigger = page.getByRole("button", { name: "Query Builder" });
  await trigger.click();
  const dialog = page.getByRole("alertdialog", { name: "Discard raw query edits?" });
  await expect(dialog).toBeVisible();
  return { trigger, dialog };
}

async function expectDescribed(dialog: Locator) {
  const describedBy = await dialog.getAttribute("aria-describedby");
  expect(describedBy).toBeTruthy();
  await expect(dialog.page().locator(`[id="${describedBy}"]`)).toBeVisible();
}

test.describe("delete project confirmation", () => {
  test("Escape cancels, keeps the project and returns focus to the trigger", async ({ page }) => {
    const { writeRequests } = await installMockApi(page);
    const { trigger, dialog } = await openDeleteDialog(page);

    await expect(dialog).toContainText(PROJECT_NAME);
    await expectDescribed(dialog);
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    expect(writeRequests).toEqual([]);
  });

  test("focus is trapped inside the dialog", async ({ page }) => {
    await installMockApi(page);
    const { dialog } = await openDeleteDialog(page);
    const cancel = dialog.getByRole("button", { name: "Cancel" });
    const confirm = dialog.getByRole("button", { name: "Delete project" });

    await page.keyboard.press("Tab");
    await expect(confirm).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(cancel).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(confirm).toBeFocused();
  });

  test("the destructive action uses the danger token", async ({ page }) => {
    await installMockApi(page);
    const { dialog } = await openDeleteDialog(page);
    const confirm = dialog.getByRole("button", { name: "Delete project" });
    const expected = await page.evaluate(() => {
      const probe = document.createElement("span");
      probe.style.color = "var(--color-danger)";
      document.body.append(probe);
      const color = getComputedStyle(probe).color;
      probe.remove();
      return color;
    });
    await expect(confirm).toHaveCSS("background-color", expected);
  });

  test("Cancel button closes without deleting", async ({ page }) => {
    const { writeRequests } = await installMockApi(page);
    const { trigger, dialog } = await openDeleteDialog(page);

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    expect(writeRequests).toEqual([]);
  });

  test("confirming deletes the project", async ({ page }) => {
    const { writeRequests } = await installMockApi(page);
    const { dialog } = await openDeleteDialog(page);

    await dialog.getByRole("button", { name: "Delete project" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("link", { name: `Open project ${PROJECT_NAME}` })).toHaveCount(0);
    expect(writeRequests).toEqual(["DELETE /api/projects/1"]);
  });

  test("a failed delete keeps the dialog open and re-enables its buttons", async ({ page }) => {
    await installMockApi(page);
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    await page.route("**/api/projects/1", async (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      await gate;
      return route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' });
    });
    const { dialog } = await openDeleteDialog(page);
    const confirm = dialog.getByRole("button", { name: "Delete project" });
    const cancel = dialog.getByRole("button", { name: "Cancel" });

    await confirm.click();
    await expect(confirm).toBeDisabled();
    await expect(cancel).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeVisible();

    release();
    await expect(page.getByText("Failed to delete project")).toBeVisible();
    await expect(dialog).toBeVisible();
    await expect(confirm).toBeEnabled();
    await expect(cancel).toBeEnabled();
  });
});

test.describe("bulk-exclude confirmation", () => {
  test("states how many publications will be excluded and cancels without writing", async ({ page }) => {
    const { writeRequests } = await installMockApi(page);
    const { trigger, dialog } = await openBulkExcludeDialog(page);

    await expect(dialog).toContainText("1 publication will be excluded");
    await expectDescribed(dialog);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    expect(writeRequests).toEqual([]);
  });

  test("counts across the whole project when it spans several pages", async ({ page }) => {
    await installMockApi(page);
    const records = Array.from({ length: 25 }, (_, i) => ({
      id: 100 + i,
      pmid: `bulk-${i}`,
      doi: null,
      title: `Paged record ${i}`,
      abstract: null,
      year: 2024,
      publication_type: "Article",
      citation_count: i < 4 ? 0 : i,
      excluded: i === 0,
      exclusion_reason: i === 0 ? "other" : null,
      journal_name: null,
      authors: [],
    }));
    const limits: string[] = [];
    await page.route("**/api/projects/1/publications?*", (route) => {
      const url = new URL(route.request().url());
      const limit = Number(url.searchParams.get("limit"));
      limits.push(String(limit));
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ total: records.length, excluded_count: 1, items: records.slice(0, limit) }),
      });
    });
    const { dialog } = await openBulkExcludeDialog(page);

    await expect(dialog).toContainText("3 publications will be excluded");
    await expect(dialog.getByRole("button", { name: "Exclude 3 publications" })).toBeVisible();
    expect(limits).toContain("500");
  });

  test("confirming excludes the uncited publications", async ({ page }) => {
    const { writeRequests } = await installMockApi(page);
    const { dialog } = await openBulkExcludeDialog(page);

    await expect(dialog).toContainText("1 publication will be excluded");
    await dialog.getByRole("button", { name: "Exclude 1 publication" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText("1 publication excluded.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Re-include "A pilot curriculum/ })).toBeVisible();
    expect(writeRequests).toEqual(["POST /api/projects/1/publications/bulk-exclude"]);
  });
});

test.describe("discard raw query confirmation", () => {
  test("cancelling keeps the raw query edits", async ({ page }) => {
    await installMockApi(page);
    const { trigger, dialog } = await openDiscardRawQueryDialog(page);

    await expectDescribed(dialog);
    await dialog.getByRole("button", { name: "Keep editing" }).click();
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    await expect(page.getByRole("textbox", { name: "Raw query" })).toHaveValue("custom[tiab] AND edits[tiab]");
  });

  test("confirming switches back to the Query Builder", async ({ page }) => {
    await installMockApi(page);
    const { dialog } = await openDiscardRawQueryDialog(page);

    await dialog.getByRole("button", { name: "Discard edits" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("textbox", { name: "Topic A" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Raw query" })).toHaveCount(0);
  });
});

const dialogs = [
  { name: "delete project", open: openDeleteDialog },
  { name: "bulk exclude", open: openBulkExcludeDialog },
  { name: "discard raw query", open: openDiscardRawQueryDialog },
];

for (const theme of ["light", "dark"] as const) {
  for (const { name, open } of dialogs) {
    test(`${name} dialog has no WCAG A/AA violations in ${theme} mode`, async ({ page }) => {
      await installMockApi(page);
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.addInitScript((themeChoice) => localStorage.setItem("bibmeded:theme", themeChoice), theme);
      const { dialog } = await open(page);
      await expect(page.locator("html")).toHaveClass(new RegExp(theme));
      await expect(dialog.getByRole("button").last()).toBeEnabled();

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    });
  }
}
