<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { RevisionRecord } from '~/types/api'

const props = defineProps<{
  functionId: string
  initial?: RevisionRecord | null
}>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{
  created: [revision: RevisionRecord]
  saved: []
}>()
const api = useApi()
const state = reactive({
  kind: 'python',
  code: '',
  template: '',
  timeout: '30',
  baseUrl: 'https://api.openai.com/v1',
  model: '',
  apiKey: '',
  outputSchema: '{}',
  activate: true
})
const saving = ref(false)
const error = ref('')
const created = ref<RevisionRecord | null>(null)
const pythonExample = 'from pydantic import BaseModel\n\n\nclass Input(BaseModel):\n    name: str\n\n\nasync def function(input: Input) -> str:\n    return f"Hello, {input.name}!"\n'
watch(open, (value) => {
  if (!value) {
    state.apiKey = ''
    return
  }
  const initial = props.initial
  state.kind = initial?.implementation.type || 'python'
  state.code = initial?.implementation.type === 'python' ? initial.implementation.code : pythonExample
  state.template = initial?.implementation.type === 'jinja' ? initial.implementation.template : 'Поприветствуй {{ name }} кратко и дружелюбно.'
  state.outputSchema = initial ? JSON.stringify(initial.implementation.output_schema, null, 2) : '{}'
  state.timeout = initial ? initial.runner_options.timeout == null ? '' : String(initial.runner_options.timeout) : '30'
  state.baseUrl = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.base_url : 'https://api.openai.com/v1'
  state.model = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.model : ''
  state.apiKey = ''
  state.activate = true
  created.value = null
  error.value = ''
}, { immediate: true })
function validate(): FormError[] {
  if (created.value)
    return []
  const errors: FormError[] = []
  if (state.timeout !== '' && (!Number.isFinite(Number(state.timeout)) || Number(state.timeout) < 0))
    errors.push({ name: 'timeout', message: 'Введите число не меньше нуля или оставьте поле пустым.' })
  if (state.kind === 'python' && !state.code.trim())
    errors.push({ name: 'code', message: 'Добавьте код функции.' })
  if (state.kind === 'jinja') {
    if (!state.model.trim())
      errors.push({ name: 'model', message: 'Укажите модель.' })
    try {
      if (!['http:', 'https:'].includes(new URL(state.baseUrl).protocol))
        throw new Error()
    } catch {
      errors.push({ name: 'baseUrl', message: 'Укажите HTTP или HTTPS адрес.' })
    }
    try {
      parseObject(state.outputSchema)
    } catch (problem) {
      errors.push({ name: 'outputSchema', message: problem instanceof Error ? problem.message : 'Некорректный JSON.' })
    }
  }
  return errors
}
async function save() {
  if (saving.value)
    return
  saving.value = true
  error.value = ''
  try {
    if (!created.value) {
      const timeout = state.timeout === '' ? null : Number(state.timeout)
      const body = state.kind === 'python'
        ? { function_id: props.functionId, implementation: { type: 'python', code: state.code }, runner_options: { type: 'inline_python', timeout } }
        : { function_id: props.functionId, implementation: { type: 'jinja', template: state.template, output_schema: parseObject(state.outputSchema) }, runner_options: { type: 'openai_jinja', timeout, base_url: state.baseUrl, model: state.model, api_key: state.apiKey || null } }
      created.value = await api<RevisionRecord>('/revisions', { method: 'POST', body })
      state.apiKey = ''
      emit('created', created.value)
    }
    if (state.activate)
      await api(`/functions/${props.functionId}`, { method: 'PATCH', body: { revision_id: created.value.id } })
    emit('saved')
    open.value = false
  } catch (problem) {
    error.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Новая версия реализации"
    description="Каждая версия сохраняет код и настройки запуска. История предыдущих версий останется доступна."
    :ui="{ content: 'sm:max-w-3xl' }"
    :dismissible="!saving"
    scrollable
  >
    <template #body>
      <UForm
        :state="state"
        :validate="validate"
        class="space-y-5"
        @submit="save"
      >
        <UAlert
          v-if="error"
          title="Не удалось завершить сохранение"
          :description="created ? `Версия уже создана. Повторите её выбор или снимите флажок «Сделать текущей». ${error}` : error"
          color="error"
          icon="i-lucide-circle-alert"
        />
        <UFormField
          label="Реализация"
          name="kind"
        >
          <USelect
            v-model="state.kind"
            :items="[{ label: 'Python · Inline', value: 'python', icon: 'i-simple-icons-python' }, { label: 'Jinja · OpenAI', value: 'jinja', icon: 'i-lucide-sparkles' }]"
            :disabled="saving || !!created"
            class="w-full sm:w-64"
          />
        </UFormField>
        <UFormField
          v-if="state.kind === 'python'"
          label="Код функции"
          name="code"
          required
          description="Асинхронная function(input: Input) с аннотациями аргумента и результата. Input — модель Pydantic или None."
        >
          <UTextarea
            v-model="state.code"
            :rows="13"
            :spellcheck="false"
            :disabled="saving || !!created"
            class="w-full"
            :ui="{ base: 'font-mono text-sm leading-6' }"
            aria-label="Python-код"
          />
        </UFormField>
        <template v-else>
          <UFormField
            label="Jinja-шаблон"
            name="template"
            description="Переменные шаблона автоматически образуют входную схему."
          >
            <UTextarea
              v-model="state.template"
              :rows="5"
              :spellcheck="false"
              :disabled="saving || !!created"
              class="w-full"
              :ui="{ base: 'font-mono text-sm' }"
              aria-label="Jinja-шаблон"
            />
          </UFormField>
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField
              label="Адрес API"
              name="baseUrl"
              required
            >
              <UInput
                v-model="state.baseUrl"
                placeholder="https://api.openai.com/v1"
                :disabled="saving || !!created"
                class="w-full"
              />
            </UFormField>
            <UFormField
              label="Модель"
              name="model"
              required
            >
              <UInput
                v-model="state.model"
                placeholder="Название модели"
                :disabled="saving || !!created"
                class="w-full"
              />
            </UFormField>
          </div>
          <UFormField
            label="API ключ"
            name="apiKey"
            hint="Необязательно"
            :description="initial?.runner_options.type === 'openai_jinja' ? 'Сохранённый ключ не возвращается API. Для новой версии введите его снова, если он необходим.' : 'Для локального сервера без авторизации оставьте поле пустым.'"
          >
            <UInput
              v-model="state.apiKey"
              type="password"
              autocomplete="off"
              :disabled="saving || !!created"
              class="w-full"
            />
          </UFormField>
          <UFormField
            label="Выходная схема"
            name="outputSchema"
            description="{} — текстовый ответ. Непустая схема передаётся провайдеру как Structured Outputs."
          >
            <UTextarea
              v-model="state.outputSchema"
              :rows="5"
              :spellcheck="false"
              :disabled="saving || !!created"
              class="w-full"
              :ui="{ base: 'font-mono text-sm' }"
            />
          </UFormField>
        </template>
        <UFormField
          label="Таймаут, секунды"
          name="timeout"
          description="Пустое поле — без ограничения времени."
        >
          <UInput
            v-model="state.timeout"
            type="number"
            min="0"
            step="any"
            :disabled="saving || !!created"
            class="w-44"
          />
        </UFormField>
        <USeparator />
        <UCheckbox
          v-model="state.activate"
          label="Сделать текущей версией"
          description="Новые запуски функции будут использовать эту реализацию."
          :disabled="saving"
        />
        <div class="flex justify-end gap-2">
          <UButton
            label="Закрыть"
            color="neutral"
            variant="ghost"
            :disabled="saving"
            @click="open = false"
          /><UButton
            type="submit"
            :label="created ? state.activate ? 'Выбрать текущей' : 'Готово' : 'Сохранить версию'"
            icon="i-lucide-git-branch"
            :loading="saving"
          />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
