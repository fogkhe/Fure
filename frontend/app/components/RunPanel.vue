<script setup lang="ts">
import type { FunctionRecord, JsonObject, RunResult } from '~/types/api'

const props = defineProps<{
  record: FunctionRecord
}>()
const api = useApi()
const initialInput = ref(JSON.stringify(sampleInput(props.record.input_schema), null, 2))
const input = ref(initialInput.value)
const running = ref(false)
const error = ref('')
const result = ref<RunResult | null>(null)
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
  let value: JsonObject | null
  try {
    value = JSON.parse(input.value)
    if (value !== null && (typeof value !== 'object' || Array.isArray(value)))
      throw new Error('Ожидается JSON-объект или null.')
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : 'Некорректный JSON.'
    return
  }
  running.value = true
  controller = new AbortController()
  try {
    const response = await api.raw<RunResult>(`/run/${encodeURIComponent(props.record.name)}`, { method: 'POST', body: { input: value }, signal: controller.signal })
    result.value = response._data ?? null
    runId.value = response.headers.get('x-run-id')
  } catch (problem) {
    if (!controller.signal.aborted) {
      error.value = errorMessage(problem)
      runId.value = (problem as {
        response?: Response
      }).response?.headers.get('x-run-id') ?? null
    }
  } finally {
    running.value = false
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
      title="Функция пока недоступна для запуска"
      description="Выберите текущую реализацию и включите функцию в настройках. Удалённую функцию сначала нужно восстановить."
    />
    <div class="grid items-start gap-6 lg:grid-cols-2">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <h2 class="font-semibold text-highlighted">
              Входные данные
            </h2><UButton
              label="Пример из схемы"
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
            description="Параметры передаются выбранной реализации функции."
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
              type="submit"
              label="Запустить"
              icon="i-lucide-play"
              :loading="running"
              :disabled="!record.runnable"
            /><UButton
              label="Входная схема"
              color="neutral"
              variant="ghost"
              size="sm"
              @click="showSchema = !showSchema"
            />
          </div>
          <JsonView
            v-if="showSchema"
            :value="record.input_schema"
            title="Входная схема"
          />
        </form>
        <template #footer>
          <p class="text-xs text-muted">
            Активные запуски можно отменить в <NuxtLink
              :to="`/runs?function_id=${record.id}`"
              class="text-primary hover:underline"
            >истории</NuxtLink>. Закрытие страницы не отменяет выполнение.
          </p>
        </template>
      </UCard>
      <div
        class="space-y-4"
        aria-live="polite"
      >
        <UAlert
          v-if="error"
          title="Не удалось выполнить запуск"
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
              {{ result.meta.total_tokens }} токенов
            </UBadge>
          </div>
          <JsonView
            :value="result.output"
            title="Результат"
            text
          />
          <JsonView
            v-if="Object.keys(result.meta).length"
            :value="result.meta"
            title="Метаданные"
          />
        </template>
        <UEmpty
          v-else-if="!error"
          :icon="running ? 'i-lucide-loader-circle' : 'i-lucide-terminal'"
          :title="running ? 'Функция выполняется' : 'Здесь появится результат'"
          :description="running ? 'Ожидаем ответ от выбранной реализации.' : 'Укажите входные данные и запустите функцию.'"
          class="min-h-72 border border-dashed border-default"
        />
        <UButton
          v-if="runId"
          :to="`/runs/${runId}`"
          label="Открыть запись запуска"
          icon="i-lucide-arrow-up-right"
          color="neutral"
          variant="link"
        />
      </div>
    </div>
  </div>
</template>
