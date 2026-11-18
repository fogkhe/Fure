<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { RevisionRecord } from '~/types/api'

const { errorMessage } = useFormatting()
const { t } = useI18n()

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
  structuredOutputs: true,
  reasoningEndTags: '',
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
  state.template = initial?.implementation.type === 'jinja' ? initial.implementation.template : t('ui.greetNameBrieflyAndWarmly')
  state.outputSchema = initial ? JSON.stringify(initial.implementation.output_schema, null, 2) : '{}'
  state.timeout = initial ? initial.runner_options.timeout == null ? '' : String(initial.runner_options.timeout) : '30'
  state.baseUrl = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.base_url : 'https://api.openai.com/v1'
  state.model = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.model : ''
  state.structuredOutputs = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.structured_outputs : true
  state.reasoningEndTags = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.reasoning_end_tags.join('\n') : ''
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
    errors.push({ name: 'timeout', message: t('ui.enterANumberGreaterThanOrEqualToZero') })
  if (state.kind === 'python' && !state.code.trim())
    errors.push({ name: 'code', message: t('ui.addTheFunctionCode') })
  if (state.kind === 'jinja') {
    if (!state.model.trim())
      errors.push({ name: 'model', message: t('ui.specifyAModel') })
    try {
      if (!['http:', 'https:'].includes(new URL(state.baseUrl).protocol))
        throw new Error()
    } catch {
      errors.push({ name: 'baseUrl', message: t('ui.enterAnHttpOrHttpsUrl') })
    }
    try {
      parseObject(state.outputSchema)
    } catch (problem) {
      errors.push({ name: 'outputSchema', message: errorMessage(problem) })
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
        : { function_id: props.functionId, implementation: { type: 'jinja', template: state.template, output_schema: parseObject(state.outputSchema) }, runner_options: { type: 'openai_jinja', timeout, base_url: state.baseUrl, model: state.model, api_key: state.apiKey || null, structured_outputs: state.structuredOutputs, reasoning_end_tags: state.reasoningEndTags.split('\n').filter(tag => tag.trim()) } }
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
    :title="t('ui.newImplementationVersion')"
    :description="t('ui.eachVersionStoresTheCodeAndExecutionSettingsPrevious')"
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
          :title="t('ui.couldNotFinishSaving')"
          :description="created ? t('ui.theVersionHasAlreadyBeenCreatedTrySelectingIt', { value1: error }) : error"
          color="error"
          icon="i-lucide-circle-alert"
        />
        <UFormField
          :label="t('ui.implementation')"
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
          :label="t('ui.functionCode')"
          name="code"
          required
          :description="t('ui.anAsyncFunctionInputInputWithArgumentAndReturn')"
        >
          <UTextarea
            v-model="state.code"
            :rows="13"
            :spellcheck="false"
            :disabled="saving || !!created"
            class="w-full"
            :ui="{ base: 'font-mono text-sm leading-6' }"
            :aria-label="t('ui.pythonCode')"
          />
        </UFormField>
        <template v-else>
          <UFormField
            :label="t('ui.jinjaTemplate')"
            name="template"
            :description="t('ui.templateVariablesAutomaticallyDefineTheInputSchema')"
          >
            <UTextarea
              v-model="state.template"
              :rows="5"
              :spellcheck="false"
              :disabled="saving || !!created"
              class="w-full"
              :ui="{ base: 'font-mono text-sm' }"
              :aria-label="t('ui.jinjaTemplate')"
            />
          </UFormField>
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField
              :label="t('ui.apiUrl')"
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
              :label="t('ui.model')"
              name="model"
              required
            >
              <UInput
                v-model="state.model"
                :placeholder="t('ui.modelName')"
                :disabled="saving || !!created"
                class="w-full"
              />
            </UFormField>
          </div>
          <UFormField
            :label="t('ui.apiKey')"
            name="apiKey"
            :hint="t('ui.optional')"
            :description="initial?.runner_options.type === 'openai_jinja' ? t('ui.theApiDoesNotReturnStoredKeysEnterThe') : t('ui.leaveEmptyForALocalServerWithoutAuthentication')"
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
            :label="t('ui.outputSchema')"
            name="outputSchema"
            :description="t('ui.returnsATextResponseANonEmptySchemaDefines')"
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
          <USwitch
            v-model="state.structuredOutputs"
            label="Structured Outputs"
            :description="t('ui.disableIfYourProviderDoesNotSupportThisMode')"
            :disabled="saving || !!created"
          />
          <UFormField
            v-if="!state.structuredOutputs"
            :label="t('ui.reasoningEndTags')"
            name="reasoningEndTags"
            :description="t('ui.onePerLineForExampleThinkAnEmptyList')"
          >
            <UTextarea
              v-model="state.reasoningEndTags"
              :rows="3"
              :disabled="saving || !!created"
              :spellcheck="false"
              class="w-full"
            />
          </UFormField>
        </template>
        <UFormField
          :label="t('ui.timeoutSeconds')"
          name="timeout"
          :description="t('ui.leaveEmptyForNoTimeLimit')"
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
          :label="t('ui.setAsCurrentVersion')"
          :description="t('ui.newRunsWillUseThisImplementation')"
          :disabled="saving"
        />
        <div class="flex justify-end gap-2">
          <UButton
            :label="t('ui.close')"
            color="neutral"
            variant="ghost"
            :disabled="saving"
            @click="open = false"
          /><UButton
            type="submit"
            :label="created ? state.activate ? t('ui.setAsCurrent') : t('ui.done') : t('ui.saveVersion')"
            icon="i-lucide-git-branch"
            :loading="saving"
          />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
