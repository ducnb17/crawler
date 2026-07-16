<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import Card from "@/components/ui/Card.vue";
import Switch from "@/components/ui/Switch.vue";
import Button from "@/components/ui/Button.vue";

const { t, locale } = useI18n();
const auth = useAuthStore();
const theme = useThemeStore();

function toggleLang() {
  const next = locale.value === "vi" ? "en" : "vi";
  locale.value = next;
  localStorage.setItem("crawler.lang", next);
}
</script>

<template>
  <div class="max-w-2xl space-y-4">
    <div>
      <h1 class="text-2xl font-bold">{{ t("nav.settings") }}</h1>
      <p class="text-sm text-muted-foreground">Profile & preferences</p>
    </div>

    <Card title="Profile">
      <div class="space-y-2 text-sm">
        <div class="flex justify-between"><span class="text-muted-foreground">Email</span><span>{{ auth.user?.email }}</span></div>
        <div class="flex justify-between"><span class="text-muted-foreground">Full name</span><span>{{ auth.user?.full_name || "—" }}</span></div>
        <div class="flex justify-between"><span class="text-muted-foreground">User ID</span><span class="font-mono text-xs">{{ auth.user?.id }}</span></div>
        <div class="flex justify-between"><span class="text-muted-foreground">Superuser</span><span>{{ auth.isSuperuser ? "✓" : "—" }}</span></div>
      </div>
    </Card>

    <Card title="Preferences">
      <div class="flex items-center justify-between rounded-md border p-3">
        <div>
          <p class="text-sm font-medium">Dark mode</p>
          <p class="text-xs text-muted-foreground">Bật/tắt theme tối</p>
        </div>
        <Switch :model-value="theme.mode === 'dark'" @update:model-value="theme.toggle()" />
      </div>
      <div class="mt-2 flex items-center justify-between rounded-md border p-3">
        <div>
          <p class="text-sm font-medium">Language</p>
          <p class="text-xs text-muted-foreground">vi / en</p>
        </div>
        <Button variant="outline" size="sm" @click="toggleLang">{{ locale === "vi" ? "Tiếng Anh" : "Vietnamese" }}</Button>
      </div>
    </Card>

    <Card title="Scopes">
      <div class="flex flex-wrap gap-1 text-xs">
        <span v-for="s in auth.scopes" :key="s" class="rounded bg-muted px-1.5 py-0.5 font-mono">{{ s }}</span>
      </div>
    </Card>
  </div>
</template>