import { expect, test, type Page } from "@playwright/test";
import { installMockApi } from "./mock-api";

function collectRuntimeErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("_next/hmr")) {
      errors.push(message.text());
    }
  });
  return errors;
}

test("sample project opens a complete dashboard", async ({ page }) => {
  await installMockApi(page, { emptyWorkspace: true });
  const errors = collectRuntimeErrors(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Explore sample project" }).click();

  await expect(page).toHaveURL(/\/projects\/1\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Analysis Overview" })).toBeVisible();
  await expect(page.getByText("AI in Medical Education — Sample Project")).toBeVisible();
  await expect(page.getByText("Marcus Chen Sample — 5")).toBeAttached();
  expect(errors).toEqual([]);
});

test("new project gives an inline date correction and continues to search", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/new");

  const projectName = page.getByLabel("Project name");
  const continueButton = page.getByRole("button", { name: "Continue to search" });
  await expect(async () => {
    await projectName.fill("Accessible review project");
    await expect(continueButton).toBeEnabled();
  }).toPass();
  await page.getByLabel("Date range start").fill("2025-01-01");
  await page.getByLabel("Date range end").fill("2024-01-01");
  await continueButton.click();

  await expect(page.locator("#date-range-error")).toContainText("Start date must be before end date");
  await expect(page.getByLabel("Date range start")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Date range end")).toHaveAttribute("aria-invalid", "true");

  await page.getByLabel("Date range end").fill("2025-12-31");
  await continueButton.click();
  await expect(page).toHaveURL(/\/projects\/1\/search$/);
  await expect(page.getByRole("heading", { name: "Precision Search Strategy" })).toBeVisible();
});

test("search builder exposes labels and selected options", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/search");

  await expect(page.getByRole("textbox", { name: "Topic A" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Topic B" })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "Start year" })).toHaveValue("2022");
  await expect(page.getByRole("spinbutton", { name: "End year" })).toHaveValue("2025");
  await expect(page.getByRole("radio", { name: "PubMed" })).toBeChecked();
  await expect(page.getByRole("radio", { name: "AND" })).toBeChecked();

  const andOption = page.getByRole("radio", { name: "AND", exact: true });
  const orOption = page.getByRole("radio", { name: "OR", exact: true });
  await andOption.focus();
  await page.keyboard.press("ArrowRight");
  await expect(orOption).toBeFocused();
  await expect(orOption).toBeChecked();

  const pubmedOption = page.getByRole("radio", { name: "PubMed" });
  const openAlexOption = page.getByRole("radio", { name: "OpenAlex" });
  await pubmedOption.focus();
  await page.keyboard.press("ArrowRight");
  await expect(openAlexOption).toBeFocused();
  await expect(openAlexOption).toBeChecked();

  await page.getByRole("button", { name: "Advanced Query (Raw)" }).click();
  await expect(page.getByRole("textbox", { name: "Raw query" })).toBeVisible();
});

test("results can be screened with the keyboard", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/results");

  const exclude = page.getByRole("button", { name: /Exclude "Simulation-based feedback/ });
  await exclude.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitem", { name: "Wrong study design" })).toBeFocused();
  await page.keyboard.press("ArrowDown");
  const reason = page.getByRole("menuitem", { name: "Wrong population" });
  await expect(reason).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Re-include "Simulation-based feedback/ })).toBeVisible();
});

test("dashboard tabs change the visible analysis section", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/dashboard");

  await page.getByRole("tab", { name: "Authors" }).click();
  await expect(page.getByRole("heading", { name: "Top Authors" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Publication Trends" })).toBeHidden();

  await page.getByRole("tab", { name: "Citations" }).click();
  await expect(page.getByRole("heading", { name: "Most Cited Publications" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Network Preview" })).toBeHidden();
});

test("export tabs have valid relationships and keyboard activation", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/export");

  const dataTab = page.getByRole("tab", { name: "Data export" });
  const methodologyTab = page.getByRole("tab", { name: "Methodology & PRISMA" });
  await dataTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(methodologyTab).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(methodologyTab).toHaveAttribute("aria-selected", "true");
  const labelledBy = await page.getByRole("tabpanel").getAttribute("aria-labelledby");
  expect(labelledBy).toBeTruthy();
  await expect(page.locator(`#${labelledBy}`)).toBeVisible();
  await expect(page.getByText("BibMedEd methodology log")).toBeVisible();
});

test("mobile navigation is hidden when closed and restores focus on Escape", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium");
  await installMockApi(page);
  await page.goto("/");

  const trigger = page.getByRole("button", { name: "Open navigation" });
  const sidebar = page.getByRole("complementary", { name: "Primary navigation" });
  await expect(sidebar).toBeHidden();
  await trigger.click();
  await expect(sidebar).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sidebar).toBeHidden();
  await expect(trigger).toBeFocused();
});
