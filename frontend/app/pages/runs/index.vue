<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const functionId = computed(() => typeof route.query.function_id === 'string' ? route.query.function_id : undefined)
const revisionId = computed(() => typeof route.query.revision_id === 'string' ? route.query.revision_id : undefined)
useSeoMeta({ title: () => t('ui.runHistory') })
</script>

<template>
  <UContainer class="py-8 sm:py-12">
    <div class="mb-8">
      <p class="mb-3 text-sm font-medium text-primary">
        {{ t('ui.observability') }}
      </p><h1 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
        {{ t('ui.runHistory') }}
      </h1><p class="mt-3 text-muted">
        {{ t('ui.inputDataResultsAndExecutionTimeForEveryCall') }}
      </p>
    </div>
    <UAlert
      v-if="functionId || revisionId"
      class="mb-5"
      color="neutral"
      icon="i-lucide-filter"
      :title="t('ui.historyIsFiltered')"
      :description="[functionId ? t('ui.function2', { value1: functionId }) : '', revisionId ? t('ui.version', { value1: revisionId }) : ''].filter(Boolean).join(' · ')"
      :actions="[{ label: t('ui.reset'), to: '/runs', variant: 'outline', color: 'neutral' }]"
    />
    <RunHistory
      :function-id="functionId"
      :revision-id="revisionId"
    />
  </UContainer>
</template>
