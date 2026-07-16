<script setup lang="ts">
import { cn } from "@/lib/utils";
const props = withDefaults(defineProps<{ class?: string; modelValue?: string | number; type?: string; placeholder?: string; disabled?: boolean; required?: boolean }>(), { type: "text", disabled: false, required: false });
defineEmits<{ "update:modelValue": [v: string] }>();
</script>

<template>
  <input
    :class="cn('flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50', props.class)"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :required="required"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>