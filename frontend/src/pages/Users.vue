<script setup lang="ts">
import { ref, computed } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import { Plus, Trash2 } from "lucide-vue-next";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Switch from "@/components/ui/Switch.vue";
import Card from "@/components/ui/Card.vue";
import Dialog from "@/components/ui/Dialog.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { usersApi, errorMsg } from "@/api/client";
import type { UserCreate } from "@/types";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const queryClient = useQueryClient();
const page = ref(1);
const size = ref(20);

const usersQ = useQuery({
  queryKey: ["users", page, size],
  queryFn: () => usersApi.list(page.value, size.value),
  enabled: auth.hasScope("users:read"),
});
const data = computed(() => usersQ.data.value);
const refetch = () => usersQ.refetch();

const showCreate = ref(false);
const form = ref<UserCreate>({ email: "", password: "", full_name: "", scopes: ["jobs:read", "jobs:write", "jobs:run", "results:read", "results:export"], is_superuser: false });

// Computed wrapper for nullable full_name (UserCreate allows null, Input expects string|number).
const fullNameModel = computed({
  get: () => form.value.full_name ?? "",
  set: (v: string) => { form.value.full_name = v; },
});

const availableScopes = [
  "jobs:read", "jobs:write", "jobs:delete", "jobs:run",
  "results:read", "results:export", "results:delete",
  "proxies:read", "proxies:write", "proxies:delete",
  "webhooks:read", "webhooks:write", "webhooks:delete",
  "users:read", "users:write", "users:delete",
  "settings:read", "settings:write",
];

function toggleScope(s: string) {
  const idx = form.value.scopes?.indexOf(s) ?? -1;
  if (idx >= 0) form.value.scopes?.splice(idx, 1);
  else form.value.scopes?.push(s);
}

async function submitCreate() {
  try {
    await usersApi.create(form.value);
    toast.success("User created");
    showCreate.value = false;
    refetch();
  } catch (e) {
    toast.error(errorMsg(e));
  }
}
async function deleteUser(id: string) {
  if (!confirm(t("users.delete_warn"))) return;
  try {
    await usersApi.delete(id);
    toast.success("User deleted");
    refetch();
  } catch (e) {
    toast.error(errorMsg(e));
  }
}

async function toggleActive(u: any) {
  try {
    await usersApi.update(u.id, { is_active: !u.is_active });
    queryClient.invalidateQueries({ queryKey: ["users"] });
  } catch (e) {
    toast.error(errorMsg(e));
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">{{ t("nav.users") }}</h1>
        <p class="text-sm text-muted-foreground">Quản lý user & RBAC scopes</p>
      </div>
      <Button v-if="auth.hasScope('users:write')" @click="showCreate = true"><Plus class="h-4 w-4" /> {{ t("users.create") }}</Button>
    </div>

    <Card>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b bg-muted/30 text-left text-xs uppercase text-muted-foreground">
              <th class="px-3 py-2">{{ t("users.email") }}</th>
              <th class="px-3 py-2">{{ t("users.scopes") }}</th>
              <th class="px-3 py-2">{{ t("users.is_active") }}</th>
              <th class="px-3 py-2">{{ t("users.is_superuser") }}</th>
              <th class="px-3 py-2">Created</th>
              <th class="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in data?.items ?? []" :key="u.id" class="border-b last:border-0">
              <td class="px-3 py-2">{{ u.email }}</td>
              <td class="px-3 py-2 text-xs">
                <span v-if="u.is_superuser" class="rounded bg-brand-100 px-1.5 py-0.5 text-brand-700">superuser</span>
                <span v-else v-for="s in u.scopes" :key="s" class="mr-1 inline-block rounded bg-muted px-1.5 py-0.5 font-mono">{{ s }}</span>
              </td>
              <td class="px-3 py-2">
                <Switch :model-value="u.is_active" @update:model-value="() => toggleActive(u)" :disabled="!auth.hasScope('users:write')" />
              </td>
              <td class="px-3 py-2">
                <StatusBadge :status="u.is_superuser ? 'ok' : 'pending'" />
              </td>
              <td class="px-3 py-2 text-xs text-muted-foreground">{{ formatDate(u.created_at) }}</td>
              <td class="px-3 py-2 text-right">
                <Button v-if="auth.hasScope('users:delete') && !u.is_superuser" variant="ghost" size="icon" @click="deleteUser(u.id)"><Trash2 class="h-4 w-4 text-destructive" /></Button>
              </td>
            </tr>
            <tr v-if="!data?.items?.length">
              <td colspan="6" class="px-3 py-8 text-center text-muted-foreground">{{ t("common.noData") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <Dialog v-model:open="showCreate" :title="t('users.create')" size="lg">
      <div class="space-y-4">
        <div>
          <label class="text-sm font-medium">Email</label>
          <Input v-model="form.email" type="email" class="mt-1" />
        </div>
        <div>
          <label class="text-sm font-medium">Password</label>
          <Input v-model="form.password" type="password" class="mt-1" />
        </div>
        <div>
          <label class="text-sm font-medium">Full name</label>
          <Input v-model="fullNameModel" class="mt-1" />
        </div>
        <div>
          <label class="text-sm font-medium">Scopes</label>
          <div class="mt-2 grid grid-cols-3 gap-1 text-xs">
            <label v-for="s in availableScopes" :key="s" class="flex items-center gap-1 rounded border px-2 py-1">
              <input
                type="checkbox"
                :checked="form.scopes?.includes(s)"
                :disabled="form.is_superuser"
                @change="toggleScope(s)"
              />
              <span class="font-mono">{{ s }}</span>
            </label>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <Switch v-model="form.is_superuser" />
          <label class="text-sm">Superuser</label>
        </div>
        <div class="flex justify-end gap-2">
          <Button variant="outline" @click="showCreate = false">Cancel</Button>
          <Button @click="submitCreate">Create</Button>
        </div>
      </div>
    </Dialog>
  </div>
</template>