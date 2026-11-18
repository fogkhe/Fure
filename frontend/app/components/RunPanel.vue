<script setup lang="ts">
import type { FunctionRecord, JsonObject, RunRecord, RunResult } from '~/types/api'

const { formatDuration, errorMessage, translateDetail } = useFormatting()
const { t } = useI18n()

const props = defineProps<{
  record: FunctionRecord
}>()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const initialInput = ref(JSON.stringify(sampleInput(props.record.input_schema), null, 2))
const input = ref(initialInput.value)
const running = ref(false)
const cancelling = ref(false)
const cancelled = ref(false)
const cancelOpen = ref(false)
const canCancel = computed(() => auth.can('runs.read') && auth.can('runs.cancel'))
const error = ref('')
const result = shallowRef<RunResult | null>(null)
const runId = ref<string | null>(null)
const showSchema = ref(false)
let controller: AbortController | undefined
function fillExample() {
  initialInput.value = JSON.stringify(sampleInput(props.record.input_schema), null, 2)
  input.value = initialInput.value
}
watch(() => props.record.revision_id, () => {
  if (input.value === initialInput.value)
    fillExample()
})
async function execute() {
  if (running.value || !props.record.runnable)
    return
  error.value = ''
  result.value = null
  runId.value = null
  cancelled.value = false
  cancelling.value = false
  let value: JsonObject | null
  try {
    value = JSON.parse(input.value)
    if (value !== null && (typeof value !== 'object' || Array.isArray(value)))
      throw new Error(t('ui.expectedAJsonObjectOrNull'))
  } catch (problem) {
    error.value = errorMessage(problem)
    return
  }
  running.value = true
  controller = new AbortController()
  const signal = controller.signal
  try {
    const endpoint = `/functions/${props.record.id}/run`
    if (auth.can('runs.read')) {
      let run = await api<RunRecord>(endpoint, { method: 'POST', query: { wait: false }, body: { input: value }, signal })
      runId.value = run.id
      while (run.status === 'pending' || run.status === 'running') {
        run = await api<RunRecord>(`/runs/${run.id}`, { signal })
        if (run.status === 'pending' || run.status === 'running') {
          await new Promise(resolve => setTimeout(resolve, 500))
          signal.throwIfAborted()
        }
      }
      if (run.status === 'succeeded')
        result.value = { output: run.output, meta: run.meta ?? {}, duration: run.duration ?? 0 }
      else if (run.status === 'cancelled')
        cancelled.value = true
      else
        error.value = run.meta?.message ? translateDetail(run.meta.message) : t('ui.couldNotExecuteTheFunction')
    } else {
      const response = await api.raw<RunResult>(endpoint, { method: 'POST', body: { input: value }, signal })
      result.value = response._data ?? null
      runId.value = response.headers.get('x-run-id')
    }
  } catch (problem) {
    if (!signal.aborted) {
      error.value = errorMessage(problem)
      runId.value = (problem as {
        response?: Response
      }).response?.headers.get('x-run-id') ?? runId.value
    }
  } finally {
    running.value = false
    cancelling.value = false
    cancelOpen.value = false
  }
}
async function cancel() {
  const target = runId.value
  if (!target || !running.value || cancelling.value)
    return
  cancelling.value = true
  try {
    await api(`/runs/${target}/cancel`, { method: 'POST' })
    if (runId.value === target)
      cancelOpen.value = false
  } catch (problem) {
    if (runId.value === target) {
      cancelling.value = false
      toast.add({ title: t('ui.couldNotCancelRun'), description: errorMessage(problem), color: 'error' })
    }
  }
}
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="space-y-5">
    <UAlert
      v-if="!record.runnable"
      color="warning"
      icon="i-lucide-circle-alert"
      :title="t('ui.thisFunctionIsNotReadyToRun')"
      :description="t('ui.selectACurrentImplementationAndEnableTheFunctionIn')"
    />
    <div class="grid items-start gap-6 lg:grid-cols-2">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <h2 class="font-semibold text-highlighted">
              {{ t('ui.inputData') }}
            </h2><UButton
              :label="t('ui.exampleFromSchema')"
              icon="i-lucide-braces"
              size="xs"
              color="neutral"
              variant="ghost"
              :disabled="running"
              @click="fillExample"
            />
          </div>
        </template>
        <form
          class="space-y-4"
          @submit.prevent="execute"
        >
          <UFormField
            label="Input · JSON"
            :description="t('ui.parametersArePassedToTheSelectedImplementation')"
          >
            <UTextarea
              v-model="input"
              :rows="12"
              class="w-full"
              :ui="{ base: 'font-mono text-sm' }"
              :disabled="running"
              spellcheck="false"
            />
          </UFormField>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <UButton
              v-if="running && canCancel"
              type="button"
              :label="t('ui.cancel2')"
              icon="i-lucide-square"
              color="error"
              :loading="cancelling"
              :disabled="!runId"
              @click="cancelOpen = true"
            />
            <UButton
              v-else
              type="submit"
              :label="t('ui.run2')"
              icon="i-lucide-play"
              :loading="running"
              :disabled="!record.runnable || (!record.public && !auth.can('functions.run'))"
            /><UButton
              :label="t('ui.inputSchema')"
              color="neutral"
              variant="ghost"
              size="sm"
              @click="showSchema = !showSchema"
            />
          </div>
          <JsonView
            v-if="showSchema"
            :value="record.input_schema"
            :title="t('ui.inputSchema')"
          />
        </form>
        <template #footer>
          <p
            v-if="auth.can('runs.read')"
            class="text-xs text-muted"
          >
            <NuxtLink
              :to="`/runs?function_id=${record.id}`"
              class="text-primary hover:underline"
            >{{ t('ui.runHistory') }}</NuxtLink>{{ t('ui.closingThisPageDoesNotCancelExecution') }}
          </p>
        </template>
      </UCard>
      <div
        class="space-y-4"
        aria-live="polite"
      >
        <UAlert
          v-if="cancelled"
          :title="t('ui.runCancelled')"
          :description="t('ui.executionWasInterruptedTheHistoryEntryHasBeenPreserved')"
          icon="i-lucide-ban"
          color="neutral"
        />
        <UAlert
          v-if="error"
          :title="t('ui.couldNotExecuteTheFunction2')"
          :description="error"
          icon="i-lucide-circle-alert"
          color="error"
        />
        <template v-if="result">
          <div class="flex flex-wrap items-center gap-3">
            <StatusBadge status="succeeded" /><span class="text-sm text-muted">{{ formatDuration(result.duration) }}</span><UBadge
              v-if="result.meta.total_tokens != null"
              color="neutral"
              variant="subtle"
            >
              {{ t('counts.tokens', result.meta.total_tokens) }}
            </UBadge>
          </div>
          <JsonView
            :value="result.output"
            :title="t('ui.result')"
            text
          />
          <JsonView
            v-if="Object.keys(result.meta).length"
            :value="result.meta"
            :title="t('ui.metadata')"
          />
        </template>
        <UEmpty
          v-else-if="!error && !cancelled"
          :icon="running ? 'i-lucide-loader-circle' : 'i-lucide-terminal'"
          :title="running ? t('ui.functionIsRunning') : t('ui.theResultWillAppearHere')"
          :description="running ? t('ui.waitingForAResponseFromTheSelectedImplementation') : t('ui.enterInputDataAndRunTheFunction')"
          class="min-h-72 border border-dashed border-default"
        />
        <UButton
          v-if="runId && auth.can('runs.read')"
          :to="`/runs/${runId}`"
          :label="t('ui.openRunRecord')"
          icon="i-lucide-arrow-up-right"
          color="neutral"
          variant="link"
        />
      </div>
    </div>
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
            @click="cancelOpen = false"
          />
          <UButton
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
