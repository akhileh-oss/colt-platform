// @ts-check
import eslint from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/.venv/**",
      "**/__pycache__/**",
      "**/.pytest_cache/**",
      "**/.ruff_cache/**",
      "**/.mypy_cache/**",
      "**/dist/**",
      "**/.next/**",
      "**/coverage/**",
      "**/test-results/**",
      "**/playwright-report/**",
      // Generated from the FastAPI OpenAPI schema — never edited by hand (CLAUDE.md §25.3).
      "packages/typescript/api-client/src/generated/**",
      "packages/typescript/api-client/openapi.json",
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      // CLAUDE.md §8.3: `any` only as a temporary migration with a tracked TODO.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "no-console": ["error", { allow: ["warn", "error"] }],
    },
  },
  // apps/web: React, Next.js, and accessibility rules (CLAUDE.md §43, §78).
  {
    files: ["apps/web/**/*.{ts,tsx}"],
    plugins: {
      "@next/next": nextPlugin,
      "jsx-a11y": jsxA11y,
      "react-hooks": reactHooks,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
    },
    languageOptions: {
      ...jsxA11y.flatConfigs.recommended.languageOptions,
    },
    settings: {
      next: { rootDir: "apps/web" },
    },
  },
  // Playwright specs and generated Next.js build metadata are not part of the app's own
  // module graph, so Next's "must import from next/link, not <a>" style rules don't apply.
  {
    files: ["tests/e2e/**/*.ts"],
    rules: {
      "@next/next/no-html-link-for-pages": "off",
    },
  },
);
