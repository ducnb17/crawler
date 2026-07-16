<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import { useAuthStore } from "@/stores/auth";
import { errorMsg } from "@/api/client";

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const email = ref("");
const password = ref("");
const submitting = ref(false);

async function submit(e: Event) {
  e.preventDefault();
  submitting.value = true;
  try {
    await auth.login(email.value, password.value);
    toast.success(t("toast.login_success"));
    const redirect = (route.query.redirect as string) || "/dashboard";
    router.replace(redirect);
  } catch (err) {
    toast.error(t("toast.login_failed"), { description: errorMsg(err) });
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="grid min-h-full md:grid-cols-2">
    <!-- Brand panel -->
    <div class="hidden md:flex flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-600 to-brand-900 p-12 text-white">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 backdrop-blur">
          <span class="text-lg font-black">C</span>
        </div>
        <div class="leading-none">
          <p class="text-xl font-bold">{{ t("app.title") }}</p>
          <p class="text-sm text-white/80">{{ t("app.subtitle") }}</p>
        </div>
      </div>
      <div>
        <h1 class="text-4xl font-extrabold leading-tight">
          {{ t("auth.login_desc") }}
        </h1>
        <p class="mt-4 text-white/80">JWT · RBAC · SSE realtime · Celery worker pool.</p>
      </div>
      <div class="text-xs text-white/60">© {{ new Date().getFullYear() }} Crawler System</div>
    </div>

    <!-- Form panel -->
    <div class="flex items-center justify-center p-6 md:p-10">
      <form @submit="submit" class="w-full max-w-md space-y-5">
        <div class="md:hidden mb-6 text-center">
          <h1 class="text-2xl font-bold">{{ t("auth.login") }}</h1>
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium" for="email">{{ t("auth.email") }}</label>
          <Input id="email" v-model="email" type="email" required placeholder="you@example.com" autocomplete="email" />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium" for="password">{{ t("auth.password") }}</label>
          <Input id="password" v-model="password" type="password" required placeholder="••••••••" autocomplete="current-password" />
        </div>
        <Button type="submit" :loading="submitting" class="w-full" size="lg">
          {{ t("auth.login") }}
        </Button>
        <RouterLink
          :to="{ name: 'signup' }"
          class="block text-center text-sm text-brand-700 hover:underline dark:text-brand-300"
        >
          {{ t("auth.to_signup") }}
        </RouterLink>
      </form>
    </div>
  </div>
</template>