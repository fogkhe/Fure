<script setup lang="ts">
import type { FunctionRecord, Page } from '~/types/api'

useSeoMeta({ title: 'Функции' })
const api = useApi()
const auth = useAuth()
const page = ref(1)
const name = ref('')
const search = ref('')
const filter = ref('all')
const creating = ref(false)
const filters = [
  { label: 'Все функции', value: 'all' },
  { label: 'Включённые', value: 'enabled' },
  { label: 'Выключенные', value: 'disabled' },
  { label: 'Удалённые', value: 'deleted' }
]
const query = computed(() => ({ page: page.value - 1, size: 12, name: name.value || undefined, deleted: filter.value === 'deleted', enabled: filter.value === 'enabled' ? true : filter.value === 'disabled' ? false : undefined }))
const { data, status, error, refresh } = await useAsyncData('functions', () => api<Page<FunctionRecord>>('/functions', { query: query.value }), { server: false, watch: [query] })
const { data: overview, refresh: refreshOverview } = await useAsyncData('overview', async () => {
  const [functions, revisions, runs] = await Promise.all(['/functions', '/revisions', '/runs'].map(url => url === '/runs' && !auth.can('runs.read') ? Promise.resolve(null) : api<Page<unknown>>(url, { query: { size: 1 } })))
  return { functions: functions?.total, revisions: revisions?.total, runs: runs?.total }
}, { server: false })
watch(filter, () => {
  page.value = 1
})
function applySearch() {
  page.value = 1
  name.value = search.value.trim()
}
async function reload() {
  await Promise.all([refresh(), refreshOverview()])
}
function state(record: FunctionRecord) {
  return record.deleted ? 'deleted' : !record.enabled ? 'disabled' : record.runnable ? 'ready' : 'draft'
}
</script>

<template>
  <UContainer class="py-8 sm:py-12">
    <div class="mb-9 flex flex-wrap items-end justify-between gap-5">
      <div>
        <p class="mb-3 text-xs font-semibold tracking-widest text-primary uppercase">
          Ваше рабочее пространство
        </p><h1 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
          Логика — в функциях.
        </h1><p class="mt-3 max-w-xl text-muted">
          Создавайте реализации, управляйте версиями и превращайте код в готовый API.
        </p>
      </div>
      <UButton
        v-if="auth.can('functions.create')"
        label="Новая функция"
        icon="i-lucide-plus"
        size="lg"
        @click="creating = true"
      />
    </div>
    <div class="mb-9 grid gap-4 sm:grid-cols-3">
      <div
        v-for="item in [{ label: 'Функции', value: overview?.functions, icon: 'i-lucide-square-function' }, { label: 'Версии реализаций', value: overview?.revisions, icon: 'i-lucide-git-branch' }, { label: 'Запуски', value: overview?.runs, icon: 'i-lucide-activity' }]"
        :key="item.label"
        class="flex items-center justify-between rounded-xl border border-default bg-elevated/25 p-5"
      >
        <div>
          <p class="text-sm text-muted">
            {{ item.label }}
          </p><p class="mt-1 text-2xl font-semibold tabular-nums text-highlighted">
            {{ item.value ?? '—' }}
          </p>
        </div><UIcon
          :name="item.icon"
          class="size-6 text-primary/70"
        />
      </div>
    </div>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h2 class="font-semibold text-highlighted">
          Библиотека функций
        </h2><UBadge
          v-if="data"
          :label="String(data.total)"
          color="neutral"
          variant="subtle"
          size="sm"
        />
      </div>
      <div class="flex w-full flex-wrap gap-2 sm:w-auto">
        <form
          class="flex w-full min-w-0 gap-1 sm:w-auto"
          @submit.prevent="applySearch"
        >
          <UInput
            v-model="search"
            icon="i-lucide-search"
            placeholder="Точное имя функции"
            aria-label="Поиск по имени"
            class="w-full sm:w-56"
          /><UButton
            type="submit"
            icon="i-lucide-arrow-right"
            color="neutral"
            variant="outline"
            aria-label="Найти"
          />
        </form>
        <USelect
          v-model="filter"
          :items="filters"
          class="w-44"
          aria-label="Статус функций"
        />
        <UTooltip text="Обновить">
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="outline"
            aria-label="Обновить список"
            :loading="status === 'pending'"
            @click="reload"
          />
        </UTooltip>
      </div>
    </div>
    <PageError
      v-if="error"
      :error="error"
      @retry="reload"
    />
    <div
      v-else-if="status === 'pending' && !data"
      class="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      <USkeleton
        v-for="i in 6"
        :key="i"
        class="h-48 rounded-xl"
      />
    </div>
    <div
      v-else-if="data?.items.length"
      class="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      <UCard
        v-for="record in data.items"
        :key="record.id"
        class="transition-shadow hover:ring-primary/40"
      >
        <div class="mb-4 flex items-center justify-between gap-2">
          <div class="flex size-10 items-center justify-center rounded-xl bg-primary/10">
            <UIcon
              name="i-lucide-square-function"
              class="size-5 text-primary"
            />
          </div><StatusBadge :status="state(record)" />
        </div>
        <NuxtLink
          :to="`/functions/${record.id}`"
          class="inline-flex max-w-full items-center gap-2 text-lg font-semibold text-highlighted transition-colors hover:text-primary"
        ><span class="truncate">{{ record.name }}</span><UIcon
          name="i-lucide-arrow-up-right"
          class="size-4 shrink-0 text-dimmed"
        /></NuxtLink>
        <p class="mt-2 min-h-10 line-clamp-2 text-sm leading-5 text-muted">
          {{ record.description || 'Описание пока не добавлено.' }}
        </p>
        <div class="mt-5 flex items-center justify-between gap-2 border-t border-default pt-3 text-xs text-dimmed">
          <span>{{ formatDate(record.updated_at) }}</span><span class="font-mono">{{ record.revision_id ? `#${shortId(record.revision_id)}` : 'Нет версии' }}</span>
        </div>
      </UCard>
    </div>
    <UEmpty
      v-else
      icon="i-lucide-square-function"
      :title="name || filter !== 'all' ? 'Функции не найдены' : 'Здесь начинается ваша первая функция'"
      :description="name || filter !== 'all' ? 'Измените фильтры или проверьте точное имя функции.' : 'Добавьте Python-код или Jinja-шаблон, создайте версию и выполните первый запуск.'"
      :actions="auth.can('functions.create') ? [{ label: 'Новая функция', icon: 'i-lucide-plus', onClick: () => creating = true }] : []"
      class="min-h-72 border border-dashed border-default"
    />
    <div
      v-if="data && data.total > 12"
      class="mt-7 flex justify-center"
    >
      <UPagination
        v-model:page="page"
        :total="data.total"
        :items-per-page="12"
      />
    </div>
    <CreateFunction v-model:open="creating" />
  </UContainer>
</template>
