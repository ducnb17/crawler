<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRunEvents } from "@/composables/useSSE";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import type { RunEvent } from "@/types";
import { formatDate } from "@/lib/utils";

const props = defineProps<{ runId: string; initialStatus?: string }>();
const emit = defineEmits<{ done: [RunEvent] }>();

interface LogLine {
  ts: string;
  event: string;
  text: string;
  level: "info" | "warn" | "error" | "success";
}

const log = ref<LogLine[]>([]);
const connected = ref(false);
const autoScroll = ref(true);
const lastEvent = ref<RunEvent | null>(null);
const container = ref<HTMLDivElement | null>(null);

function render(e: RunEvent) {
  lastEvent.value = e;
  const ts = ("ts" in e && e.ts) || new Date().toISOString();
  let line: LogLine;
  switch (e.event) {
    case "start":
      line = { ts, event: e.event, text: `▶ Run bắt đầu (run=${e.run_id} job=${e.job_id})`, level: "info" };
      break;
    case "page_done":
      line = { ts, event: e.event, text: `✓ ${e.url || ""} · ${e.items || 0} items · ${e.elapsed_ms}ms${e.fallback ? " · " + e.fallback : ""}`, level: "success" };
      break;
    case "page_failed":
      line = { ts, event: e.event, text: `✗ ${e.url || ""} ${e.error ? "· " + e.error : ""}`, level: "error" };
      break;
    case "progress":
      line = { ts, event: e.event, text: `… progress · pages=${e.pages_crawled} items=${e.items}`, level: "info" };
      break;
    case "done":
      line = { ts, event: e.event, text: `✓ DONE · pages=${e.pages_crawled} failed=${e.pages_failed} items=${e.items_extracted} pw=${e.fallbacks_playwright} cf=${e.fallbacks_cloudscraper}`, level: "success" };
      emit("done", e);
      break;
    case "error":
      line = { ts, event: e.event, text: `❌ ${e.error}`, level: "error" };
      emit("done", e);
      break;
    default:
      return;
  }
  log.value.push(line);
  if (log.value.length > 500) log.value.splice(0, log.value.length - 500);
  if (autoScroll.value) {
    requestAnimationFrame(() => {
      if (container.value) container.value.scrollTop = container.value.scrollHeight;
    });
  }
}

const { connected: conn, setRunId, stop } = useRunEvents(ref(props.runId), { onEvent: render });
watch(conn, (v) => (connected.value = v));

onMounted(() => setRunId(props.runId));
onUnmounted(stop);

function clearLog() {
  log.value = [];
}
</script>

<template>
  <div class="flex flex-col rounded-lg border bg-black/90 text-xs leading-relaxed">
    <div class="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2">
      <div class="flex items-center gap-2">
        <span class="status-dot" :class="connected ? 'status-dot--ok' : 'status-dot--pending'" />
        <span class="font-mono text-[11px] text-white/70">{{ connected ? "live" : "disconnected" }}</span>
        <StatusBadge v-if="initialStatus" :status="initialStatus" class="ml-2" />
      </div>
      <label class="flex items-center gap-1 text-[11px] text-white/60">
        <input v-model="autoScroll" type="checkbox" class="h-3 w-3" />
        auto-scroll
        <button class="ml-3 rounded px-2 py-0.5 text-white/70 hover:bg-white/10" @click="clearLog">clear</button>
      </label>
    </div>
    <div ref="container" class="h-full max-h-[60vh] min-h-[220px] grow overflow-y-auto p-2 font-mono">
      <p v-for="(l, i) in log" :key="i" class="px-1 py-px" :class="l.level === 'error' ? 'text-red-400' : l.level === 'success' ? 'text-emerald-400' : 'text-white/80'">
        <span class="text-white/40">{{ formatDate(l.ts).slice(-5) }}</span>
        <span class="ml-2">{{ l.text }}</span>
      </p>
      <p v-if="!log.length" class="text-white/40 italic">Đang chờ events...</p>
    </div>
  </div>
</template>