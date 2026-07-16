<script setup lang="ts">
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import Card from "@/components/ui/Card.vue";
import { jobsApi, runsApi } from "@/api/client";
import { formatNumber, formatRelative } from "@/lib/utils";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { Activity, Database, FileText, TrendingUp } from "lucide-vue-next";

const { t } = useI18n();

const jobsQ = useQuery({ queryKey: ["jobs", "", 1, 200], queryFn: () => jobsApi.list({ page: 1, size: 200 }) });
const runsQ = useQuery({
  queryKey: ["runs-recent"],
  queryFn: () => runsApi.list({ page: 1, size: 10 }),
});

const activeJobs = computed(() => (jobsQ.data.value?.items ?? []).filter((j) => j.status === "active").length);
const totalRuns = computed(() => runsQ.data.value?.total ?? 0);
const totalItems = computed(() => (runsQ.data.value?.items ?? []).reduce((s, r) => s + (r.items_extracted || 0), 0));
const successRate = computed(() => {
  const arr = runsQ.data.value?.items ?? [];
  if (!arr.length) return 0;
  const ok = arr.filter((r) => r.status === "done").length;
  return Math.round((ok / arr.length) * 100);
});
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold">{{ t("dashboard.title") }}</h1>
      <p class="text-sm text-muted-foreground">Tổng quan hệ thống crawler</p>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card class="p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs uppercase text-muted-foreground">{{ t("dashboard.kpi_active_jobs") }}</p>
            <p class="mt-1 text-2xl font-bold">{{ formatNumber(activeJobs) }}</p>
          </div>
          <Activity class="h-8 w-8 text-brand-600" />
        </div>
      </Card>
      <Card class="p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs uppercase text-muted-foreground">{{ t("dashboard.kpi_items_today") }}</p>
            <p class="mt-1 text-2xl font-bold">{{ formatNumber(totalItems) }}</p>
          </div>
          <Database class="h-8 w-8 text-emerald-600" />
        </div>
      </Card>
      <Card class="p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs uppercase text-muted-foreground">{{ t("dashboard.kpi_runs_24h") }}</p>
            <p class="mt-1 text-2xl font-bold">{{ formatNumber(totalRuns) }}</p>
          </div>
          <FileText class="h-8 w-8 text-amber-600" />
        </div>
      </Card>
      <Card class="p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs uppercase text-muted-foreground">{{ t("dashboard.kpi_success_rate") }}</p>
            <p class="mt-1 text-2xl font-bold">{{ successRate }}%</p>
          </div>
          <TrendingUp class="h-8 w-8 text-purple-600" />
        </div>
      </Card>
    </div>

    <Card>
      <h2 class="mb-3 text-lg font-semibold">{{ t("dashboard.recent_runs") }}</h2>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b text-left text-xs uppercase text-muted-foreground">
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Job</th>
              <th class="px-3 py-2">Pages</th>
              <th class="px-3 py-2">Items</th>
              <th class="px-3 py-2">When</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in runsQ.data.value?.items ?? []" :key="r.id" class="border-b last:border-0">
              <td class="px-3 py-2"><StatusBadge :status="r.status" /></td>
              <td class="px-3 py-2 font-mono text-xs">{{ r.job_id.slice(0, 8) }}</td>
              <td class="px-3 py-2 text-xs">{{ r.pages_crawled }}<span class="text-muted-foreground">/{{ r.pages_failed }}</span></td>
              <td class="px-3 py-2 text-xs">{{ r.items_extracted }}</td>
              <td class="px-3 py-2 text-xs text-muted-foreground">{{ formatRelative(r.created_at) }}</td>
            </tr>
            <tr v-if="!runsQ.data.value?.items?.length">
              <td colspan="5" class="px-3 py-8 text-center text-muted-foreground">{{ t("common.noData") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>