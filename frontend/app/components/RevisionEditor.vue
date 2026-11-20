<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { RevisionRecord } from '~/types/api'
import { outputSchemaIssue, readOutputSchema, writeOutputSchema } from '~/utils/outputSchema'
import type { OutputNode } from '~/utils/outputSchema'

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
  reasoningEndTags: [] as string[],
  toolFunctionIds: [] as string[],
  maxSteps: '8',
  maxToolCalls: '16',
  activate: true
})
const saving = ref(false)
const error = ref('')
const created = ref<RevisionRecord | null>(null)
const schemaDraft = ref<OutputNode>()
const schemaSwitchError = ref('')
const schemaMode = computed(() => schemaDraft.value ? 'fields' : 'json')
const schemaModes = computed(() => [{ label: t('inputEditor.fields'), value: 'fields' }, { label: 'JSON', value: 'json' }])
const schemaIssue = computed(() => schemaDraft.value && outputSchemaIssue(schemaDraft.value))
watch([schemaIssue, () => state.outputSchema], () => {
  schemaSwitchError.value = ''
})

function changeSchemaMode(mode: string) {
  if (mode === schemaMode.value) return
  schemaSwitchError.value = ''
  if (schemaDraft.value) {
    if (schemaIssue.value) {
      schemaSwitchError.value = t(`outputSchema.${schemaIssue.value}`)
      return
    }
    state.outputSchema = JSON.stringify(writeOutputSchema(schemaDraft.value), null, 2)
    schemaDraft.value = undefined
    return
  }
  try {
    const draft = readOutputSchema(parseObject(state.outputSchema))
    if (draft) schemaDraft.value = draft
    else schemaSwitchError.value = t('outputSchema.requiresJson')
  } catch (problem) {
    schemaSwitchError.value = errorMessage(problem)
  }
}

function getOutputSchema() {
  return schemaDraft.value ? writeOutputSchema(schemaDraft.value) : parseObject(state.outputSchema)
}
const pythonExample = `from pydantic import BaseModel


class Input(BaseModel):
    name: str


async def function(input: Input, vars: dict[str, object]) -> str:
    greeting = vars.get("greeting", "Hello")
    return f"{greeting}, {input.name}!"
`
watch(open, (value) => {
  if (!value) {
    state.apiKey = ''
    return
  }
  const initial = props.initial
  state.kind = initial?.implementation.type || 'python'
  state.code = initial?.implementation.type === 'python' ? initial.implementation.code : pythonExample
  state.template = initial?.implementation.type === 'jinja' ? initial.implementation.template : t('ui.greetNameWithSharedGreeting')
  state.outputSchema = initial ? JSON.stringify(initial.implementation.output_schema, null, 2) : '{}'
  schemaDraft.value = readOutputSchema(initial?.implementation.output_schema ?? {})
  schemaSwitchError.value = ''
  state.timeout = initial ? initial.runner_options.timeout == null ? '' : String(initial.runner_options.timeout) : '30'
  state.baseUrl = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.base_url : 'https://api.openai.com/v1'
  state.model = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.model : ''
  state.structuredOutputs = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options.structured_outputs : true
  state.reasoningEndTags = initial?.runner_options.type === 'openai_jinja' ? [...initial.runner_options.reasoning_end_tags] : []
  const options = initial?.runner_options.type === 'openai_jinja' ? initial.runner_options : null
  state.toolFunctionIds = [...(options?.tool_function_ids ?? [])]
  state.maxSteps = options ? String(options.max_steps ?? '') : '8'
  state.maxToolCalls = options ? String(options.max_tool_calls ?? '') : '16'
  state.apiKey = ''
  state.activate = true
  created.value = null
  error.value = ''
}, { immediate: true })
function optionalNumber(value: string | number | null | undefined) {
  return String(value ?? '').trim() === '' ? null : Number(value)
}
function validate(): FormError[] {
  if (created.value)
    return []
  const errors: FormError[] = []
  if (state.timeout !== '' && (!Number.isFinite(Number(state.timeout)) || Number(state.timeout) < 0))
    errors.push({ name: 'timeout', message: t('ui.enterANumberGreaterThanOrEqualToZero') })
  if (state.kind === 'python' && !state.code.trim())
    errors.push({ name: 'code', message: t('ui.addTheFunctionCode') })
  if (state.kind === 'jinja') {
    const steps = optionalNumber(state.maxSteps)
    const calls = optionalNumber(state.maxToolCalls)
    if (steps !== null && (!Number.isSafeInteger(steps) || steps < 1))
      errors.push({ name: 'maxSteps', message: t('agent.positiveInteger') })
    if (calls !== null && (!Number.isSafeInteger(calls) || calls < 0))
      errors.push({ name: 'maxToolCalls', message: t('agent.nonNegativeInteger') })
    if (!state.model.trim())
      errors.push({ name: 'model', message: t('ui.specifyAModel') })
    try {
      if (!['http:', 'https:'].includes(new URL(state.baseUrl).protocol))
        throw new Error()
    } catch {
      errors.push({ name: 'baseUrl', message: t('ui.enterAnHttpOrHttpsUrl') })
    }
    if (schemaIssue.value) {
      errors.push({ name: 'outputSchema', message: t(`outputSchema.${schemaIssue.value}`) })
    } else if (!schemaDraft.value) {
      try {
        parseObject(state.outputSchema)
      } catch (problem) {
        errors.push({ name: 'outputSchema', message: errorMessage(problem) })
      }
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
        : {
            function_id: props.functionId,
            implementation: { type: 'jinja', template: state.template, output_schema: getOutputSchema() },
            runner_options: {
              type: 'openai_jinja',
              timeout,
              base_url: state.baseUrl,
              model: state.model,
              api_key: state.apiKey || null,
              structured_outputs: state.structuredOutputs,
              reasoning_end_tags: state.reasoningEndTags.filter(tag => tag.trim()),
              tool_function_ids: state.toolFunctionIds,
              max_steps: optionalNumber(state.maxSteps),
              max_tool_calls: optionalNumber(state.maxToolCalls)
            }
          }
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
          <CodeEditor
            v-model="state.code"
            language="python"
            :rows="13"
            expand
            :disabled="saving || !!created"
            :label="t('ui.pythonCode')"
          />
        </UFormField>
        <template v-else>
          <UFormField
            :label="t('ui.jinjaTemplate')"
            name="template"
            :description="t('ui.templateVariablesAutomaticallyDefineTheInputSchema')"
          >
            <CodeEditor
              v-model="state.template"
              language="jinja"
              :rows="5"
              expand
              :disabled="saving || !!created"
              :label="t('ui.jinjaTemplate')"
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
            <div class="space-y-3">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="text-sm text-muted">{{ t('outputSchema.editor') }}</span>
                <UFormField>
                  <USelect
                    :model-value="schemaMode"
                    :items="schemaModes"
                    :aria-label="t('outputSchema.editor')"
                    :disabled="saving || !!created"
                    class="w-36"
                    @update:model-value="changeSchemaMode"
                  />
                </UFormField>
              </div>
              <p
                v-if="schemaSwitchError"
                role="alert"
                class="text-sm text-error"
              >
                {{ schemaSwitchError }}
              </p>
              <template v-if="schemaDraft">
                <p class="text-xs text-muted">
                  {{ t('outputSchema.strictHint') }}
                </p>
                <OutputSchemaFields
                  v-model="schemaDraft"
                  root
                  :disabled="saving || !!created"
                />
              </template>
              <CodeEditor
                v-else
                v-model="state.outputSchema"
                language="json"
                :label="t('ui.outputSchema')"
                :rows="8"
                :disabled="saving || !!created"
              />
            </div>
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
            :description="t('ui.reasoningEndTagsDescription')"
          >
            <div class="space-y-2">
              <div
                v-for="(_, index) in state.reasoningEndTags"
                :key="index"
                class="flex items-start gap-2"
              >
                <UFormField class="min-w-0 flex-1">
                  <UTextarea
                    v-model="state.reasoningEndTags[index]"
                    :aria-label="t('ui.reasoningEndTag', { index: index + 1 })"
                    :rows="1"
                    autoresize
                    placeholder="</think>"
                    :spellcheck="false"
                    :disabled="saving || !!created"
                    class="w-full"
                    :ui="{ base: 'font-mono' }"
                  />
                </UFormField>
                <UButton
                  type="button"
                  icon="i-lucide-trash-2"
                  color="neutral"
                  variant="ghost"
                  :aria-label="t('ui.removeReasoningEndTag', { index: index + 1 })"
                  :disabled="saving || !!created"
                  @click="state.reasoningEndTags.splice(index, 1)"
                />
              </div>
              <UButton
                type="button"
                :label="t('inputEditor.addItem')"
                color="neutral"
                variant="soft"
                size="xs"
                :disabled="saving || !!created"
                @click="state.reasoningEndTags.push('')"
              />
            </div>
          </UFormField>
          <UFormField
            :label="t('agent.tools')"
            :description="t('agent.toolsDescription')"
            name="toolFunctionIds"
          >
            <UCollapsible class="space-y-3">
              <UButton
                type="button"
                :label="t('agent.chooseTools', { count: state.toolFunctionIds.length })"
                trailing-icon="i-lucide-chevron-down"
                color="neutral"
                variant="outline"
              />
              <template #content>
                <FunctionSelect
                  v-model="state.toolFunctionIds"
                  :exclude="props.functionId"
                  :disabled="saving || !!created"
                />
              </template>
            </UCollapsible>
          </UFormField>
          <div
            v-if="state.toolFunctionIds.length"
            class="grid gap-4 sm:grid-cols-2"
          >
            <UFormField
              :label="t('agent.maxSteps')"
              :description="t('agent.stepLimitDescription')"
              name="maxSteps"
            >
              <UInput
                v-model="state.maxSteps"
                type="number"
                :min="1"
                step="1"
                :placeholder="t('agent.unlimited')"
                :disabled="saving || !!created"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('agent.maxToolCalls')"
              :description="t('agent.callLimitDescription')"
              name="maxToolCalls"
            >
              <UInput
                v-model="state.maxToolCalls"
                type="number"
                :min="0"
                step="1"
                :placeholder="t('agent.unlimited')"
                :disabled="saving || !!created"
                class="w-full"
              />
            </UFormField>
          </div>
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
