<script setup lang="ts">
import { cn } from "@/lib/utils";
const props = withDefaults(defineProps<{ class?: string; title?: string }>(), { title: undefined });
</script>

<template>
  <div :class="cn('rounded-lg border bg-card text-card-foreground shadow-sm', props.class)">
    <div v-if="title" class="px-5 py-4 border-b border-border">
      <p class="text-sm font-semibold leading-none">{{ title }}</p>
    </div>
    <div class="p-5">
      <slot />
    </div>
  </div>
</template>