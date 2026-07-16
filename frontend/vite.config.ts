import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBase = env.VITE_API_BASE_URL || "http://localhost:8001";
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      host: "0.0.0.0",
      proxy: {
        "/api": {
          target: apiBase,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
        // Keep SSE proxy-friendly
        "/sse": {
          target: apiBase,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/sse/, ""),
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
      target: "es2022",
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        output: {
          manualChunks: {
            "vue-vendor": ["vue", "vue-router", "pinia"],
            "ui-vendor": ["radix-vue", "lucide-vue-next", "vue-sonner"],
            "charts-vendor": ["echarts", "vue-echarts"],
            "table-vendor": ["@tanstack/vue-table", "@tanstack/vue-query"],
          },
        },
      },
    },
    optimizeDeps: {
      include: ["vue", "vue-router", "pinia", "axios", "@vueuse/core"],
    },
  };
});