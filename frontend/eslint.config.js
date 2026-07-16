/** @type {import('eslint').Linter.Config[]} */
import js from "@eslint/js";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import vuePlugin from "eslint-plugin-vue";
import vueParser from "vue-eslint-parser";

export default [
  js.configs.recommended,
  {
    files: ["**/*.{ts,vue,tsx,jsx}"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: 2022,
        sourceType: "module",
        extraFileExtensions: [".vue"],
      },
      globals: {
        // browser globals
        window: "readonly",
        document: "readonly",
        localStorage: "readonly",
        crypto: "readonly",
        console: "readonly",
        location: "readonly",
        navigator: "readonly",
        EventSource: "readonly",
        Event: "readonly",
        HTMLElement: "readonly",
        HTMLInputElement: "readonly",
        HTMLSelectElement: "readonly",
        HTMLTextAreaElement: "readonly",
        HTMLDivElement: "readonly",
        MessageEvent: "readonly",
        FormData: "readonly",
        requestAnimationFrame: "readonly",
        clearTimeout: "readonly",
        setTimeout: "readonly",
        confirm: "readonly",
        alert: "readonly",
        prompt: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        Intl: "readonly",
        Node: "readonly",
        Element: "readonly",
        EventTarget: "readonly",
      },
    },
    plugins: {
      vue: vuePlugin,
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      ...vuePlugin.configs["flat/recommended"].rules,
      ...tsPlugin.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "vue/no-mutating-props": "off",
      "vue/multi-word-component-names": "off",
      "vue/html-self-closing": ["warn", { html: { void: "always", normal: "always", component: "always" } }],
    },
  },
  {
    // Config files (node environment, ESM)
    files: ["*.config.js", "*.config.ts", "postcss.config.js", "vite.config.ts", "tailwind.config.ts"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        process: "readonly",
        console: "readonly",
        module: "readonly",
        require: "readonly",
        __dirname: "readonly",
        Buffer: "readonly",
      },
    },
  },
  {
    ignores: ["dist/**", "node_modules/**", "*.d.ts"],
  },
];
