<script setup lang="ts">
import type { FunctionRecord, Page } from '~/types/api'

const { t } = useI18n()

const selected = defineModel<string[]>({ required: true })
const api = useApi()
const auth = useAuth()
const search = ref('')
const page = ref(1)
const { data, status, error, refresh } = await useAsyncData('key-function-options', () => auth.can('functions.read')
  ? api<Page<FunctionRecord>>('/functions', { query: { page: page.value - 1, size: 50 } })
  : Promise.resolve(null), { server: false, watch: [page] })
const items = computed(() => (data.value?.items || [])
  .filter(item => `${item.name} ${item.description || ''}`.toLowerCase().includes(search.value.toLowerCase()))
  .map(item => ({ label: item.name, value: item.id, description: item.description || undefined })))
</script>

<template>
  <div class="space-y-3">
    <p class="text-sm text-muted">
      {{ t('counts.selection', { count: selected.length }) }}
    </p>
    <UInput
      v-model="search"
      :aria-label="t('ui.searchFunctionsOnThisPage')"
      :placeholder="t('ui.searchThisPage')"
      icon="i-lucide-search"
      class="w-full"
    />
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <p
      v-else-if="status === 'idle' || status === 'pending'"
      class="text-sm text-muted"
    >
      {{ t('ui.loadingFunctions') }}
    </p>
    <template v-else>
      <UCheckboxGroup
        v-model="selected"
        :items="items"
      />
      <p
        v-if="!items.length"
        class="text-sm text-muted"
      >
        {{ t('ui.noFunctionsAvailableOnThisPage') }}
      </p>
      <UPagination
        v-if="data && data.total > 50"
        v-model:page="page"
        :total="data.total"
        :items-per-page="50"
      />
    </template>
    <UButton
      v-if="selected.length"
      :label="t('ui.clearSelection')"
      color="neutral"
      variant="ghost"
      size="xs"
      @click="selected = []"
    />
    <p
      v-if="!auth.can('functions.read')"
      class="text-sm text-muted"
    >
      {{ t('ui.readingFunctionsPermissionIsRequiredToSelectFunctions') }}
    </p>
  </div>
</template>
