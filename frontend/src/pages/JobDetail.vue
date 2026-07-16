<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import { ArrowLeft, Play, Square } from "lucide-vue-next";
import Button from "@/components/ui/Button.vue";
import Card from "@/components/ui/Card.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import LiveLogViewer from "@/components/run/LiveLogViewer.vue";
import { jobsApi, runsApi, errorMsg } from "@/api/client";
import { formatDate } from "@/lib/utils";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();
const { t } = useI18n();

type TabKey = "overview" | "runs" | "results";
const tab = ref<TabKey>((route.query.tab as TabKey) || "runs");
watch(tab, (v) => router.replace({ query: { ...route.query, tab: v } }));

const { data: job, isLoading } = useQuery({
  queryKey: ["job", props.id],
  queryFn: () => jobsApi.get(props.id),
  enabled: computed(() => !!props.id),
});

const queryParams = ref({ status: "", page: 1, size: 10 });
const { data: runsPage, refetch: refetchRuns } = useQuery({
  queryKey: ["runs", props.id, queryParams],
  queryFn: () => runsApi.listForJob(props.id, { status: queryParams.value.status || undefined, page: queryParams.value.page, size: queryParams.value.size }),
});

const activeRunId = ref<string | null>(null);
async function startRun() {
  try {
    const run = await runsApi.start(props.id, { triggered_by: "manual" });
    activeRunId.value = run.id;
    toast.success(t("toast.run_started"));
    tab.value = "runs";
    refetchRuns();
  } catch (e) {
    toast.error(errorMsg(e));
  }
}
async function cancelRun(id: string) {
  if (!confirm("Hủy run này?")) return;
  try {
    await runsApi.cancel(id);
    toast.success(t("toast.run_cancelled"));
    refetchRuns();
  } catch (e) {
    toast.error(errorMsg(e));
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-3">
      <Button variant="ghost" size="icon" @click="router.push({ name: 'jobs' })"><ArrowLeft class="h-4 w-4" /></Button>
      <div class="flex-1">
        <h1 class="text-2xl font-bold leading-none">
          {{ job?.name ?? (isLoading ? "..." : "Job") }}
        </h1>
        <p v-if="job" class="mt-1 text-sm text-muted-foreground">{{ formatDate(job?.updated_at) }}</p>
      </div>
      <StatusBadge v-if="job" :status="job.status" />
      <Button v-if="job?.status === 'active' || job?.status === 'paused'" variant="secondary" @click="startRun">
        <Play class="h-4 w-4 text-emerald-600" /> {{ t("runs.start_run") }}
      </Button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b">
      <button
        v-for="(tabKey, i) in ['overview', 'runs', 'results']"
        :key="tabKey"
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="tab === tabKey ? 'border-brand-600 text-brand-700 dark:text-brand-300' : 'border-transparent text-muted-foreground hover:text-foreground'"
        @click="tab = tabKey as TabKey"
      >
        {{ ['Overview', 'Runs', 'Results'][i] }}
      </button>
    </div>

    <!-- Overview -->
    <div v-if="tab === 'overview'" class="grid lg:grid-cols-2 gap-4">
      <Card title="Cấu hình">
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between"><dt class="text-muted-foreground">Start URLs</dt><dd>{{ job?.start_urls?.join(", ") }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Domains</dt><dd>{{ job?.allowed_domains?.join(", ") || "—" }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Item</dt><dd class="font-mono">{{ job?.item_container || "(root)" }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Render JS</dt><dd>{{ job?.render_js ? "✓" : "✗" }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Delay</dt><dd>{{ job?.delay }}s</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Concurrency</dt><dd>{{ job?.concurrency || "default" }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Max pages</dt><dd>{{ job?.max_pages || "∞" }}</dd></div>
          <div class="flex justify-between"><dt class="text-muted-foreground">Cron</dt><dd class="font-mono">{{ job?.schedule_cron || "—" }}</dd></div>
        </dl>
      </Card>
      <Card title="Field selectors">
        <div class="space-y-2 text-sm">
          <div v-for="(spec, name) in job?.fields" :key="name" class="rounded-md border bg-muted/30 px-3 py-2">
            <p class="font-mono font-medium">{{ name }}</p>
            <p class="text-xs text-muted-foreground">
              <span class="font-mono">{{ spec.selector }}</span>
              <span v-if="spec.attr"> · @{{ spec.attr }}</span>
              <span v-if="spec.transform"> · {{ spec.transform }}</span>
            </p>
          </div>
        </div>
      </Card>
    </div>

    <!-- Runs -->
    <div v-else-if="tab === 'runs'" class="space-y-4">
      <div v-if="activeRunId" class="space-y-2">
        <h3 class="text-sm font-semibold">{{ t("runs.live_log") }}</h3>
        <LiveLogViewer :run-id="activeRunId" @done="refetchRuns()" />
      </div>

      <div class="rounded-lg border">
        <table class="w-full">
          <thead>
            <tr class="border-b bg-muted/30 text-left text-xs uppercase text-muted-foreground">
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Started</th>
              <th class="px-3 py-2">Pages</th>
              <th class="px-3 py-2">Items</th>
              <th class="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in runsPage?.items ?? []" :key="r.id">
              <td class="px-3 py-2"><StatusBadge :status="r.status" /></td>
              <td class="px-3 py-2 text-xs">{{ formatDate(r.started_at || r.created_at) }}</td>
              <td class="px-3 py-2 text-xs">{{ r.pages_crawled }}/{{ r.pages_failed }} fail</td>
              <td class="px-3 py-2 text-xs">{{ r.items_extracted }}</td>
              <td class="px-3 py-2 text-right">
                <Button
                  variant="ghost"
                  size="xs"
                  @click="activeRunId = r.id"
                  v-if="r.status === 'running' || r.status === 'pending'"
                >
                  Watch
                </Button>
                <Button
                  v-if="r.status === 'running' || r.status === 'pending'"
                  variant="ghost"
                  size="xs"
                  @click="cancelRun(r.id)"
                >
                  <Square class="h-3 w-3 text-destructive" />
                </Button>
              </td>
            </tr>
            <tr v-if="!runsPage?.items?.length">
              <td colspan="5" class="px-3 py-8 text-center text-sm text-muted-foreground">{{ t("common.noData") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Results (link to /results?job_id) -->
    <div v-else class="space-y-3">
      <p class="text-sm text-muted-foreground">Xem kết quả crawl chi tiết trong trang Results.</p>
      <Button @click="router.push({ name: 'results', query: { job_id: props.id } })">Mở Results →</Button>
    </div>
  </div>
</template>