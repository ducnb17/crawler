<script setup lang="ts">
import { cn } from "@/lib/utils";
const props = withDefaults(defineProps<{ class?: string; modelValue?: string | number; disabled?: boolean }>(), { disabled: false });
defineEmits<{ "update:modelValue": [v: string] }>();
</script>

<template>
  <select
    :value="modelValue"
    :disabled="disabled"
    :class="cn('flex h-10 w-full items-center rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50', props.class)"
    @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
  >
    <slot />
  </select>
</template>