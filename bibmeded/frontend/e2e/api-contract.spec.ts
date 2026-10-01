import { expect, test } from "@playwright/test";
import { diffShape, loadApiShapes, type ShapeNode } from "./api-contract";
import { analysisResults, analysisRunResponse } from "./mock-api";

const shapes = loadApiShapes();
const refreshHint =
  "Mocked analysis responses in e2e/mock-api.ts drifted from the backend shapes in " +
  "e2e/fixtures/api-shapes.json. Fix the mock (or refresh the fixture as described in CONTRIBUTING.md):";

test.describe("mock analysis responses match the backend contract", () => {
  test("every backend analysis type is mocked and nothing else is", () => {
    expect(Object.keys(analysisResults).sort()).toEqual(Object.keys(shapes).sort());
  });

  for (const [analysisType, shape] of Object.entries(shapes)) {
    test(`${analysisType} mock matches the backend shape`, () => {
      const drift = diffShape(shape, analysisRunResponse(analysisType), analysisType);
      expect(drift, `${refreshHint}\n${drift.join("\n")}`).toEqual([]);
    });
  }
});

test.describe("shape diff", () => {
  const journals: ShapeNode = {
    type: "object",
    properties: {
      top_journals: {
        type: "array",
        items: { type: "object", properties: { name: { type: "string" }, pub_count: { type: "number" } } },
      },
      field_maturity: { type: "object", nullable: true, properties: { phase: { type: "string" } } },
      burst_terms: { type: "array", items: null },
    },
  };

  test("names the drifted field, as in the #75 top_journals regression", () => {
    const drift = diffShape(
      journals,
      { top_journals: [{ name: "Medical Teacher", count: 3 }], field_maturity: null, burst_terms: [] },
      "journals",
    );

    expect(drift).toEqual([
      "journals.top_journals[0].pub_count: missing from mock (backend returns number)",
      "journals.top_journals[0].count: mock has a field the backend does not return",
    ]);
  });

  test("rejects null where the backend never returns it and wrong value types", () => {
    const drift = diffShape(
      journals,
      { top_journals: null, field_maturity: { phase: 1 }, burst_terms: [{ anything: true }] },
      "journals",
    );

    expect(drift).toEqual([
      "journals.top_journals: mock is null but backend returns array",
      "journals.field_maturity.phase: mock is number but backend returns string",
    ]);
  });
});
