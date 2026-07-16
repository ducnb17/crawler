<script setup lang="ts">
import { computed } from "vue";
import { cn } from "@/lib/utils";
const props = withDefaults(defineProps<{ modelValue?: boolean; disabled?: boolean; size?: "sm" | "md" }>(), { size: "md", disabled: false });
const emit = defineEmits<{ "update:modelValue": [v: boolean] }>();

function toggle() {
  if (props.disabled) return;
  emit("update:modelValue", !props.modelValue);
}

const kn = computed(() => (props.size === "sm" ? "h-4 w-7" : "h-5 w-9"));
const dot = computed(() => (props.size === "sm" ? "h-3 w-3" : "h-4 w-4"));
</script>

<template>
  <button
    type="button"
    :disabled="disabled"
    :class="cn('relative inline-flex shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50', kn, modelValue ? 'bg-brand-600' : 'bg-muted')"
    @click="toggle"
  >
    <span :class="cn('inline-block transform rounded-full bg-background shadow-lg transition-transform', dot, modelValue ? 'translate-x-4' : 'translate-x-1')" />
  </button>
</template>