import { expect, test, type Page } from "@playwright/test";
import { analysisResults, installMockApi, sampleQueryString } from "./mock-api";

type GrowthSummaryOverride = {
  cagr: number | null;
  doubling_time_years: number | null;
  start_year: number | null;
  end_year: number | null;
  excluded_current_year: boolean;
  reason: string | null;
};

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

async function overridePublicationGrowthSummary(page: Page, growthSummary: GrowthSummaryOverride) {
  await page.route("**/api/projects/1/analysis/publications", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        project_id: 1,
        analysis_type: "publications",
        results: {
          ...analysisResults.publications,
          growth_summary: growthSummary,
        },
        created_at: "2026-08-23T12:00:00Z",
      }),
    }),
  );
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
  await expect(page.getByText("CAGR")).toBeVisible();
  await expect(page.getByText("41.42%")).toBeVisible();
  await expect(page.getByText("Doubling time")).toBeVisible();
  await expect(page.getByText("2 years")).toBeVisible();
  await expect(page.getByText("Growth window 2018–2020")).toBeVisible();
  expect(errors).toEqual([]);
});

test("publication trends notes when current incomplete year is excluded", async ({ page }) => {
  await installMockApi(page);
  await overridePublicationGrowthSummary(page, {
    cagr: 50,
    doubling_time_years: 1.71,
    start_year: 2023,
    end_year: 2025,
    excluded_current_year: true,
    reason: null,
  });

  await page.goto("/projects/1/dashboard");

  await expect(page.getByText("Current incomplete year excluded from growth calculations.")).toBeVisible();
});

test("publication trends shows null metric reasons without hiding zero values", async ({ page }) => {
  await installMockApi(page);
  await overridePublicationGrowthSummary(page, {
    cagr: 0,
    doubling_time_years: null,
    start_year: 2018,
    end_year: 2020,
    excluded_current_year: false,
    reason: "Doubling time is not defined for non-positive growth (CAGR <= 0).",
  });

  await page.goto("/projects/1/dashboard");

  await expect(page.getByText("0%")).toBeVisible();
  await expect(page.getByText("Doubling time is not defined for non-positive growth (CAGR <= 0).")).toBeVisible();
  await expect(page.getByText("NaN")).toHaveCount(0);
});

test("publication trends shows CAGR null reasons without hiding zero doubling time", async ({ page }) => {
  await installMockApi(page);
  await overridePublicationGrowthSummary(page, {
    cagr: null,
    doubling_time_years: 0,
    start_year: 2018,
    end_year: 2020,
    excluded_current_year: false,
    reason: "CAGR is undefined because the first full calendar year has zero publications.",
  });

  await page.goto("/projects/1/dashboard");

  await expect(page.getByText("0 years")).toBeVisible();
  await expect(page.getByText("CAGR is undefined because the first full calendar year has zero publications.")).toBeVisible();
  await expect(page.getByText("NaN")).toHaveCount(0);
});

test("publication trends shows a shared reason once when both growth metrics are null", async ({ page }) => {
  await installMockApi(page);
  await overridePublicationGrowthSummary(page, {
    cagr: null,
    doubling_time_years: null,
    start_year: 2029,
    end_year: 2029,
    excluded_current_year: false,
    reason: "At least two full calendar years of data are required to compute CAGR.",
  });

  await page.goto("/projects/1/dashboard");

  await expect(page.getByText("At least two full calendar years of data are required to compute CAGR.")).toHaveCount(1);
  await expect(page.getByText("NaN")).toHaveCount(0);
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
  await expect(page.getByRole("heading", { name: "Search strategy" })).toBeVisible();
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

test("sample project search page shows its stored strategy", async ({ page }) => {
  const { writeRequests } = await installMockApi(page, { sampleSearch: true });
  await page.goto("/projects/1/search");

  await expect(page.getByRole("textbox", { name: "Raw query" })).toHaveValue(sampleQueryString);
  await expect(page.getByRole("button", { name: "Advanced Query (Raw)" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Loaded from the bundled sample project's search strategy")).toBeVisible();

  await page.getByRole("button", { name: "Query Builder" }).click();
  await page.getByRole("button", { name: "Discard edits" }).click();
  await expect(page.getByRole("spinbutton", { name: "Start year" })).toHaveValue("2018");
  await expect(page.getByRole("spinbutton", { name: "End year" })).toHaveValue("2025");
  await expect(page.getByRole("radio", { name: "PubMed" })).toBeChecked();
  expect(writeRequests).toEqual([]);
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

test("results exclusion records the PRISMA screening stage with the keyboard", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/results");

  await page.getByRole("button", { name: /Exclude "Simulation-based feedback/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu", { name: /title \/ abstract stage/i })).toBeVisible();
  const titleAbstract = page.getByRole("menuitemradio", { name: "Title / abstract" });
  const fullText = page.getByRole("menuitemradio", { name: "Full text" });
  const firstReason = page.getByRole("menuitem", { name: "Wrong study design" });
  await expect(titleAbstract).toHaveAttribute("aria-checked", "true");
  await expect(fullText).toHaveAttribute("aria-checked", "false");
  await expect(firstReason).toBeFocused();

  await page.keyboard.press("ArrowUp");
  await expect(fullText).toBeFocused();
  await page.keyboard.press("Space");
  await expect(fullText).toHaveAttribute("aria-checked", "true");
  await expect(titleAbstract).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("menu", { name: /full text stage/i })).toBeVisible();

  await page.keyboard.press("ArrowDown");
  await expect(firstReason).toBeFocused();
  const patch = page.waitForRequest((r) => r.method() === "PATCH" && r.url().endsWith("/publications/1/exclude"));
  await page.keyboard.press("Enter");
  expect((await patch).postDataJSON()).toEqual({ reason: "wrong_study_design", screening_stage: "full_text" });
  await expect(page.getByRole("button", { name: /Re-include "Simulation-based feedback/ })).toBeVisible();
  await expect(page.getByText("Full text stage")).toBeVisible();

  // The chosen stage carries over to the next record's picker.
  await page.getByRole("button", { name: /Exclude "Learning analytics/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitemradio", { name: "Full text" })).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toBeHidden();
});

test("full-text-unavailable exclusions are always recorded at the full-text stage", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/projects/1/results");

  await page.getByRole("button", { name: /Exclude "Simulation-based feedback/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitemradio", { name: "Title / abstract" })).toHaveAttribute("aria-checked", "true");
  const unavailable = page.getByRole("menuitem", { name: /Full-text not retrievable.*Always recorded at the full-text stage/ });
  await expect(unavailable).toBeVisible();

  const patch = page.waitForRequest((r) => r.method() === "PATCH" && r.url().endsWith("/publications/1/exclude"));
  await unavailable.click();
  expect((await patch).postDataJSON()).toEqual({ reason: "fulltext_unavailable", screening_stage: "full_text" });
  await expect(page.getByText("Full text stage")).toBeVisible();
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
