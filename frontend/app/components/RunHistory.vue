<script setup lang="ts">
import type { Page, FunctionRecord, RunRecord, RunStatus } from '~/types/api'

const { formatDate, formatDuration, errorMessage } = useFormatting()
const { t } = useI18n()

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
const statuses = computed(() => ([{ label: t('ui.allStatuses'), value: 'all' }, { label: t('ui.pending'), value: 'pending' }, { label: t('ui.running'), value: 'running' }, { label: t('ui.succeeded'), value: 'succeeded' }, { label: t('ui.failed'), value: 'failed' }, { label: t('ui.cancelled'), value: 'cancelled' }]))
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
    toast.add({ title: t('ui.runCancelled'), color: 'success' })
  } catch (problem) {
    toast.add({ title: t('ui.couldNotCancelRun'), description: errorMessage(problem), color: 'error' })
    await refresh()
  } finally {
    cancelling.value = false
  }
}
const columns = computed(() => ([{ accessorKey: 'id', header: t('ui.run') }, { accessorKey: 'function_id', header: t('ui.function') }, { accessorKey: 'status', header: t('ui.status') }, { accessorKey: 'duration', header: t('ui.duration') }, { accessorKey: 'created_at', header: t('ui.created') }, { id: 'actions' }]))
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-muted">
        {{ data ? t('counts.records', data.total) : t('ui.runHistory') }}
      </p><div class="flex flex-wrap items-center gap-3">
        <USwitch
          v-model="autoRefresh"
          :label="t('ui.autoRefresh')"
          size="sm"
        /><USelect
          v-model="filter"
          :items="statuses"
          :aria-label="t('ui.runStatus')"
          class="w-44"
        /><UButton
          icon="i-lucide-refresh-cw"
          :aria-label="t('ui.refreshHistory')"
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
      :empty="t('ui.noRunsYet')"
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
            :aria-label="t('ui.cancelRun')"
            color="error"
            variant="ghost"
            size="xs"
            @click="target = row.original"
          /><UButton
            :to="`/runs/${row.original.id}`"
            icon="i-lucide-arrow-up-right"
            :aria-label="t('ui.openRun')"
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
      :title="t('ui.cancelRun2')"
      :description="t('ui.executionWillBeInterruptedInputDataAndTheHistory')"
      :dismissible="!cancelling"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            :label="t('ui.back')"
            color="neutral"
            variant="ghost"
            :disabled="cancelling"
            @click="target = null"
          /><UButton
            :label="t('ui.cancelRun')"
            color="error"
            :loading="cancelling"
            @click="cancel"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>
