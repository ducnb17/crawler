import { createApp } from "vue";
import { createPinia } from "pinia";
import { VueQueryPlugin } from "@tanstack/vue-query";
import { QueryClient } from "@tanstack/vue-query";
import { createI18n } from "vue-i18n";

import App from "./App.vue";
import { router } from "./router";
import { messages } from "./i18n";

import "./assets/main.css";

const app = createApp(App);

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem("crawler.lang") ?? "vi",
  fallbackLocale: "en",
  messages,
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

app.use(createPinia());
app.use(router);
app.use(i18n);
app.use(VueQueryPlugin, { queryClient });

app.mount("#app");