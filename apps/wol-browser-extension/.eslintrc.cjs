/* eslint-env node */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    project: "./tsconfig.json",
  },
  plugins: ["@typescript-eslint"],
  env: { browser: true, node: false, webextensions: true, es2022: true },
  rules: {
    "@typescript-eslint/no-explicit-any": "warn",
    // Defense-in-depth: forbid direct fetch() calls AND any non-localhost URL
    // literal anywhere outside the api / verse_detector / i18n / tests files.
    "no-restricted-syntax": [
      "error",
      {
        selector: "CallExpression[callee.name='fetch']",
        message:
          "Direct fetch() is forbidden. Use JwApiClient from src/api.ts.",
      },
      {
        selector: "Literal[value=/^https?:\\/\\/(?!localhost:8765).*/]",
        message:
          "External URL literal forbidden. Only http://localhost:8765 is allowed.",
      },
    ],
  },
  overrides: [
    {
      // The api module is the SOLE place fetch is allowed.
      files: ["src/api.ts"],
      rules: { "no-restricted-syntax": "off" },
    },
    {
      // verse_detector contains a literal `wol.jw.org` hostname check;
      // i18n loads the messages tables (no URLs but flagged otherwise).
      // Tests + fixtures naturally carry sample wol.jw.org URLs.
      files: [
        "tests/**",
        "src/dom/verse_detector.ts",
        "src/i18n/**",
      ],
      rules: { "no-restricted-syntax": "off" },
    },
  ],
};
