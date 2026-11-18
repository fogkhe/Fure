<script setup lang="ts">
import type { FunctionRecord, Page, RevisionRecord } from '~/types/api'

const { formatDate, errorMessage } = useFormatting()
const { t } = useI18n()

const props = defineProps<{
  record: FunctionRecord
  revisionId?: string
}>()
const emit = defineEmits<{
  create: [revision: RevisionRecord | null]
  changed: []
}>()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const page = ref(1)
const selected = ref<RevisionRecord | null>(null)
const selecting = ref(false)
const previewTab = ref('source')
const { data, status, error, refresh } = await useAsyncData(`revisions-${props.record.id}`, () => api<Page<RevisionRecord>>('/revisions', { query: { function_id: props.record.id, page: page.value - 1, size: 10 } }), { server: false, watch: [page] })
watch(data, (value) => {
  if (value && !props.revisionId && !value.items.some(item => item.id === selected.value?.id))
    selected.value = value.items.find(item => item.id === props.record.revision_id) ?? value.items[0] ?? null
}, { immediate: true })
watch(() => props.revisionId, async (id) => {
  if (!id) return
  try {
    const revision = await api<RevisionRecord>(`/revisions/${encodeURIComponent(id)}`)
    if (revision.function_id !== props.record.id) throw new Error('Revision belongs to another function')
    selected.value = revision
  } catch (problem) {
    toast.add({ title: t('ui.couldNotLoadVersion'), description: errorMessage(problem), color: 'error' })
  }
}, { immediate: true })
async function activate() {
  if (!selected.value || selecting.value)
    return
  selecting.value = true
  try {
    await api(`/functions/${props.record.id}`, { method: 'PATCH', body: { revision_id: selected.value.id } })
    emit('changed')
    toast.add({ title: t('ui.currentVersionChanged'), color: 'success', icon: 'i-lucide-check' })
  } catch (problem) {
    toast.add({ title: t('ui.couldNotSelectVersion'), description: errorMessage(problem), color: 'error' })
  } finally {
    selecting.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="font-semibold text-highlighted">
          {{ t('ui.implementationVersions') }}
        </h2><p class="mt-1 text-sm text-muted">
          {{ t('ui.savedCodeIsImmutableCreateANewVersionTo') }}
        </p>
      </div><UButton
        v-if="!record.deleted && auth.can('functions.update')"
        :label="t('ui.newVersion')"
        icon="i-lucide-plus"
        variant="soft"
        @click="emit('create', selected)"
      />
    </div>
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <USkeleton
      v-else-if="(status === 'idle' || status === 'pending') && !data"
      class="h-64 rounded-xl"
    />
    <UEmpty
      v-else-if="!data?.items.length"
      icon="i-lucide-git-branch"
      :title="t('ui.noImplementationsYet')"
      :description="t('ui.addPythonCodeOrAJinjaTemplateToMake')"
      :actions="record.deleted || !auth.can('functions.update') ? [] : [{ label: t('ui.addImplementation'), icon: 'i-lucide-plus', onClick: () => emit('create', null) }]"
      class="border border-dashed border-default"
    />
    <div
      v-else
      class="grid items-start gap-5 lg:grid-cols-3"
    >
      <div class="space-y-2">
        <button
          v-for="revision in data.items"
          :key="revision.id"
          class="w-full rounded-xl border p-4 text-left transition-colors"
          :class="selected?.id === revision.id ? 'border-primary/50 bg-primary/5' : 'border-default hover:bg-elevated/50'"
          @click="selected = revision"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="font-mono text-sm font-medium text-highlighted">#{{ shortId(revision.id) }}</span><UBadge
              v-if="revision.id === record.revision_id"
              :label="t('ui.current')"
              size="xs"
              variant="subtle"
            /><UIcon
              v-else
              name="i-lucide-chevron-right"
              class="size-4 text-dimmed"
            />
          </div>
          <p class="mt-2 text-sm text-muted">
            {{ revision.implementation.type === 'python' ? 'Python · Inline' : 'Jinja · OpenAI' }}
          </p><p class="mt-1 text-xs text-dimmed">
            {{ formatDate(revision.created_at) }}
          </p>
        </button>
        <UPagination
          v-if="data.total > 10"
          v-model:page="page"
          :total="data.total"
          :items-per-page="10"
          size="xs"
          :ui="{ list: 'flex-wrap' }"
        />
      </div>
      <UCard
        v-if="selected"
        class="min-w-0 lg:col-span-2"
      >
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <span class="font-mono text-sm text-highlighted">#{{ shortId(selected.id) }}</span><div class="flex gap-2">
              <UButton
                v-if="selected.id !== record.revision_id && !record.deleted && auth.can('functions.update')"
                :label="t('ui.setAsCurrent')"
                icon="i-lucide-check"
                size="sm"
                :loading="selecting"
                @click="activate"
              /><UButton
                v-if="!record.deleted && auth.can('functions.update')"
                :label="t('ui.useAsAStartingPoint')"
                icon="i-lucide-copy-plus"
                color="neutral"
                variant="outline"
                size="sm"
                @click="emit('create', selected)"
              />
            </div>
          </div>
        </template>
        <UTabs
          v-model="previewTab"
          :items="[{ label: t('ui.code'), value: 'source' }, { label: t('ui.schemas'), value: 'schemas' }, { label: t('ui.settings'), value: 'options' }]"
          :content="false"
          size="sm"
          class="mb-4"
        />
        <pre
          v-if="previewTab === 'source'"
          class="rounded-lg bg-elevated/40 p-4 font-mono text-sm leading-6 whitespace-pre-wrap break-words"
        >{{ selected.implementation.type === 'python' ? selected.implementation.code : selected.implementation.template }}</pre>
        <div
          v-else-if="previewTab === 'schemas'"
          class="space-y-4"
        >
          <JsonView
            :value="selected.implementation.input_schema"
            :title="t('ui.inputSchema')"
          /><JsonView
            :value="selected.implementation.output_schema"
            :title="t('ui.outputSchema')"
          />
        </div>
        <JsonView
          v-else
          :value="selected.runner_options"
          :title="t('ui.runnerSettings')"
        />
      </UCard>
    </div>
  </div>
</template>
