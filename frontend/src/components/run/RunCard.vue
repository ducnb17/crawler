<script setup lang="ts">
import { computed } from "vue";
import { formatNumber } from "@/lib/utils";
import StatusBadge from "@/components/ui/StatusBadge.vue";

const props = defineProps<{ run: { status: string; started_at: string | null; ended_at: string | null; pages_crawled: number; pages_failed: number; items_extracted: number; triggered_by: string } }>();

const dur = computed(() => {
  if (!props.run.started_at) return "—";
  const s = new Date(props.run.started_at).getTime();
  const e = props.run.ended_at ? new Date(props.run.ended_at).getTime() : Date.now();
  const diff = Math.max(0, e - s);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  return `${m}m ${sec % 60}s`;
});
</script>

<template>
  <div class="flex items-center gap-2">
    <StatusBadge :status="run.status" />
    <span class="text-xs text-muted-foreground">·</span>
    <span class="text-xs">⏱ {{ dur }}</span>
    <span class="text-xs text-muted-foreground">·</span>
    <span class="text-xs">📄 {{ formatNumber(run.pages_crawled) }}</span>
    <span class="text-xs text-muted-foreground">·</span>
    <span class="text-xs">📦 {{ formatNumber(run.items_extracted) }}</span>
    <span class="text-xs text-muted-foreground">·</span>
    <span class="text-xs">{{ run.triggered_by }}</span>
  </div>
</template>