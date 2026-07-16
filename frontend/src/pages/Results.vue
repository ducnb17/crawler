<script setup lang="ts">
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { Download, Search } from "lucide-vue-next";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Card from "@/components/ui/Card.vue";
import { resultsApi } from "@/api/client";
import { formatDate, trunc } from "@/lib/utils";

const { t } = useI18n();
const route = useRoute();

const q = ref("");
const urlContains = ref("");
const jobId = computed(() => (route.query.job_id as string) || undefined);
const page = ref(1);
const size = ref(20);
const sort = ref("extracted_at:desc");

const resultsQ = useQuery({
  queryKey: ["results", q, urlContains, jobId, page, size, sort],
  queryFn: () =>
    resultsApi.list({
      q: q.value || undefined,
      url_contains: urlContains.value || undefined,
      job_id: jobId.value,
      page: page.value,
      size: size.value,
      sort: sort.value,
    }),
  refetchInterval: 5000,
});

const data = computed(() => resultsQ.data.value);
const isLoading = computed(() => resultsQ.isLoading.value);
const isFetching = computed(() => resultsQ.isFetching.value);

const cols = computed<string[]>(() => {
  const set = new Set<string>();
  for (const it of data.value?.items ?? []) {
    Object.keys(it.data).forEach((k) => set.add(k));
  }
  return Array.from(set).slice(0, 12);
});

function exportCsv() {
  const u = resultsApi.exportCsvUrl({
    job_id: jobId.value,
    q: q.value || undefined,
  });
  window.open(u, "_blank");
}
function exportJson() {
  const u = resultsApi.exportJsonUrl({
    job_id: jobId.value,
    q: q.value || undefined,
  });
  window.open(u, "_blank");
}

function goto(p: number) {
  page.value = p;
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold">{{ t("results.title") }}</h1>
        <p class="text-sm text-muted-foreground">Kết quả crawl (auto-refresh 5s)</p>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" @click="exportCsv"><Download class="h-4 w-4" /> CSV</Button>
        <Button variant="outline" size="sm" @click="exportJson"><Download class="h-4 w-4" /> JSON</Button>
      </div>
    </div>

    <Card>
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative grow min-w-[200px]">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="q" :placeholder="t('common.search')" class="pl-9" />
        </div>
        <Input v-model="urlContains" placeholder="URL contains..." class="w-44" />
        <Select v-model="sort" class="w-44">
          <option value="extracted_at:desc">↓ Extracted</option>
          <option value="extracted_at:asc">↑ Extracted</option>
          <option value="url:asc">↑ URL</option>
          <option value="url:desc">↓ URL</option>
        </Select>
        <Button variant="secondary" size="sm" @click="page = 1">Apply</Button>
        <span v-if="isFetching" class="text-xs text-muted-foreground">⟳ {{ t("common.loading") }}</span>
      </div>

      <div class="mt-4 overflow-x-auto rounded-md border">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b bg-muted/30 text-left text-xs uppercase text-muted-foreground">
              <th class="px-3 py-2 w-40">URL</th>
              <th v-for="c in cols" :key="c" class="px-3 py-2">{{ c }}</th>
              <th class="px-3 py-2">Extracted</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading">
              <td :colspan="cols.length + 2" class="px-3 py-12 text-center text-muted-foreground">{{ t("common.loading") }}</td>
            </tr>
            <tr v-else-if="!data?.items?.length">
              <td :colspan="cols.length + 2" class="px-3 py-12 text-center text-muted-foreground">{{ t("common.noData") }}</td>
            </tr>
            <tr v-for="r in data?.items ?? []" :key="r.id" class="border-b last:border-0 hover:bg-muted/30">
              <td class="px-3 py-2 font-mono text-xs" :title="r.url">{{ trunc(r.url, 40) }}</td>
              <td v-for="c in cols" :key="c" class="px-3 py-2 text-xs">
                {{ r.data?.[c] != null ? trunc(String(r.data?.[c]), 50) : "—" }}
              </td>
              <td class="px-3 py-2 text-xs text-muted-foreground">{{ formatDate(r.extracted_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="data" class="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>{{ data.total }} items</span>
        <div class="flex items-center gap-2">
          <Button variant="ghost" size="xs" :disabled="page === 1" @click="goto(page - 1)">←</Button>
          <span>{{ t("common.page") }} {{ page }} / {{ data.pages || 1 }}</span>
          <Button variant="ghost" size="xs" :disabled="page >= data.pages" @click="goto(page + 1)">→</Button>
        </div>
      </div>
    </Card>
  </div>
</template>