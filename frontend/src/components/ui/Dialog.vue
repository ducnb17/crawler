<script setup lang="ts">
import { DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTrigger } from "radix-vue";
import { X } from "lucide-vue-next";
import { cn } from "@/lib/utils";
import { onMounted } from "vue";

const props = withDefaults(defineProps<{
  open?: boolean;
  title?: string;
  size?: "sm" | "md" | "lg" | "xl";
  closable?: boolean;
}>(), { size: "md", closable: true });

const emit = defineEmits<{ "update:open": [v: boolean]; close: [] }>();

function setOpen(v: boolean) {
  emit("update:open", v);
  if (!v) emit("close");
}
const sizeClass = ({ sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" })[props.size];

onMounted(() => {});
</script>

<template>
  <DialogRoot :open="open" @update:open="setOpen">
    <DialogTrigger v-if="$slots.trigger" as-child>
      <slot name="trigger" />
    </DialogTrigger>
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-fade-in" />
      <DialogContent
        :class="cn('fixed left-1/2 top-1/2 z-50 w-full -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-card p-6 shadow-2xl', sizeClass)"
      >
        <div v-if="title || closable" class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold leading-none">
            {{ title }}
          </h2>
          <button v-if="closable" class="rounded-md p-1 text-muted-foreground hover:bg-accent" @click="setOpen(false)">
            <X class="h-4 w-4" />
          </button>
        </div>
        <div class="max-h-[70vh] overflow-y-auto">
          <slot />
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>