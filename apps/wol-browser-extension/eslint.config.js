// Flat config for ESLint v9+.
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import globals from "globals";

const fetchAndUrlGuards = [
  "error",
  {
    selector: "CallExpression[callee.name='fetch']",
    message: "Direct fetch() is forbidden. Use JwApiClient from src/api.ts.",
  },
  {
    selector: "Literal[value=/^https?:\\/\\/(?!localhost:8765).*/]",
    message:
      "External URL literal forbidden. Only http://localhost:8765 is allowed.",
  },
];

export default [
  {
    ignores: ["dist/**", "dist-zip/**", "node_modules/**", "test-results/**"],
  },
  {
    files: ["src/**/*.ts"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
        project: "./tsconfig.json",
      },
      globals: {
        ...globals.browser,
        ...globals.webextensions,
      },
    },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "no-restricted-syntax": fetchAndUrlGuards,
    },
  },
  {
    // src/api.ts is the SOLE module allowed to call fetch.
    files: ["src/api.ts"],
    rules: { "no-restricted-syntax": "off" },
  },
  {
    // verse_detector + content_script + background all need literal
    // ``https://wol.jw.org/`` host checks (startsWith / regex / hostname
    // gates). None of them issues a fetch; URL literals here are pattern
    // matchers, not network targets.
    files: [
      "src/dom/verse_detector.ts",
      "src/content_script.ts",
      "src/background.ts",
    ],
    rules: { "no-restricted-syntax": "off" },
  },
];
