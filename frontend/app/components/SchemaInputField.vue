<script setup lang="ts">
import type { JsonObject, JsonValue } from '~/types/api'
import { fieldSample, inputSchema, invalidInputFields, isJsonObject, parseInputJson } from '~/utils/inputSchema'

const props = withDefaults(defineProps<{
  schema: JsonObject
  root: JsonObject
  label: string
  required?: boolean
  disabled?: boolean
  depth?: number
}>(), { depth: 0 })
// A Boolean runtime prop would coerce empty strings to true in recursive fields.
const value = defineModel<JsonValue | undefined>({ type: null })
const { t } = useI18n()
const node = computed(() => inputSchema(props.schema, props.root))
const title = computed(() => typeof node.value.title === 'string' ? `${node.value.title} (${props.label})` : props.label)
const description = computed(() => typeof node.value.description === 'string' ? node.value.description : undefined)
const nullable = computed(() => node.value.nullable === true || node.value.type === 'null')
const properties = computed(() => isJsonObject(node.value.properties) ? node.value.properties : {})
const fields = computed(() => Object.entries(properties.value).map(([name, schema]) => ({ name, schema: isJsonObject(schema) ? schema : {} })))
const requiredFields = computed(() => Array.isArray(node.value.required) ? node.value.required : [])
const kind = computed(() => {
  const schema = node.value
  if (props.depth > 12 || schema.allOf || schema.anyOf || schema.oneOf || schema.not || schema.if || 'const' in schema) return 'json'
  if (Array.isArray(schema.enum)) return 'enum'
  if ((schema.type === 'object' || schema.properties) && isJsonObject(value.value) && fields.value.length
    && Object.keys(value.value).every(key => Object.hasOwn(properties.value, key))) return 'object'
  if (schema.type === 'array' && Array.isArray(value.value) && isJsonObject(schema.items) && !schema.prefixItems) return 'array'
  if (schema.type === 'string' && typeof value.value === 'string') return 'string'
  if ((schema.type === 'number' || schema.type === 'integer') && typeof value.value === 'number') return 'number'
  if (schema.type === 'boolean' && typeof value.value === 'boolean') return 'boolean'
  return 'json'
})
const enumItems = computed(() => Array.isArray(node.value.enum) ? node.value.enum.map((item, index) => ({ label: typeof item === 'string' ? item : JSON.stringify(item), value: String(index) })) : [])
const enumIndex = computed(() => enumItems.value.find(item => JSON.stringify((node.value.enum as JsonValue[])[Number(item.value)]) === JSON.stringify(value.value))?.value)
// The request itself and fields with a single declared type still use their schema.
const textOrJson = computed(() => props.depth > 0 && (node.value.type === undefined
  || (Array.isArray(node.value.type) && node.value.type.includes('string'))))
const draft = ref('')
const invalidDraft = ref(false)
const invalidFields = inject(invalidInputFields)
const fieldKey = Symbol()
const showDraftError = computed(() => invalidDraft.value && kind.value === 'json'
  && value.value !== undefined && !(nullable.value && value.value === null))
watch(showDraftError, (invalid) => {
  if (invalid) invalidFields?.add(fieldKey)
  else invalidFields?.delete(fieldKey)
}, { flush: 'sync' })
onScopeDispose(() => invalidFields?.delete(fieldKey))

const draftLanguage = computed(() => {
  const source = draft.value.trim()
  if (!textOrJson.value || !source || /^[{["]|^(?:true|false|null|[-\d][\d.eE+-]*)$/.test(source)) return 'json'
  return 'text'
})

function parseDraft(source: string): JsonValue {
  try {
    return parseInputJson(source)
  } catch (problem) {
    if (textOrJson.value) return source
    throw problem
  }
}

watch([value, textOrJson], ([next, flexible], [previous, wasFlexible]) => {
  if (flexible === wasFlexible && JSON.stringify(next) === JSON.stringify(previous)) return
  try {
    if (JSON.stringify(parseDraft(draft.value)) === JSON.stringify(next)) return
  } catch { /* External edits replace an invalid draft. */ }
  // Quote strings that would otherwise be read as a different JSON value.
  draft.value = flexible && typeof next === 'string' && parseDraft(next) === next
    ? next
    : JSON.stringify(next, null, 2) ?? ''
  invalidDraft.value = false
}, { immediate: true, deep: true })
function editDraft(source: string) {
  draft.value = source
  try {
    value.value = parseDraft(source)
    invalidDraft.value = false
  } catch {
    invalidDraft.value = true
  }
}
function setProperty(name: string, next: JsonValue | undefined) {
  const entries = Object.entries(isJsonObject(value.value) ? value.value : {}).filter(([key]) => key !== name)
  if (next !== undefined) entries.push([name, next])
  value.value = Object.fromEntries(entries)
}
function setItem(index: number, next: JsonValue | undefined) {
  if (Array.isArray(value.value)) value.value = value.value.map((item, i) => i === index ? next ?? null : item)
}
function numberInput(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.value !== '' && Number.isFinite(input.valueAsNumber)) value.value = input.valueAsNumber
}
function nonNullSample(): JsonValue {
  const schema = { ...node.value }
  if (schema.default === null) delete schema.default
  if (Array.isArray(schema.enum)) schema.enum = schema.enum.filter(item => item !== null)
  return fieldSample(schema, props.root)
}
const controlClass = 'w-full rounded-md border border-default bg-default px-3 py-2 text-sm outline-none focus:border-primary disabled:opacity-50'
</script>

<template>
  <UFormField
    :label="title"
    :description="description"
    :required="required"
    :error="showDraftError ? t('inputEditor.invalidJson') : undefined"
  >
    <div class="space-y-3">
      <UButton
        v-if="required && value === undefined"
        type="button"
        size="xs"
        :label="t('inputEditor.setValue')"
        :disabled="disabled"
        @click="value = fieldSample(node, root)"
      />
      <div
        v-if="!required || nullable"
        class="flex flex-wrap gap-4"
      >
        <UCheckbox
          v-if="!required"
          :model-value="value !== undefined"
          :label="t('inputEditor.include')"
          :aria-label="t('inputEditor.includeField', { name: label })"
          :disabled="disabled"
          @update:model-value="value = $event ? fieldSample(node, root) : undefined"
        />
        <UCheckbox
          v-if="nullable && value !== undefined"
          :model-value="value === null"
          :label="t('inputEditor.null')"
          :aria-label="t('inputEditor.nullField', { name: label })"
          :disabled="disabled || node.type === 'null'"
          @update:model-value="value = $event ? null : nonNullSample()"
        />
      </div>
      <template v-if="value !== undefined && !(nullable && value === null)">
        <div
          v-if="kind === 'object'"
          class="space-y-4 border-l border-default pl-4"
        >
          <SchemaInputField
            v-for="field in fields"
            :key="field.name"
            :schema="field.schema"
            :root="root"
            :label="field.name"
            :model-value="isJsonObject(value) ? value[field.name] : undefined"
            :required="requiredFields.includes(field.name)"
            :disabled="disabled"
            :depth="depth + 1"
            @update:model-value="setProperty(field.name, $event)"
          />
        </div>
        <div
          v-else-if="kind === 'array'"
          class="space-y-4 border-l border-default pl-4"
        >
          <div
            v-for="(item, index) in (value as JsonValue[])"
            :key="index"
            class="space-y-2"
          >
            <SchemaInputField
              :schema="node.items as JsonObject"
              :root="root"
              :label="`${label}[${index}]`"
              :model-value="item"
              required
              :disabled="disabled"
              :depth="depth + 1"
              @update:model-value="setItem(index, $event)"
            />
            <UButton
              type="button"
              size="xs"
              color="neutral"
              variant="ghost"
              :label="t('inputEditor.remove')"
              :aria-label="t('inputEditor.removeItem', { name: `${label}[${index}]` })"
              :disabled="disabled"
              @click="value = (value as JsonValue[]).filter((_, i) => i !== index)"
            />
          </div>
          <UButton
            type="button"
            size="xs"
            color="neutral"
            variant="soft"
            :label="t('inputEditor.addItem')"
            :disabled="disabled"
            @click="value = [...(value as JsonValue[]), fieldSample(node.items as JsonObject, root)]"
          />
        </div>
        <USelect
          v-else-if="kind === 'enum'"
          :model-value="enumIndex"
          :items="enumItems"
          :aria-label="title"
          class="w-full"
          :disabled="disabled"
          @update:model-value="value = (node.enum as JsonValue[])[Number($event)]"
        />
        <UTextarea
          v-else-if="kind === 'string'"
          :model-value="value as string"
          :aria-label="title"
          :rows="3"
          class="w-full"
          :disabled="disabled"
          :minlength="typeof node.minLength === 'number' ? node.minLength : undefined"
          :maxlength="typeof node.maxLength === 'number' ? node.maxLength : undefined"
          @update:model-value="value = $event"
        />
        <input
          v-else-if="kind === 'number'"
          type="number"
          :value="value"
          :aria-label="title"
          :class="controlClass"
          :step="node.type === 'integer' ? 1 : 'any'"
          :min="typeof node.minimum === 'number' ? node.minimum : undefined"
          :max="typeof node.maximum === 'number' ? node.maximum : undefined"
          :disabled="disabled"
          required
          @input="numberInput"
        >
        <USwitch
          v-else-if="kind === 'boolean'"
          :model-value="value as boolean"
          :aria-label="title"
          :disabled="disabled"
          @update:model-value="value = $event"
        />
        <div
          v-else
          class="space-y-2"
        >
          <p class="text-xs text-muted">
            {{ t(textOrJson ? 'inputEditor.textOrJson' : 'inputEditor.jsonFallback') }}
          </p>
          <CodeEditor
            :model-value="draft"
            :language="draftLanguage"
            :label="title"
            :rows="5"
            :disabled="disabled"
            :invalid="showDraftError"
            @update:model-value="editDraft"
          />
        </div>
      </template>
    </div>
  </UFormField>
</template>
