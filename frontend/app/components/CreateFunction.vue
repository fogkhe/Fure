<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { FunctionRecord } from '~/types/api'

const { errorMessage } = useFormatting()
const { t } = useI18n()

const open = defineModel<boolean>('open', { default: false })
const api = useApi()
const auth = useAuth()
const state = reactive({ name: '', description: '' })
const saving = ref(false)
const error = ref('')
watch(open, (value) => {
  if (value) {
    state.name = ''
    state.description = ''
    error.value = ''
  }
})
function validate(): FormError[] {
  const errors: FormError[] = []
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(state.name))
    errors.push({ name: 'name', message: t('ui.use164LatinLettersDigitsHyphensOrUnderscores') })
  if (state.description.length > 1000)
    errors.push({ name: 'description', message: t('ui.maximum1000Characters') })
  return errors
}
async function create() {
  if (saving.value)
    return
  saving.value = true
  error.value = ''
  try {
    const record = await api<FunctionRecord>('/functions', { method: 'POST', body: { name: state.name, description: state.description || null } })
    open.value = false
    await navigateTo(`/functions/${record.id}${auth.can('functions.update') ? '?newRevision=1' : ''}`)
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
    :title="t('ui.newFunction')"
    :description="t('ui.chooseANameThenAddAPythonOrJinja')"
    :dismissible="!saving"
  >
    <template #body>
      <UForm
        :state="state"
        :validate="validate"
        class="space-y-5"
        @submit="create"
      >
        <UAlert
          v-if="error"
          :description="error"
          color="error"
          icon="i-lucide-circle-alert"
        />
        <UFormField
          :label="t('ui.functionName')"
          name="name"
          required
          :description="t('ui.thisNameWillBeUsedToRunTheFunction')"
        >
          <UInput
            v-model="state.name"
            :placeholder="t('ui.forExampleGreet')"
            autofocus
            class="w-full"
            :disabled="saving"
          />
        </UFormField>
        <UFormField
          :label="t('ui.description')"
          name="description"
          :hint="t('ui.optional')"
        >
          <UTextarea
            v-model="state.description"
            :placeholder="t('ui.whatDoesThisFunctionDo')"
            :rows="3"
            class="w-full"
            :disabled="saving"
          />
        </UFormField>
        <div class="flex justify-end gap-2">
          <UButton
            :label="t('ui.cancel')"
            color="neutral"
            variant="ghost"
            :disabled="saving"
            @click="open = false"
          /><UButton
            type="submit"
            :label="t('ui.createFunction')"
            icon="i-lucide-plus"
            :loading="saving"
          />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
