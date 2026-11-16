<script setup lang="ts">
import type { Page, RoleRecord, UserRecord } from '~/types/api'

useSeoMeta({ title: 'Пользователи' })
const api = useApi()
const auth = useAuth()
const page = ref(1)
const { data, error, status, refresh } = await useAsyncData('users', () => api<Page<UserRecord>>('/users', { query: { page: page.value - 1, size: 20 } }), { server: false, watch: [page] })
const { data: roles, error: rolesError, refresh: refreshRoles } = await useAsyncData('user-roles', () => api<Page<RoleRecord>>('/roles', { query: { size: 1000 } }), { server: false })
const open = ref(false)
const selected = ref<UserRecord | null>(null)
const saving = ref(false)
const formError = ref('')
const state = reactive({ username: '', password: '', role_ids: [] as string[], enabled: true })
function edit(user: UserRecord | null) {
  selected.value = user
  Object.assign(state, { username: user?.username || '', password: '', role_ids: [...(user?.role_ids || [])], enabled: user?.enabled ?? true })
  formError.value = ''
  open.value = true
}
async function save() {
  saving.value = true
  formError.value = ''
  try {
    await api(selected.value ? `/users/${selected.value.id}` : '/users', {
      method: selected.value ? 'PATCH' : 'POST', body: {
        username: state.username, role_ids: state.role_ids, enabled: state.enabled,
        ...(state.password ? { password: state.password } : {})
      }
    })
    state.password = ''
    open.value = false
    await auth.refresh()
    if (!auth.can('users.manage')) {
      await navigateTo(auth.home())
      return
    }
    await refresh()
  } catch (problem) {
    formError.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UContainer class="space-y-7 py-8 sm:py-12">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="mb-3 text-sm font-medium text-primary">
          Управление доступом
        </p><h1 class="text-3xl font-semibold text-highlighted">
          Пользователи
        </h1><p class="mt-3 text-muted">
          Назначайте роли и управляйте доступом к общему каталогу.
        </p>
      </div>
      <UButton
        label="Новый пользователь"
        icon="i-lucide-user-plus"
        @click="edit(null)"
      />
    </div>
    <PageError
      v-if="error"
      :error="error"
      @retry="refresh()"
    />
    <UTable
      :data="data?.items || []"
      :loading="status === 'pending'"
      :columns="[{ accessorKey: 'username', header: 'Логин' }, { id: 'roles', header: 'Роли' }, { id: 'status', header: 'Статус' }, { id: 'created', header: 'Создан' }, { id: 'actions' }]"
      empty="Пользователи не найдены"
      class="rounded-xl border border-default"
    >
      <template #username-cell="{ row }">
        <span class="font-medium text-highlighted">{{ row.original.username }}</span><UBadge
          v-if="row.original.id === auth.session.value?.user.id"
          label="Вы"
          size="xs"
          color="neutral"
          variant="subtle"
          class="ml-2"
        />
      </template>
      <template #roles-cell="{ row }">
        <div class="flex flex-wrap gap-1">
          <UBadge
            v-for="role in row.original.roles"
            :key="role.id"
            :label="role.name"
            color="neutral"
            variant="subtle"
          />
        </div>
      </template>
      <template #status-cell="{ row }">
        <UBadge
          :label="row.original.enabled ? 'Активен' : 'Заблокирован'"
          :color="row.original.enabled ? 'success' : 'neutral'"
          variant="subtle"
        />
      </template>
      <template #created-cell="{ row }">
        {{ formatDate(row.original.created_at) }}
      </template>
      <template #actions-cell="{ row }">
        <UButton
          label="Изменить"
          icon="i-lucide-pencil"
          color="neutral"
          variant="ghost"
          size="xs"
          @click="edit(row.original)"
        />
      </template>
    </UTable>
    <UPagination
      v-if="data && data.total > 20"
      v-model:page="page"
      :total="data.total"
      :items-per-page="20"
      class="justify-center"
    />
    <UModal
      v-model:open="open"
      :title="selected ? `Пользователь ${selected.username}` : 'Новый пользователь'"
      description="Разрешения всех назначенных ролей складываются."
      :dismissible="!saving"
      @after:leave="state.password = ''"
    >
      <template #body>
        <UForm
          :state="state"
          class="space-y-5"
          @submit="save"
        >
          <UAlert
            v-if="formError"
            :description="formError"
            color="error"
          />
          <UFormField
            label="Логин"
            name="username"
            description="Строчные латинские буквы, цифры, точки, дефисы и подчёркивания."
            required
          >
            <UInput
              v-model="state.username"
              autocomplete="off"
              pattern="[a-z0-9][a-z0-9_.\-]{0,63}"
              required
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="selected ? 'Новый пароль' : 'Пароль'"
            name="password"
            :required="!selected"
            :description="selected ? 'Оставьте пустым, чтобы сохранить текущий пароль. Новый пароль завершит все сеансы пользователя.' : 'От 12 до 256 символов.'"
          >
            <UInput
              v-model="state.password"
              type="password"
              autocomplete="new-password"
              :minlength="12"
              :maxlength="256"
              :required="!selected"
              class="w-full"
            />
          </UFormField>
          <PageError
            v-if="rolesError"
            :error="rolesError"
            @retry="refreshRoles()"
          />
          <UFormField
            label="Роли"
            name="role_ids"
          >
            <UCheckboxGroup
              v-model="state.role_ids"
              :items="roles?.items.map(role => ({ label: role.name, value: role.id })) || []"
            />
          </UFormField>
          <USwitch
            v-model="state.enabled"
            label="Пользователь активен"
            description="Блокировка завершает сеансы и отзывает все API-ключи."
          />
          <UButton
            type="submit"
            :label="selected ? 'Сохранить пользователя' : 'Создать пользователя'"
            :loading="saving"
            :disabled="!!rolesError"
          />
        </UForm>
      </template>
    </UModal>
  </UContainer>
</template>
