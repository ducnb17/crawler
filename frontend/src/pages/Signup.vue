<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import { useAuthStore } from "@/stores/auth";
import { errorMsg } from "@/api/client";

const { t } = useI18n();
const router = useRouter();
const auth = useAuthStore();
const email = ref("");
const password = ref("");
const full_name = ref("");
const submitting = ref(false);

async function submit(e: Event) {
  e.preventDefault();
  submitting.value = true;
  try {
    await auth.signup(email.value, password.value, full_name.value || undefined);
    toast.success(t("toast.signup_success"));
    router.replace("/dashboard");
  } catch (err) {
    toast.error(t("toast.signup_failed"), { description: errorMsg(err) });
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="flex min-h-full items-center justify-center bg-gradient-to-br from-brand-50 via-background to-brand-100/30 dark:from-brand-950/30 dark:via-background dark:to-brand-900/20 p-6">
    <form @submit="submit" class="w-full max-w-md space-y-5 rounded-xl border bg-card p-8 shadow-xl">
      <div class="text-center">
        <h1 class="text-2xl font-bold">{{ t("auth.signup") }}</h1>
        <p class="mt-1 text-sm text-muted-foreground">{{ t("auth.signup_desc") }}</p>
      </div>
      <div class="space-y-2">
        <label class="text-sm font-medium">{{ t("auth.full_name") }} (optional)</label>
        <Input v-model="full_name" type="text" autocomplete="name" />
      </div>
      <div class="space-y-2">
        <label class="text-sm font-medium">{{ t("auth.email") }}</label>
        <Input v-model="email" type="email" required autocomplete="email" />
      </div>
      <div class="space-y-2">
        <label class="text-sm font-medium">{{ t("auth.password") }}</label>
        <Input v-model="password" type="password" required minlength="8" autocomplete="new-password" />
      </div>
      <Button type="submit" :loading="submitting" class="w-full" size="lg">
        {{ t("auth.signup") }}
      </Button>
      <RouterLink :to="{ name: 'login' }" class="block text-center text-sm text-brand-700 hover:underline dark:text-brand-300">
        {{ t("auth.to_login") }}
      </RouterLink>
    </form>
  </div>
</template>