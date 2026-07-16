<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { computed } from "vue";
import {
  LayoutDashboard,
  Briefcase,
  Search,
  Cloud,
  Webhook,
  Users as UsersIcon,
  Settings,
  Moon,
  Sun,
  LogOut,
  Globe,
} from "lucide-vue-next";

import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import { cn } from "@/lib/utils";
import { toast } from "vue-sonner";

const { t, locale, availableLocales } = useI18n();
const router = useRouter();
const auth = useAuthStore();
const theme = useThemeStore();

const navItems = computed(() => [
  { name: "dashboard", to: { name: "dashboard" }, label: t("nav.dashboard"), icon: LayoutDashboard, show: true },
  { name: "jobs", to: { name: "jobs" }, label: t("nav.jobs"), icon: Briefcase, show: true },
  { name: "results", to: { name: "results" }, label: t("nav.results"), icon: Search, show: true },
  { name: "proxies", to: { name: "proxies" }, label: t("nav.proxies"), icon: Cloud, show: auth.hasScope("proxies:read") },
  { name: "webhooks", to: { name: "webhooks" }, label: t("nav.webhooks"), icon: Webhook, show: auth.hasScope("webhooks:read") },
  { name: "users", to: { name: "users" }, label: t("nav.users"), icon: UsersIcon, show: auth.hasScope("users:read") },
  { name: "settings", to: { name: "settings" }, label: t("nav.settings"), icon: Settings, show: true },
]);

async function logout() {
  await auth.logout();
  toast.success(t("auth.logout_success"));
  router.replace({ name: "login" });
}

function toggleLocale() {
  const next = locale.value === "vi" ? "en" : "vi";
  locale.value = next;
  localStorage.setItem("crawler.lang", next);
}
</script>

<template>
  <div class="flex h-full w-full">
    <!-- Sidebar -->
    <aside class="hidden md:flex w-60 shrink-0 flex-col border-r bg-card">
      <div class="flex h-16 items-center gap-2 border-b px-5">
        <div class="flex h-8 w-8 items-center justify-center rounded-md bg-brand-600 text-white">
          <span class="text-base font-black">C</span>
        </div>
        <div class="flex flex-col leading-none">
          <span class="text-sm font-bold">{{ t("app.title") }}</span>
          <span class="text-xs text-muted-foreground">{{ t("app.subtitle") }}</span>
        </div>
      </div>
      <nav class="flex-1 space-y-1 overflow-y-auto py-4 px-3">
        <RouterLink
          v-for="item in navItems"
          v-show="item.show"
          :key="item.name"
          :to="item.to"
          class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          active-class="bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-200"
          exact-active-class="bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-200"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="border-t p-3">
        <button
          class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          @click="logout"
        >
          <LogOut class="h-4 w-4" />
          {{ t("nav.logout") }}
        </button>
      </div>
    </aside>

    <!-- Main -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Topbar -->
      <header class="flex h-16 items-center justify-between gap-4 border-b bg-card px-6">
        <div class="flex items-center gap-4">
          <!-- Mobile logo -->
          <div class="md:hidden flex h-8 w-8 items-center justify-center rounded-md bg-brand-600 text-white font-black">C</div>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            :title="availableLocales.join(' / ')"
            @click="toggleLocale"
          >
            <Globe class="h-4 w-4" />
            <span class="sr-only">{{ locale }}</span>
          </button>
          <button
            class="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            @click="theme.toggle()"
          >
            <Moon v-if="theme.mode === 'light'" class="h-4 w-4" />
            <Sun v-else class="h-4 w-4" />
          </button>
          <div class="flex items-center gap-2 pl-2">
            <div class="hidden md:flex h-9 w-9 select-none items-center justify-center rounded-full bg-brand-100 text-brand-700 text-sm font-semibold uppercase">
              {{ auth.user?.email?.slice(0, 2).toUpperCase() ?? "?" }}
            </div>
            <div class="hidden md:flex flex-col leading-tight">
              <span class="text-sm font-medium">{{ auth.user?.email ?? "" }}</span>
              <span v-if="auth.isSuperuser" class="text-[10px] uppercase text-brand-600">superuser</span>
            </div>
          </div>
        </div>
      </header>

      <!-- Body -->
      <main class="flex-1 overflow-y-auto bg-background">
        <div :class="cn('mx-auto p-6')">
          <RouterView v-slot="{ Component }">
            <Transition name="fade" mode="out-in">
              <component :is="Component" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>
  </div>
</template>