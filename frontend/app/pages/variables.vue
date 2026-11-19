<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { Page, VariableRecord } from '~/types/api'
import { parseInputJson } from '~/utils/inputSchema'

const { t } = useI18n()
const { formatDate, errorMessage } = useFormatting()
useSeoMeta({ title: () => t('variables.title') })
const api = useApi()
const auth = useAuth()
const page = ref(1)
const size = 20
const { data, error, status, refresh } = await useAsyncData('variables', (_app, { signal }) => api<Page<VariableRecord>>('/variables', { query: { page: page.value - 1, size }, signal }), { server: false, watch: [page] })
const canManage = computed(() => auth.can('variables.manage'))
const columns = computed(() => [
  { accessorKey: 'name', header: t('ui.name') },
  { id: 'value', header: t('variables.value') },
  { id: 'updated', header: t('variables.updated') },
  ...(canManage.value ? [{ id: 'actions' }] : [])
])

const open = ref(false)
const editing = ref<VariableRecord | null>(null)
const target = ref<VariableRecord | null>(null)
const deleting = computed({
  get: () => target.value !== null,
  set: (value: boolean) => {
    if (!value) target.value = null
  }
})
const busy = ref(false)
const problem = ref('')
const state = reactive({ name: '', secret: false, value: '', secretValue: '' })
watch(open, (value) => {
  if (!value) state.secretValue = ''
})

function edit(item: VariableRecord | null) {
  editing.value = item
  state.name = item?.name ?? ''
  state.secret = item?.secret ?? false
  state.value = item && !item.secret ? JSON.stringify(item.value, null, 2) : ''
  state.secretValue = ''
  problem.value = ''
  open.value = true
}

function validate(): FormError[] {
  const errors: FormError[] = []
  if (!/^[a-zA-Z_][a-zA-Z0-9_]{0,63}$/.test(state.name)) {
    errors.push({ name: 'name', message: t('variables.invalidName') })
  }
  if (state.secret) {
    if (!state.secretValue) errors.push({ name: 'secretValue', message: t('variables.secretRequired') })
  } else {
    try {
      parseInputJson(state.value)
    } catch (failure) {
      errors.push({ name: 'value', message: errorMessage(failure) })
    }
  }
  return errors
}

async function save() {
  if (busy.value) return
  busy.value = true
  problem.value = ''
  try {
    const value = state.secret ? state.secretValue : parseInputJson(state.value)
    if (editing.value) {
      await api(`/variables/${encodeURIComponent(editing.value.name)}`, { method: 'PATCH', body: { value } })
    } else {
      await api('/variables', { method: 'POST', body: { name: state.name, secret: state.secret, value } })
    }
    open.value = false
    await refresh()
  } catch (failure) {
    problem.value = errorMessage(failure)
  } finally {
    busy.value = false
  }
}

function confirmDelete(item: VariableRecord) {
  problem.value = ''
  target.value = item
}

async function remove() {
  if (!target.value || busy.value) return
  busy.value = true
  problem.value = ''
  try {
    await api(`/variables/${encodeURIComponent(target.value.name)}`, { method: 'DELETE' })
    target.value = null
    if (page.value > 1 && data.value?.items.length === 1) page.value--
    else await refresh()
  } catch (failure) {
    problem.value = errorMessage(failure)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <UContainer class="space-y-6 py-8 sm:py-12">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-semibold tracking-tight text-highlighted">
          {{ t('variables.title') }}
        </h1>
        <p class="mt-2 text-muted">
          {{ t('variables.description') }}
        </p>
      </div>
      <UButton
        v-if="canManage"
        icon="i-lucide-plus"
        :label="t('variables.create')"
        @click="edit(null)"
      />
    </div>
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <UTable
      v-else
      :data="data?.items || []"
      :loading="status === 'idle' || status === 'pending'"
      :columns="columns"
      :empty="t('variables.empty')"
      class="rounded-xl border border-default"
    >
      <template #name-cell="{ row }">
        <code>{{ row.original.name }}</code>
      </template>
      <template #value-cell="{ row }">
        <UBadge
          v-if="row.original.secret"
          :label="t('variables.secretSet')"
          color="neutral"
          variant="subtle"
        />
        <code
          v-else
          class="block max-w-64 truncate"
        >{{ JSON.stringify(row.original.value) }}</code>
      </template>
      <template #updated-cell="{ row }">
        {{ formatDate(row.original.updated_at) }}
      </template>
      <template #actions-cell="{ row }">
        <div class="flex justify-end gap-1">
          <UButton
            icon="i-lucide-pencil"
            color="neutral"
            variant="ghost"
            :aria-label="t('variables.edit')"
            @click="edit(row.original)"
          />
          <UButton
            icon="i-lucide-trash-2"
            color="neutral"
            variant="ghost"
            :aria-label="t('variables.delete')"
            @click="confirmDelete(row.original)"
          />
        </div>
      </template>
    </UTable>
    <UPagination
      v-if="data && data.total > size"
      v-model:page="page"
      :total="data.total"
      :items-per-page="size"
      class="justify-center"
    />

    <UModal
      v-model:open="open"
      :title="t(editing ? 'variables.edit' : 'variables.create')"
      :dismissible="!busy"
      scrollable
    >
      <template #body>
        <UForm
          :state="state"
          :validate="validate"
          class="space-y-4"
          @submit="save"
        >
          <UAlert
            v-if="problem"
            :description="problem"
            color="error"
          />
          <UFormField
            :label="t('ui.name')"
            name="name"
            required
          >
            <UInput
              v-model="state.name"
              :disabled="busy || !!editing"
              autocomplete="off"
              spellcheck="false"
              class="w-full"
            />
          </UFormField>
          <USwitch
            v-model="state.secret"
            :label="t('variables.secret')"
            :description="t('variables.secretHint')"
            :disabled="busy || !!editing"
          />
          <UFormField
            v-if="state.secret"
            :label="t('variables.secretValue')"
            name="secretValue"
            required
          >
            <UInput
              v-model="state.secretValue"
              type="password"
              autocomplete="new-password"
              :disabled="busy"
              class="w-full"
            />
          </UFormField>
          <UFormField
            v-else
            :label="t('variables.jsonValue')"
            name="value"
            :description="t('variables.jsonHint')"
            required
          >
            <CodeEditor
              v-model="state.value"
              language="json"
              :label="t('variables.jsonValue')"
              :rows="6"
              :disabled="busy"
            />
          </UFormField>
          <div class="flex justify-end gap-2">
            <UButton
              :label="t('ui.close')"
              color="neutral"
              variant="ghost"
              :disabled="busy"
              @click="open = false"
            />
            <UButton
              type="submit"
              :label="t('variables.save')"
              :loading="busy"
            />
          </div>
        </UForm>
      </template>
    </UModal>

    <UModal
      v-model:open="deleting"
      :title="t('variables.delete')"
      :description="t('variables.deleteHint', { name: target?.name ?? '' })"
      :dismissible="!busy"
    >
      <template #footer>
        <div class="w-full space-y-3">
          <UAlert
            v-if="problem"
            :description="problem"
            color="error"
          />
          <div class="flex justify-end gap-2">
            <UButton
              :label="t('ui.close')"
              color="neutral"
              variant="ghost"
              :disabled="busy"
              @click="target = null"
            />
            <UButton
              :label="t('variables.delete')"
              color="error"
              :loading="busy"
              @click="remove"
            />
          </div>
        </div>
      </template>
    </UModal>
  </UContainer>
</template>
