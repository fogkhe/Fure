<script setup lang="ts">
import type { RunRecord, FunctionRecord } from '~/types/api'

const { formatDate, formatDuration, errorMessage, translateDetail } = useFormatting()
const { t } = useI18n()

const route = useRoute()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const id = String(route.params.id)
const { data: record, error, status, refresh } = await useAsyncData(`run-${id}`, () => api<RunRecord>(`/runs/${encodeURIComponent(id)}`), { server: false })
useSeoMeta({ title: () => t('ui.run3', { value1: shortId(id) }) })
const names = useState<Record<string, string>>('function-names', () => ({}))
watch(() => record.value?.function_id, async (functionId) => {
  if (functionId && !names.value[functionId] && auth.can('functions.read')) {
    try {
      names.value[functionId] = (await api<FunctionRecord>(`/functions/${functionId}`)).name
    } catch { /* The history remains available without the function. */
    }
  }
}, { immediate: true })
const active = computed(() => record.value && ['pending', 'running'].includes(record.value.status))
const confirming = ref(false)
const cancelling = ref(false)
async function cancel() {
  if (cancelling.value)
    return
  cancelling.value = true
  try {
    await api(`/runs/${id}/cancel`, { method: 'POST' })
    confirming.value = false
    await refresh()
  } catch (problem) {
    toast.add({ title: t('ui.couldNotCancelRun'), description: errorMessage(problem), color: 'error' })
    await refresh()
  } finally {
    cancelling.value = false
  }
}
let timer: ReturnType<typeof setInterval>
onMounted(() => {
  timer = setInterval(() => {
    if (active.value && document.visibilityState === 'visible')
      refresh()
  }, 2000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <UContainer class="py-8 sm:py-12">
    <UBreadcrumb
      :items="[{ label: t('ui.runs'), to: '/runs' }, { label: `#${shortId(id)}` }]"
      class="mb-7"
    />
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <div
      v-if="record"
      class="space-y-7"
    >
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="text-3xl font-semibold tracking-tight text-highlighted">
              {{ t('ui.run') }} <span class="font-mono">#{{ shortId(id) }}</span>
            </h1><StatusBadge :status="record.status" />
          </div><NuxtLink
            v-if="auth.can('functions.read')"
            :to="`/functions/${record.function_id}`"
            class="mt-3 inline-flex items-center gap-2 text-primary hover:underline"
          ><UIcon name="i-lucide-square-function" />{{ names[record.function_id] || record.function_id }}</NuxtLink>
        </div><div class="flex gap-2">
          <UButton
            v-if="active && auth.canCancel(record)"
            :label="t('ui.cancelRun')"
            icon="i-lucide-square"
            color="error"
            variant="soft"
            @click="confirming = true"
          /><UButton
            icon="i-lucide-refresh-cw"
            :aria-label="t('ui.refreshRun')"
            color="neutral"
            variant="outline"
            :loading="status === 'pending'"
            @click="refresh()"
          />
        </div>
      </div>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <UCard>
          <p class="text-xs text-muted">
            {{ t('ui.duration') }}
          </p><p class="mt-2 text-lg font-semibold text-highlighted">
            {{ formatDuration(record.duration) }}
          </p>
        </UCard><UCard>
          <p class="text-xs text-muted">
            {{ t('ui.created') }}
          </p><p class="mt-2 text-sm text-highlighted">
            {{ formatDate(record.created_at) }}
          </p>
        </UCard><UCard>
          <p class="text-xs text-muted">
            {{ t('ui.started') }}
          </p><p class="mt-2 text-sm text-highlighted">
            {{ formatDate(record.started_at) }}
          </p>
        </UCard><UCard>
          <p class="text-xs text-muted">
            {{ t('ui.finished') }}
          </p><p class="mt-2 text-sm text-highlighted">
            {{ formatDate(record.finished_at) }}
          </p>
        </UCard>
      </div>
      <UAlert
        v-if="record.status === 'failed'"
        color="error"
        icon="i-lucide-circle-alert"
        :title="record.meta?.code || t('ui.executionError')"
        :description="record.meta?.message ? translateDetail(record.meta.message) : t('ui.noDetailsAvailable')"
      />
      <div class="grid items-start gap-6 lg:grid-cols-2">
        <JsonView
          :value="record.input"
          :title="t('ui.inputData')"
        /><JsonView
          :value="record.output"
          :title="t('ui.result')"
          :text="record.status === 'succeeded'"
        />
      </div>
      <JsonView
        v-if="record.meta && Object.keys(record.meta).length"
        :value="record.meta"
        :title="t('ui.metadata')"
      />
      <UCard>
        <dl class="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt class="text-muted">
              {{ t('ui.runId') }}
            </dt><dd class="mt-1 font-mono break-all">
              {{ record.id }}
            </dd>
          </div><div>
            <dt class="text-muted">
              {{ t('ui.implementationVersion') }}
            </dt><dd class="mt-1">
              <NuxtLink
                :to="`/functions/${record.function_id}?tab=revisions&revision_id=${record.revision_id}`"
                class="font-mono break-all text-primary hover:underline"
              >{{ record.revision_id }}</NuxtLink>
            </dd>
          </div>
        </dl><UButton
          class="mt-4"
          :to="`/runs?revision_id=${record.revision_id}`"
          :label="t('ui.allRunsOfThisVersion')"
          trailing-icon="i-lucide-arrow-right"
          variant="link"
        />
      </UCard>
    </div>
    <USkeleton
      v-else-if="status === 'idle' || status === 'pending'"
      class="h-96 rounded-xl"
    />
    <UModal
      v-model:open="confirming"
      :title="t('ui.cancelRun2')"
      :description="t('ui.executionWillBeInterruptedTheHistoryEntryWillBe')"
      :dismissible="!cancelling"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            :label="t('ui.back')"
            color="neutral"
            variant="ghost"
            :disabled="cancelling"
            @click="confirming = false"
          /><UButton
            :label="t('ui.cancelRun')"
            color="error"
            :loading="cancelling"
            @click="cancel"
          />
        </div>
      </template>
    </UModal>
  </UContainer>
</template>
