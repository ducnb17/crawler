<script setup lang="ts">
import { useI18n } from "vue-i18n";
import Card from "@/components/ui/Card.vue";

const { t } = useI18n();
</script>

<template>
  <Card class="p-10 text-center">
    <h2 class="text-2xl font-bold">{{ t("nav.proxies") }}</h2>
    <p class="mt-2 text-sm text-muted-foreground">
      Proxy pool + health-check sẽ được triển khai ở milestone M4.
    </p>
  </Card>
</template>