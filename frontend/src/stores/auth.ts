import { defineStore } from "pinia";
import { computed, ref } from "vue";
import {
  authApi,
  clearTokens,
  getAccessToken,
  setTokens,
} from "@/api/client";
import type { UserRead } from "@/types";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<UserRead | null>(null);
  const loading = ref(false);
  const initialized = ref(false);

  const isLoggedIn = computed(() => !!user.value);
  const isSuperuser = computed(() => !!user.value?.is_superuser);
  const scopes = computed<string[]>(() => user.value?.scopes ?? []);
  function hasScope(scope: string): boolean {
    if (!user.value) return false;
    if (user.value.is_superuser) return true;
    return scopes.value.includes(scope) || scopes.value.includes("*");
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true;
    try {
      const pair = await authApi.login(email, password);
      setTokens(pair);
      user.value = await authApi.me();
    } finally {
      loading.value = false;
    }
  }

  async function signup(email: string, password: string, full_name?: string): Promise<void> {
    loading.value = true;
    try {
      const pair = await authApi.signup(email, password, full_name);
      setTokens(pair);
      user.value = await authApi.me();
    } finally {
      loading.value = false;
    }
  }

  async function fetchMe(): Promise<void> {
    if (!getAccessToken()) {
      user.value = null;
      return;
    }
    try {
      user.value = await authApi.me();
    } catch {
      user.value = null;
    }
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } finally {
      clearTokens();
      user.value = null;
    }
  }

  /** Restore from localStorage on app start. */
  async function init(): Promise<void> {
    if (initialized.value) return;
    initialized.value = true;
    await fetchMe();
  }

  return {
    user,
    loading,
    initialized,
    isLoggedIn,
    isSuperuser,
    scopes,
    hasScope,
    login,
    signup,
    logout,
    fetchMe,
    init,
  };
});