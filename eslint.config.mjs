// @ts-check
import eslint from "@eslint/js";
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
      // Generated from the FastAPI OpenAPI schema — never edited by hand (CLAUDE.md §25.3).
      "packages/typescript/api-client/src/generated/**",
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      // CLAUDE.md §8.3: `any` only as a temporary migration with a tracked TODO.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "no-console": ["error", { allow: ["warn", "error"] }],
    },
  },
);
