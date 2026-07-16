<script setup lang="ts">
import { ref, computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { toast } from "vue-sonner";
import { Plus, Search, Pencil, Trash2, Play } from "lucide-vue-next";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import Dialog from "@/components/ui/Dialog.vue";
import JobForm from "@/components/job/JobForm.vue";
import { jobsApi, runsApi, errorMsg } from "@/api/client";
import type { JobRead, JobCreate } from "@/types";
import { formatRelative, trunc } from "@/lib/utils";

const { t } = useI18n();
const router = useRouter();

const search = ref("");
const page = ref(1);
const size = ref(20);

const jobsQ = useQuery({
  queryKey: ["jobs", search, page, size],
  queryFn: () =>
    jobsApi.list({ q: search.value || undefined, page: page.value, size: size.value }),
});
const data = computed(() => jobsQ.data.value);
const isLoading = computed(() => jobsQ.isLoading.value);
const refetch = () => jobsQ.refetch();

const showForm = ref(false);
const editing = ref<JobRead | null>(null);
const submitLoading = ref(false);

function openNew() {
  editing.value = null;
  showForm.value = true;
}
function openEdit(j: JobRead) {
  editing.value = j;
  showForm.value = true;
}
async function submitJob(payload: JobCreate) {
  submitLoading.value = true;
  try {
    if (editing.value) {
      await jobsApi.update(editing.value.id, payload);
      toast.success(t("toast.job_updated"));
    } else {
      await jobsApi.create(payload);
      toast.success(t("toast.job_created"));
    }
    showForm.value = false;
    refetch();
  } catch (e) {
    toast.error(errorMsg(e));
  } finally {
    submitLoading.value = false;
  }
}

async function deleteJob(j: JobRead) {
  if (!confirm(`Xóa job "${j.name}"?`)) return;
  try {
    await jobsApi.delete(j.id);
    toast.success(t("toast.job_deleted"));
    refetch();
  } catch (e) {
    toast.error(errorMsg(e));
  }
}

async function startRun(j: JobRead) {
  try {
    const run = await runsApi.start(j.id, { triggered_by: "manual" });
    toast.success(t("toast.run_started"));
    router.push({ name: "job-detail", params: { id: j.id, _run: run.id } });
  } catch (e) {
    toast.error(errorMsg(e));
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold">{{ t("jobs.title") }}</h1>
        <p class="text-sm text-muted-foreground">Quản lý crawl jobs</p>
      </div>
      <Button @click="openNew">
        <Plus class="h-4 w-4" /> {{ t("jobs.new") }}
      </Button>
    </div>

    <div class="flex items-center gap-2">
      <div class="relative w-full max-w-sm">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input v-model="search" :placeholder="t('jobs.search')" class="pl-9" />
      </div>
    </div>

    <div class="rounded-lg border bg-card">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b bg-muted/30 text-left text-xs uppercase text-muted-foreground">
              <th class="px-4 py-3">Name</th>
              <th class="px-4 py-3">Status</th>
              <th class="px-4 py-3">Pages</th>
              <th class="px-4 py-3">Updated</th>
              <th class="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading">
              <td colspan="5" class="px-4 py-12 text-center text-muted-foreground">{{ t("common.loading") }}</td>
            </tr>
            <tr v-else-if="!data?.items?.length">
              <td colspan="5" class="px-4 py-12 text-center text-muted-foreground">{{ t("common.noData") }}</td>
            </tr>
            <tr v-for="j in data?.items ?? []" :key="j.id" class="border-b last:border-0 hover:bg-muted/30">
              <td class="px-4 py-3">
                <button
                  class="font-medium text-foreground hover:text-brand-700 dark:hover:text-brand-300"
                  @click="router.push({ name: 'job-detail', params: { id: j.id } })"
                >
                  {{ j.name }}
                </button>
                <p class="text-xs text-muted-foreground">{{ trunc(j.description || j.start_urls?.[0] || "", 70) }}</p>
              </td>
              <td class="px-4 py-3"><StatusBadge :status="j.status" /></td>
              <td class="px-4 py-3 text-sm">{{ j.max_pages || "∞" }}</td>
              <td class="px-4 py-3 text-xs text-muted-foreground">{{ formatRelative(j.updated_at) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  <Button variant="ghost" size="icon" @click="startRun(j)" :title="t('runs.start_run')"><Play class="h-4 w-4 text-emerald-600" /></Button>
                  <Button variant="ghost" size="icon" @click="openEdit(j)"><Pencil class="h-4 w-4" /></Button>
                  <Button variant="ghost" size="icon" @click="deleteJob(j)"><Trash2 class="h-4 w-4 text-destructive" /></Button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <Dialog v-model:open="showForm" :title="editing ? t('common.edit') : t('jobs.new')" size="xl" :closable="true">
    <JobForm :initial="editing" :submit-loading="submitLoading" @submit="submitJob" @cancel="showForm = false" />
  </Dialog>
</template>