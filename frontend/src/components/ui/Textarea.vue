<script setup lang="ts">
import { cn } from "@/lib/utils";
const props = withDefaults(defineProps<{ class?: string; modelValue?: string; placeholder?: string; rows?: number; disabled?: boolean }>(), { rows: 4, disabled: false });
defineEmits<{ "update:modelValue": [v: string] }>();
</script>

<template>
  <textarea
    :rows="rows"
    :class="cn('flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono', props.class)"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
  />
</template>