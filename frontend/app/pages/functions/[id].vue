<script setup lang="ts">
import type { FunctionRecord, RevisionRecord } from '~/types/api'

const route = useRoute()
const router = useRouter()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const id = String(route.params.id)
const { data: record, error, status, refresh } = await useAsyncData(`function-${id}`, () => api<FunctionRecord>(`/functions/${encodeURIComponent(id)}`), { server: false })
useSeoMeta({ title: () => record.value?.name || 'Функция' })
const names = useState<Record<string, string>>('function-names', () => ({}))
watch(record, (value) => {
  if (value)
    names.value[value.id] = value.name
})
const tabs = computed(() => [
  ...(auth.can('functions.run') || record.value?.public ? [{ label: 'Запустить', value: 'run', icon: 'i-lucide-play' }] : []),
  { label: 'Версии', value: 'revisions', icon: 'i-lucide-git-branch' },
  ...(auth.can('runs.read') ? [{ label: 'История', value: 'history', icon: 'i-lucide-history' }] : []),
  ...(auth.can('functions.update') || auth.can('functions.delete') ? [{ label: 'Настройки', value: 'settings', icon: 'i-lucide-settings-2' }] : [])
])
const tab = computed({ get: () => tabs.value.some(item => item.value === route.query.tab) ? String(route.query.tab) : tabs.value[0]!.value, set: (value: string) => {
  router.replace({ query: { ...route.query, tab: value } })
} })
const editor = ref(false)
const seed = ref<RevisionRecord | null>(null)
const revisionKey = ref(0)
function create(initial: RevisionRecord | null = null) {
  seed.value = initial
  editor.value = true
}
watch(record, (value) => {
  if (value && route.query.newRevision === '1' && !value.deleted && auth.can('functions.update')) {
    create()
    router.replace({ query: { tab: 'revisions' } })
  }
}, { immediate: true })
async function createFromCurrent() {
  try {
    create(record.value?.revision_id ? await api<RevisionRecord>(`/revisions/${record.value.revision_id}`) : null)
  } catch (problem) {
    toast.add({ title: 'Не удалось загрузить версию', description: errorMessage(problem), color: 'error' })
  }
}
async function saved() {
  await refresh()
  revisionKey.value++
  toast.add({ title: 'Версия сохранена', color: 'success', icon: 'i-lucide-check' })
}
const functionStatus = computed(() => record.value?.deleted ? 'deleted' : !record.value?.enabled ? 'disabled' : record.value?.runnable ? 'ready' : 'draft')
</script>

<template>
  <UContainer class="py-8 sm:py-12">
    <UBreadcrumb
      :items="[{ label: 'Функции', to: '/' }, { label: record?.name || 'Функция' }]"
      class="mb-7"
    />
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <div v-if="record">
      <div class="mb-8 flex flex-wrap items-start justify-between gap-5">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="text-3xl font-semibold tracking-tight break-all text-highlighted sm:text-4xl">
              {{ record.name }}
            </h1><StatusBadge :status="functionStatus" />
          </div><p class="mt-3 max-w-2xl text-muted">
            {{ record.description || 'Функция без описания' }}
          </p><p class="mt-3 font-mono text-xs text-dimmed">
            {{ record.id }}
          </p>
        </div>
        <UButton
          v-if="!record.deleted && auth.can('functions.update')"
          label="Новая версия"
          icon="i-lucide-plus"
          variant="soft"
          @click="createFromCurrent"
        />
      </div>
      <UTabs
        v-model="tab"
        :items="tabs"
        :content="false"
        variant="link"
        class="mb-7"
        :ui="{ list: 'overflow-x-auto' }"
      />
      <RunPanel
        v-if="tab === 'run'"
        :record="record"
      />
      <RevisionPanel
        v-else-if="tab === 'revisions'"
        :key="revisionKey"
        :record="record"
        :revision-id="typeof route.query.revision_id === 'string' ? route.query.revision_id : undefined"
        @create="create"
        @changed="refresh()"
      />
      <RunHistory
        v-else-if="tab === 'history'"
        :function-id="record.id"
      />
      <FunctionSettings
        v-else
        :record="record"
        @changed="refresh()"
      />
      <RevisionEditor
        v-model:open="editor"
        :function-id="record.id"
        :initial="seed"
        @created="revisionKey++"
        @saved="saved"
      />
    </div>
    <div
      v-else-if="status === 'idle' || status === 'pending'"
      class="space-y-6"
    >
      <USkeleton class="h-12 w-64" /><USkeleton class="h-96 w-full rounded-xl" />
    </div>
  </UContainer>
</template>
