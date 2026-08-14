import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["**/dist/**", "**/node_modules/**", "server/data/**"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["server/**/*.ts"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  {
    files: ["client/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser },
    },
  },
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
);
