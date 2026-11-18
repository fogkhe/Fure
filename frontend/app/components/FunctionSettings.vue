<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { FunctionRecord } from '~/types/api'

const { errorMessage } = useFormatting()
const { t } = useI18n()

const props = defineProps<{
  record: FunctionRecord
}>()
const emit = defineEmits<{
  changed: []
}>()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const state = reactive({ name: '', description: '', enabled: true, public: false })
const original = ref('')
const saving = ref(false)
const deleting = ref(false)
const error = ref('')
const dirty = computed(() => JSON.stringify(state) !== original.value)
function reset(value: FunctionRecord) {
  Object.assign(state, { name: value.name, description: value.description || '', enabled: value.enabled, public: value.public })
  original.value = JSON.stringify(state)
}
reset(props.record)
watch(() => props.record, (value) => {
  if (!dirty.value)
    reset(value)
})
function validate(): FormError[] {
  const errors: FormError[] = []
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(state.name))
    errors.push({ name: 'name', message: t('ui.use164LatinLettersDigitsHyphensOrUnderscores') })
  if (state.description.length > 1000)
    errors.push({ name: 'description', message: t('ui.maximum1000Characters') })
  return errors
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    const updated = await api<FunctionRecord>(`/functions/${props.record.id}`, { method: 'PATCH', body: { name: state.name, description: state.description || null, enabled: state.enabled, ...(state.public !== props.record.public ? { public: state.public } : {}) } })
    reset(updated)
    emit('changed')
    toast.add({ title: t('ui.settingsSaved'), icon: 'i-lucide-check', color: 'success' })
  } catch (problem) {
    error.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
async function changeDeletion(restore = false) {
  saving.value = true
  error.value = ''
  try {
    if (restore)
      await api(`/functions/${props.record.id}/undelete`, { method: 'POST' })
    else
      await api(`/functions/${props.record.id}`, { method: 'DELETE' })
    deleting.value = false
    emit('changed')
    toast.add({ title: restore ? t('ui.functionRestored') : t('ui.functionDeleted'), color: 'success' })
  } catch (problem) {
    error.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <UAlert
      v-if="error"
      :description="error"
      color="error"
      icon="i-lucide-circle-alert"
    />
    <UAlert
      v-if="record.deleted"
      :title="t('ui.functionDeleted')"
      :description="t('ui.versionsAndHistoryArePreservedRestoreTheFunctionTo')"
      color="warning"
      icon="i-lucide-archive"
      :actions="auth.can('functions.delete') ? [{ label: t('ui.restore'), onClick: () => changeDeletion(true), loading: saving }] : []"
    />
    <UCard>
      <template #header>
        <h2 class="font-semibold text-highlighted">
          {{ t('ui.generalSettings') }}
        </h2>
      </template>
      <UForm
        :state="state"
        :validate="validate"
        :disabled="saving || record.deleted || !auth.can('functions.update')"
        class="space-y-5"
        @submit="save"
      >
        <UFormField
          :label="t('ui.functionName')"
          name="name"
          required
          :description="t('ui.renamingChangesTheNameBasedExecutionUrl')"
        >
          <UInput
            v-model="state.name"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('ui.description')"
          name="description"
        >
          <UTextarea
            v-model="state.description"
            :rows="3"
            class="w-full"
          />
        </UFormField>
        <USwitch
          v-model="state.enabled"
          :label="t('ui.functionEnabled')"
          :description="t('ui.aDisabledFunctionKeepsItsVersionsAndHistoryBut')"
        />
        <USwitch
          v-model="state.public"
          :label="t('ui.publicExecution')"
          :description="t('ui.anyoneWhoKnowsTheFunctionNameCanRunIt')"
          :disabled="!auth.can('functions.publish') || !auth.can('functions.update') || record.deleted || saving"
        />
        <p
          v-if="record.public"
          class="font-mono text-xs break-all text-muted"
        >
          POST /v1/run/{{ record.name }}
        </p>
        <UButton
          type="submit"
          :label="t('ui.saveChanges')"
          icon="i-lucide-check"
          :disabled="!dirty || record.deleted || !auth.can('functions.update')"
          :loading="saving"
        />
      </UForm>
    </UCard>
    <UCard v-if="!record.deleted && auth.can('functions.delete')">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="font-medium text-highlighted">
            {{ t('ui.deleteFunction') }}
          </h3><p class="mt-1 text-sm text-muted">
            {{ t('ui.historyAndVersionsWillRemainAvailable') }}
          </p>
        </div><UButton
          :label="t('ui.deleteFunction2')"
          icon="i-lucide-trash-2"
          color="error"
          variant="soft"
          @click="deleting = true"
        />
      </div>
    </UCard>
    <UModal
      v-model:open="deleting"
      :title="t('ui.deleteFunction3')"
      :description="t('ui.theFunctionWillStopAcceptingRunsYouCanRestore', { value1: record.name })"
      :dismissible="!saving"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            :label="t('ui.cancel')"
            color="neutral"
            variant="ghost"
            :disabled="saving"
            @click="deleting = false"
          /><UButton
            :label="t('ui.delete')"
            color="error"
            :loading="saving"
            @click="changeDeletion()"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>
