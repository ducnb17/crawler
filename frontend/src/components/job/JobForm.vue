<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Switch from "@/components/ui/Switch.vue";
import type { FieldSpec, JobCreate, JobRead } from "@/types";

const props = defineProps<{ initial?: JobRead | null; submitLoading?: boolean }>();
const emit = defineEmits<{ submit: [payload: JobCreate]; cancel: [] }>();

const { t } = useI18n();
const step = ref(1);

const form = reactive<JobCreate>({
  name: props.initial?.name ?? "",
  description: props.initial?.description ?? "",
  start_urls: props.initial?.start_urls ?? [],
  allowed_domains: props.initial?.allowed_domains ?? [],
  item_container: props.initial?.item_container ?? "",
  fields: props.initial?.fields ? { ...props.initial.fields } : { title: { selector: "h1", type: "text" } },
  next_page: props.initial?.next_page ?? "",
  follow_links: props.initial?.follow_links ?? false,
  max_pages: props.initial?.max_pages ?? 0,
  max_depth: props.initial?.max_depth ?? 0,
  delay: props.initial?.delay ?? 1.0,
  render_js: props.initial?.render_js ?? false,
  robots_obey: props.initial?.robots_obey ?? true,
  concurrency: props.initial?.concurrency ?? 2,
  schedule_cron: props.initial?.schedule_cron ?? "",
  is_active: props.initial?.is_active ?? false,
  allow_concurrent_runs: props.initial?.allow_concurrent_runs ?? false,
  proxy_profile_id: props.initial?.proxy_profile_id ?? null,
  webhook_id: props.initial?.webhook_id ?? null,
  llm_detect_config: props.initial?.llm_detect_config ?? {},
});

const startUrlsText = ref(form.start_urls.join("\n"));
const allowedDomainsText = ref(form.allowed_domains.join("\n"));

const transforms: NonNullable<FieldSpec["transform"]>[] = ["strip", "lower", "upper", "int", "float", "price"];

// Computed wrappers for nullable fields (FieldSpec allows null but inputs expect string).
const descriptionModel = computed({
  get: () => form.description ?? "",
  set: (v: string) => { form.description = v; },
});
const itemContainerModel = computed({
  get: () => form.item_container ?? "",
  set: (v: string) => { form.item_container = v; },
});
const nextPageModel = computed({
  get: () => form.next_page ?? "",
  set: (v: string) => { form.next_page = v; },
});
const scheduleCronModel = computed({
  get: () => form.schedule_cron ?? "",
  set: (v: string) => { form.schedule_cron = v; },
});

function addField() {
  const name = prompt("Tên trường mới:");
  if (!name) return;
  if (form.fields[name]) {
    alert("Trường đã tồn tại");
    return;
  }
  form.fields[name] = { selector: "", type: "text" };
}

function removeField(name: string) {
  delete form.fields[name];
}

const submitReady = computed(
  () => !!form.name?.trim() && form.start_urls.length > 0
);

function next() {
  if (step.value === 1) {
    const urls = startUrlsText.value.split("\n").map((u) => u.trim()).filter(Boolean);
    form.start_urls = urls;
    form.allowed_domains = allowedDomainsText.value.split("\n").map((d) => d.trim()).filter(Boolean);
    if (!urls.length) {
      alert("Cần nhập ít nhất 1 start_url");
      return;
    }
  }
  if (step.value < 3) step.value++;
  else submit();
}

function back() {
  if (step.value > 1) step.value--;
}

function submit() {
  if (!submitReady.value) return;
  emit("submit", { ...form });
}
</script>

<template>
  <div class="space-y-5">
    <!-- Stepper -->
    <ol class="flex items-center gap-2 text-xs">
      <li v-for="s in [1, 2, 3]" :key="s" class="flex items-center gap-2">
        <button
          class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
          :class="step >= s ? 'bg-brand-600 text-white' : 'bg-muted text-muted-foreground'"
          @click="step = s"
        >
          {{ s }}
        </button>
        <span class="hidden sm:inline" :class="step >= s ? 'text-foreground font-medium' : 'text-muted-foreground'">
          {{ s === 1 ? t('jobs.wizard.step_target') : s === 2 ? t('jobs.wizard.step_selectors') : t('jobs.wizard.step_schedule') }}
        </span>
        <span v-if="s < 3" class="mx-1 h-px w-6 bg-border" />
      </li>
    </ol>

    <!-- Step 1: Target -->
    <div v-if="step === 1" class="space-y-4">
      <div>
        <label class="text-sm font-medium">{{ t("jobs.name") }}</label>
        <Input v-model="form.name" class="mt-1" placeholder="vd: books.toscrape limited" />
      </div>
      <div>
        <label class="text-sm font-medium">{{ t("jobs.description") }}</label>
        <Textarea v-model="descriptionModel" class="mt-1" :rows="2" placeholder="Mô tả ngắn gọn..." />
      </div>
      <div class="grid sm:grid-cols-2 gap-4">
        <div>
          <label class="text-sm font-medium">{{ t("jobs.start_urls") }}</label>
          <Textarea v-model="startUrlsText" :rows="4" placeholder="https://..." class="mt-1" />
          <p class="mt-1 text-xs text-muted-foreground">Mỗi URL 1 dòng</p>
        </div>
        <div>
          <label class="text-sm font-medium">{{ t("jobs.allowed_domains") }}</label>
          <Textarea v-model="allowedDomainsText" :rows="4" placeholder="example.com" class="mt-1" />
          <p class="mt-1 text-xs text-muted-foreground">Bỏ trống để không giới hạn</p>
        </div>
      </div>
      <div>
        <div class="mb-1 flex items-center justify-between">
          <label class="text-sm font-medium">{{ t("jobs.render_js") }}</label>
          <Switch v-model="form.render_js" />
        </div>
        <p class="text-xs text-muted-foreground">Render JS qua Playwright — chậm hơn nhưng lấy được trang SPA.</p>
      </div>
    </div>

    <!-- Step 2: Selectors -->
    <div v-else-if="step === 2" class="space-y-4">
      <div>
        <label class="text-sm font-medium">{{ t("jobs.item_container") }}</label>
        <Input v-model="itemContainerModel" class="mt-1" placeholder="article.product_pod" />
        <p class="mt-1 text-xs text-muted-foreground">CSS selector của mỗi item. Để trống nếu chỉ trích 1 page.</p>
      </div>
      <div>
        <div class="mb-2 flex items-center justify-between">
          <label class="text-sm font-medium">{{ t("jobs.fields") }}</label>
          <Button size="xs" variant="secondary" @click="addField">+ {{ t("jobs.wizard.add_field") }}</Button>
        </div>
        <div class="space-y-2">
          <div v-for="(f, name) in form.fields" :key="name" class="grid grid-cols-12 items-center gap-2">
            <Input :model-value="String(name)" disabled class="col-span-3 bg-muted/50" />
            <Input v-model="f.selector" placeholder="CSS selector" class="col-span-5" />
            <Input :model-value="f.attr ?? ''" @update:model-value="f.attr = $event || null" placeholder="attr?" class="col-span-2" />
            <select
              :model-value="f.transform ?? ''"
              @update:model-value="f.transform = ($event || null) as FieldSpec['transform']"
              class="col-span-1 h-10 rounded-md border border-input bg-background px-1 text-xs"
            >
              <option value="">—</option>
              <option v-for="tr in transforms" :key="tr" :value="tr">{{ tr }}</option>
            </select>
            <Button variant="ghost" size="icon" class="col-span-1" @click="removeField(String(name))">✕</Button>
          </div>
        </div>
      </div>
      <div>
        <label class="text-sm font-medium">{{ t("jobs.next_page") }}</label>
        <Input v-model="nextPageModel" class="mt-1" placeholder='li.next a::attr(href)' />
      </div>
    </div>

    <!-- Step 3: Schedule -->
    <div v-else class="grid sm:grid-cols-2 gap-4">
      <div>
        <label class="text-sm font-medium">{{ t("jobs.max_pages") }}</label>
        <Input v-model.number="form.max_pages" type="number" min="0" class="mt-1" />
      </div>
      <div>
        <label class="text-sm font-medium">{{ t("jobs.max_depth") }}</label>
        <Input v-model.number="form.max_depth" type="number" min="0" class="mt-1" />
      </div>
      <div>
        <label class="text-sm font-medium">{{ t("jobs.delay") }}</label>
        <Input v-model.number="form.delay" type="number" step="0.1" min="0" class="mt-1" />
      </div>
      <div>
        <label class="text-sm font-medium">{{ t("jobs.concurrency") }}</label>
        <Input v-model.number="form.concurrency" type="number" min="1" max="50" class="mt-1" />
      </div>
      <div class="sm:col-span-2">
        <label class="text-sm font-medium">{{ t("jobs.schedule_cron") }}</label>
        <Input v-model="scheduleCronModel" class="mt-1" placeholder="*/15 * * * * (để trống = không tự chạy)" />
      </div>
      <div class="flex items-center justify-between rounded-md border p-3">
        <div>
          <label class="text-sm font-medium">{{ t("jobs.is_active") }}</label>
          <p class="text-xs text-muted-foreground">Kích hoạt để lên lịch crawl</p>
        </div>
        <Switch v-model="form.is_active" />
      </div>
      <div class="flex items-center justify-between rounded-md border p-3">
        <div>
          <label class="text-sm font-medium">{{ t("jobs.allow_concurrent_runs") }}</label>
          <p class="text-xs text-muted-foreground">Cho phép nhiều run song song</p>
        </div>
        <Switch v-model="form.allow_concurrent_runs" />
      </div>
      <div class="flex items-center justify-between rounded-md border p-3">
        <div>
          <label class="text-sm font-medium">{{ t("jobs.robots_obey") }}</label>
          <p class="text-xs text-muted-foreground">Tuân thủ robots.txt</p>
        </div>
        <Switch v-model="form.robots_obey" />
      </div>
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between pt-4">
      <Button variant="outline" @click="emit('cancel')">{{ t("common.cancel") }}</Button>
      <div class="flex gap-2">
        <Button v-if="step > 1" variant="ghost" @click="back">← {{ t("common.prev") }}</Button>
        <Button v-if="step < 3" @click="next">{{ t("common.next") }} →</Button>
        <Button v-else :loading="submitLoading" :disabled="!submitReady" @click="submit">{{ t("common.save") }}</Button>
      </div>
    </div>
  </div>
</template>