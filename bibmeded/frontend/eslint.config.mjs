import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // d3 datum types are dynamic per selection; replacing `any` with full
    // generic chains hurts readability more than it helps. Allow it here.
    files: ["src/components/force-graph.tsx"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  {
    // React 19 Compiler diagnostics flag state-synchronization patterns that
    // are correct-as-written but worth a follow-up refactor. Downgraded to
    // warnings so they're visible without blocking CI. Tracked in #26.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
    },
  },
]);

export default eslintConfig;
