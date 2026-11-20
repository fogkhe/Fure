<script setup lang="ts">
import type { FunctionRecord, Page } from '~/types/api'

const { t } = useI18n()

const selected = defineModel<string[]>({ required: true })
const props = defineProps<{ exclude?: string, disabled?: boolean }>()
const api = useApi()
const auth = useAuth()
const search = ref('')
const page = ref(1)
const { data, status, error, refresh } = await useAsyncData(`function-options-${useId()}`, () => auth.can('functions.read')
  ? api<Page<FunctionRecord>>('/functions', { query: { page: page.value - 1, size: 50 } })
  : Promise.resolve(null), { server: false, watch: [page] })
const items = computed(() => (data.value?.items || [])
  .filter(item => item.id !== props.exclude && `${item.name} ${item.description || ''}`.toLowerCase().includes(search.value.toLowerCase()))
  .map(item => ({ label: item.name, value: item.id, description: item.description || undefined })))
const names = useState<Record<string, string>>('function-names', () => ({}))
watch(data, (result) => {
  for (const item of result?.items || []) names.value[item.id] = item.name
}, { immediate: true })
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
      :disabled="disabled"
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
        :disabled="disabled"
        class="max-h-52 overflow-auto"
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
    <div
      v-if="exclude && selected.length"
      class="flex flex-wrap gap-1.5"
    >
      <UButton
        v-for="id in selected"
        :key="id"
        color="neutral"
        variant="soft"
        size="xs"
        trailing-icon="i-lucide-x"
        :label="names[id] || shortId(id)"
        :aria-label="t('agent.removeTool', { name: names[id] || shortId(id) })"
        :disabled="disabled"
        @click="selected = selected.filter(item => item !== id)"
      />
    </div>
    <UButton
      v-if="selected.length"
      :label="t('ui.clearSelection')"
      color="neutral"
      variant="ghost"
      size="xs"
      :disabled="disabled"
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
