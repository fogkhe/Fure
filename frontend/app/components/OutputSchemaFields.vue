<script setup lang="ts">
import type { OutputNode, OutputType } from '~/utils/outputSchema'
import { newOutputNode, outputTypes } from '~/utils/outputSchema'

defineProps<{ root?: boolean, disabled?: boolean }>()
const node = defineModel<OutputNode>({ required: true })
const { t } = useI18n()
const types = computed(() => outputTypes.map(type => ({ label: t(`outputSchema.types.${type}`), value: type })))

function changeType(type: OutputType) {
  const { description, nullable } = node.value
  node.value = { ...newOutputNode(type), description, nullable }
}

function addField() {
  const fields = node.value.fields
  let number = fields.length + 1
  while (fields.some(field => field.name === `field_${number}`)) number++
  const id = Math.max(-1, ...fields.map(field => field.id)) + 1
  fields.push({ id, name: `field_${number}`, node: newOutputNode('string') })
}
</script>

<template>
  <div class="min-w-0 space-y-3">
    <div
      v-if="!root"
      class="flex flex-wrap items-end gap-3"
    >
      <UFormField :label="t('outputSchema.type')">
        <USelect
          :model-value="node.type"
          :items="types"
          :disabled="disabled"
          class="min-w-32"
          @update:model-value="changeType"
        />
      </UFormField>
      <UFormField class="pb-2">
        <UCheckbox
          v-model="node.nullable"
          :label="t('outputSchema.allowNull')"
          :aria-label="t('outputSchema.allowNull')"
          :disabled="disabled"
        />
      </UFormField>
    </div>
    <UFormField :label="t('ui.description')">
      <UInput
        v-model="node.description"
        :disabled="disabled"
        class="w-full"
      />
    </UFormField>
    <UFormField
      v-if="node.type === 'string'"
      :label="t('outputSchema.allowedValues')"
    >
      <UInputTags
        :model-value="node.choices"
        :placeholder="t('outputSchema.addValue')"
        :disabled="disabled"
        class="w-full"
        @update:model-value="node.choices = [...new Set($event)]"
      />
    </UFormField>
    <template v-if="node.type === 'object'">
      <fieldset
        v-for="(field, index) in node.fields"
        :key="field.id"
        class="min-w-0 space-y-3 rounded-lg border border-default px-3 pb-3"
      >
        <legend class="px-1 text-xs font-medium text-muted">
          {{ t('outputSchema.field', { index: index + 1 }) }}
        </legend>
        <div class="flex items-end gap-2">
          <UFormField
            :label="t('outputSchema.name')"
            required
            class="min-w-0 flex-1"
          >
            <UInput
              v-model="field.name"
              :disabled="disabled"
              class="w-full"
            />
          </UFormField>
          <UButton
            type="button"
            icon="i-lucide-trash-2"
            color="neutral"
            variant="ghost"
            :aria-label="t('outputSchema.removeField', { index: index + 1 })"
            :disabled="disabled"
            @click="node.fields.splice(index, 1)"
          />
        </div>
        <OutputSchemaFields
          v-model="field.node"
          :disabled="disabled"
        />
      </fieldset>
      <UButton
        type="button"
        :label="t('outputSchema.addField')"
        icon="i-lucide-plus"
        size="sm"
        color="neutral"
        variant="soft"
        :disabled="disabled"
        @click="addField"
      />
    </template>
    <fieldset
      v-else-if="node.items"
      class="min-w-0 rounded-lg border border-default px-3 pb-3"
    >
      <legend class="px-1 text-xs font-medium text-muted">
        {{ t('outputSchema.arrayItem') }}
      </legend>
      <OutputSchemaFields
        v-model="node.items"
        :disabled="disabled"
      />
    </fieldset>
  </div>
</template>
