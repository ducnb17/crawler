<script setup lang="ts">
import { RouterView } from "vue-router";
import { Toaster } from "vue-sonner";
import { onMounted } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";

const auth = useAuthStore();
const theme = useThemeStore();

onMounted(async () => {
  // Apply theme class pronto
  await theme;
  await auth.init();
});
</script>

<template>
  <Toaster
    rich-colors
    position="top-right"
    :toast-options="{ duration: 4000 }"
    class="pointer-events-auto"
  />
  <RouterView v-slot="{ Component }">
    <Transition name="fade" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>