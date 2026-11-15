<script setup lang="ts">
const route = useRoute()
const functionId = computed(() => typeof route.query.function_id === 'string' ? route.query.function_id : undefined)
const revisionId = computed(() => typeof route.query.revision_id === 'string' ? route.query.revision_id : undefined)
useSeoMeta({ title: 'История запусков' })
</script>

<template>
  <UContainer class="py-8 sm:py-12">
    <div class="mb-8">
      <p class="mb-3 text-sm font-medium text-primary">
        Наблюдаемость
      </p><h1 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
        История запусков
      </h1><p class="mt-3 text-muted">
        Входные данные, результаты и время выполнения каждого вызова.
      </p>
    </div>
    <UAlert
      v-if="functionId || revisionId"
      class="mb-5"
      color="neutral"
      icon="i-lucide-filter"
      title="История отфильтрована"
      :description="[functionId ? `Функция: ${functionId}` : '', revisionId ? `Версия: ${revisionId}` : ''].filter(Boolean).join(' · ')"
      :actions="[{ label: 'Сбросить', to: '/runs', variant: 'outline', color: 'neutral' }]"
    />
    <RunHistory
      :function-id="functionId"
      :revision-id="revisionId"
    />
  </UContainer>
</template>
