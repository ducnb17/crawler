<script setup lang="ts">
const props = withDefaults(
  defineProps<{ status?: "ok" | "running" | "failed" | "pending" | "cancelled" | string }>(),
  { status: "pending" }
);

import { computed } from "vue";
import Badge from "./Badge.vue";

const variant: Record<string, "default" | "success" | "warning" | "destructive" | "secondary" | "info"> = {
  ok: "success",
  done: "success",
  active: "success",
  running: "info",
  pending: "warning",
  draft: "secondary",
  paused: "secondary",
  archived: "secondary",
  failed: "destructive",
  cancelled: "default",
};

const label: Record<string, string> = {
  ok: "✓ OK",
  done: "✓ done",
  active: "active",
  running: "running",
  pending: "pending",
  draft: "draft",
  paused: "paused",
  archived: "archived",
  failed: "failed",
  cancelled: "cancelled",
};

const v = computed(() => variant[props.status] ?? "secondary");
const l = computed(() => label[props.status] ?? String(props.status));
</script>

<template>
  <Badge :variant="v"><span :class="['status-dot', `status-dot--${status}`]" /> <span>{{ l }}</span></Badge>
</template>