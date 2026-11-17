<script setup lang="ts">
import type { Page, FunctionRecord, RunRecord, RunStatus } from '~/types/api'

const props = defineProps<{
  functionId?: string
  revisionId?: string
}>()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const page = ref(1)
const filter = ref('all')
const autoRefresh = ref(true)
const cancelling = ref(false)
const target = ref<RunRecord | null>(null)
const cancelOpen = computed({ get: () => !!target.value, set: (open: boolean) => {
  if (!open)
    target.value = null
} })
const names = useState<Record<string, string>>('function-names', () => ({}))
const loadingNames = new Set<string>()
const statuses = [{ label: 'Все статусы', value: 'all' }, { label: 'В очереди', value: 'pending' }, { label: 'Выполняются', value: 'running' }, { label: 'Успешные', value: 'succeeded' }, { label: 'Ошибки', value: 'failed' }, { label: 'Отменённые', value: 'cancelled' }]
const query = computed(() => ({ page: page.value - 1, size: 15, function_id: props.functionId, revision_id: props.revisionId, status: filter.value === 'all' ? undefined : filter.value as RunStatus }))
const key = computed(() => `runs-${props.functionId || 'all'}-${props.revisionId || 'all'}`)
const { data, error, status, refresh } = await useAsyncData(key, () => api<Page<RunRecord>>('/runs', { query: query.value }), { server: false, watch: [query] })
watch([filter, () => props.functionId, () => props.revisionId], () => {
  page.value = 1
})
watch(data, async (value) => {
  const ids = auth.can('functions.read') ? [...new Set(value?.items.map(item => item.function_id) || [])].filter(id => !names.value[id] && !loadingNames.has(id)) : []
  await Promise.all(ids.map(async (id) => {
    loadingNames.add(id)
    try {
      names.value[id] = (await api<FunctionRecord>(`/functions/${id}`)).name
    } catch { /* The record remains readable by its identifier. */
    } finally {
      loadingNames.delete(id)
    }
  }))
}, { immediate: true })
let timer: ReturnType<typeof setInterval>
onMounted(() => {
  timer = setInterval(() => {
    if (autoRefresh.value && document.visibilityState === 'visible')
      refresh()
  }, 5000)
})
onBeforeUnmount(() => clearInterval(timer))
async function cancel() {
  if (!target.value || cancelling.value)
    return
  cancelling.value = true
  try {
    await api(`/runs/${target.value.id}/cancel`, { method: 'POST' })
    target.value = null
    await refresh()
    toast.add({ title: 'Запуск отменён', color: 'success' })
  } catch (problem) {
    toast.add({ title: 'Не удалось отменить запуск', description: errorMessage(problem), color: 'error' })
    await refresh()
  } finally {
    cancelling.value = false
  }
}
const columns = [{ accessorKey: 'id', header: 'Запуск' }, { accessorKey: 'function_id', header: 'Функция' }, { accessorKey: 'status', header: 'Статус' }, { accessorKey: 'duration', header: 'Длительность' }, { accessorKey: 'created_at', header: 'Создан' }, { id: 'actions' }]
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-muted">
        {{ data ? `${data.total} записей` : 'История запусков' }}
      </p><div class="flex flex-wrap items-center gap-3">
        <USwitch
          v-model="autoRefresh"
          label="Автообновление"
          size="sm"
        /><USelect
          v-model="filter"
          :items="statuses"
          aria-label="Статус запуска"
          class="w-44"
        /><UButton
          icon="i-lucide-refresh-cw"
          aria-label="Обновить историю"
          color="neutral"
          variant="outline"
          :loading="status === 'idle' || status === 'pending'"
          @click="refresh()"
        />
      </div>
    </div>
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <UTable
      :data="data?.items || []"
      :columns="columns"
      :loading="(status === 'idle' || status === 'pending') && !data"
      empty="Запусков пока нет"
      class="rounded-xl border border-default"
    >
      <template #id-cell="{ row }">
        <NuxtLink
          :to="`/runs/${row.original.id}`"
          class="font-mono text-primary hover:underline"
        >#{{ shortId(row.original.id) }}</NuxtLink>
      </template>
      <template #function_id-cell="{ row }">
        <NuxtLink
          v-if="auth.can('functions.read')"
          :to="`/functions/${row.original.function_id}`"
          class="font-medium hover:text-primary"
        >{{ names[row.original.function_id] || shortId(row.original.function_id) }}</NuxtLink>
        <span
          v-else
          class="font-mono text-xs"
        >{{ shortId(row.original.function_id) }}</span>
      </template>
      <template #status-cell="{ row }">
        <StatusBadge :status="row.original.status" />
      </template>
      <template #duration-cell="{ row }">
        {{ formatDuration(row.original.duration) }}
      </template>
      <template #created_at-cell="{ row }">
        <span class="text-muted">{{ formatDate(row.original.created_at) }}</span>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex justify-end gap-1">
          <UButton
            v-if="['pending', 'running'].includes(row.original.status) && auth.canCancel(row.original)"
            icon="i-lucide-square"
            aria-label="Отменить запуск"
            color="error"
            variant="ghost"
            size="xs"
            @click="target = row.original"
          /><UButton
            :to="`/runs/${row.original.id}`"
            icon="i-lucide-arrow-up-right"
            aria-label="Открыть запуск"
            color="neutral"
            variant="ghost"
            size="xs"
          />
        </div>
      </template>
    </UTable>
    <UPagination
      v-if="data && data.total > 15"
      v-model:page="page"
      :total="data.total"
      :items-per-page="15"
      class="justify-center"
    />
    <UModal
      v-model:open="cancelOpen"
      title="Отменить запуск?"
      description="Выполнение будет прервано. Входные данные и запись в истории сохранятся."
      :dismissible="!cancelling"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            label="Назад"
            color="neutral"
            variant="ghost"
            :disabled="cancelling"
            @click="target = null"
          /><UButton
            label="Отменить запуск"
            color="error"
            :loading="cancelling"
            @click="cancel"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>
