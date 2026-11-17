<script setup lang="ts">
import type { APIKeyRecord, Page } from '~/types/api'

useSeoMeta({ title: 'Мой аккаунт' })
const auth = useAuth()
const api = useApi()
const toast = useToast()
const page = ref(1)
const { data, error, status, refresh } = await useAsyncData('my-keys', () => auth.can('keys.manage')
  ? api<Page<APIKeyRecord>>('/keys', { query: { page: page.value - 1, size: 15 } })
  : Promise.resolve(null), { server: false, watch: [page] })
const open = ref(false)
const secret = ref('')
const saving = ref(false)
const formError = ref('')
const key = reactive({ name: '', permissions: [] as string[], function_ids: [] as string[], expires: '' })
const editTarget = ref<APIKeyRecord | null>(null)
const editing = ref(false)
const editFunctions = ref<string[]>([])
const editError = ref('')
function editKey(item: APIKeyRecord) {
  editTarget.value = item
  editFunctions.value = [...item.function_ids]
  editError.value = ''
  editing.value = true
}
async function saveFunctions() {
  if (!editTarget.value) return
  saving.value = true
  editError.value = ''
  try {
    await api(`/keys/${editTarget.value.id}`, { method: 'PATCH', body: { function_ids: editFunctions.value } })
    editing.value = false
    await refresh()
  } catch (problem) {
    editError.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
const permissions = computed(() => permissionItems(auth.session.value?.permissions || []))
watch(open, (value) => {
  if (value) {
    Object.assign(key, { name: '', permissions: [], function_ids: [], expires: '' })
    formError.value = ''
    secret.value = ''
  }
})
async function createKey() {
  saving.value = true
  formError.value = ''
  try {
    const result = await api<APIKeyRecord & { secret: string }>('/keys', { method: 'POST', body: {
      name: key.name, permissions: key.permissions, function_ids: key.function_ids, expires_at: key.expires ? new Date(key.expires).toISOString() : null
    } })
    secret.value = result.secret
    page.value = 1
    await refresh()
  } catch (problem) {
    formError.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
const revokeTarget = ref<APIKeyRecord | null>(null)
const revokeOpen = computed({ get: () => !!revokeTarget.value, set: (value: boolean) => {
  if (!value) revokeTarget.value = null
} })
async function revoke() {
  if (!revokeTarget.value) return
  saving.value = true
  try {
    await api(`/keys/${revokeTarget.value.id}`, { method: 'DELETE' })
    revokeTarget.value = null
    await refresh()
  } catch (problem) {
    toast.add({ title: 'Не удалось отозвать ключ', description: errorMessage(problem), color: 'error' })
  } finally {
    saving.value = false
  }
}
const password = reactive({ current_password: '', new_password: '', confirmation: '' })
const passwordError = ref('')
async function changePassword() {
  if (password.new_password !== password.confirmation) {
    passwordError.value = 'Пароли не совпадают.'
    return
  }
  saving.value = true
  passwordError.value = ''
  try {
    await api('/auth/password', { method: 'POST', body: { current_password: password.current_password, new_password: password.new_password } })
    Object.assign(password, { current_password: '', new_password: '', confirmation: '' })
    auth.clear()
    toast.add({ title: 'Пароль изменён. Войдите снова.', color: 'success' })
    await navigateTo('/login')
  } catch (problem) {
    passwordError.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
async function copySecret() {
  try {
    await navigator.clipboard.writeText(secret.value)
    toast.add({ title: 'Ключ скопирован', color: 'success' })
  } catch {
    toast.add({ title: 'Скопируйте ключ вручную', color: 'warning' })
  }
}
function keyStatus(item: APIKeyRecord) {
  return item.revoked_at ? 'Отозван' : item.expires_at && new Date(item.expires_at) <= new Date() ? 'Истёк' : 'Активен'
}
</script>

<template>
  <UContainer class="space-y-8 py-8 sm:py-12">
    <div>
      <p class="mb-3 text-sm font-medium text-primary">
        Личный кабинет
      </p>
      <h1 class="text-3xl font-semibold tracking-tight text-highlighted">
        {{ auth.session.value?.user.username }}
      </h1>
      <div class="mt-4 flex flex-wrap gap-2">
        <UBadge
          v-for="role in auth.session.value?.user.roles"
          :key="role.id"
          :label="role.name"
          color="neutral"
          variant="subtle"
        />
      </div>
    </div>
    <UCard v-if="auth.can('keys.manage')">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="font-semibold text-highlighted">
              API-ключи
            </h2><p class="mt-1 text-sm text-muted">
              Доступ интеграций в пределах ваших разрешений.
            </p>
          </div>
          <UButton
            label="Создать ключ"
            icon="i-lucide-plus"
            @click="open = true"
          />
        </div>
      </template>
      <PageError
        v-if="error"
        :error="error"
        @retry="refresh()"
      />
      <UTable
        :data="data?.items || []"
        :loading="status === 'idle' || status === 'pending'"
        :columns="[{ accessorKey: 'name', header: 'Название' }, { accessorKey: 'prefix', header: 'Ключ' }, { id: 'status', header: 'Статус' }, { id: 'permissions', header: 'Разрешения' }, { id: 'expires', header: 'Срок действия' }, { id: 'actions' }]"
        empty="API-ключей пока нет"
      >
        <template #prefix-cell="{ row }">
          <code>{{ row.original.prefix }}…</code>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :label="keyStatus(row.original)"
            :color="keyStatus(row.original) === 'Активен' ? 'success' : 'neutral'"
            variant="subtle"
          />
        </template>
        <template #permissions-cell="{ row }">
          <span class="text-sm text-muted">{{ row.original.permissions.length }} разрешений</span>
        </template>
        <template #expires-cell="{ row }">
          {{ row.original.expires_at ? formatDate(row.original.expires_at) : 'Без ограничения' }}
        </template>
        <template #actions-cell="{ row }">
          <UButton
            v-if="keyStatus(row.original) === 'Активен'"
            :label="`Функции (${row.original.function_ids.length})`"
            color="neutral"
            variant="ghost"
            size="xs"
            @click="editKey(row.original)"
          />
          <UButton
            v-if="!row.original.revoked_at"
            label="Отозвать"
            color="error"
            variant="ghost"
            size="xs"
            @click="revokeTarget = row.original"
          />
        </template>
      </UTable>
      <UPagination
        v-if="data && data.total > 15"
        v-model:page="page"
        :total="data.total"
        :items-per-page="15"
        class="mt-5 justify-center"
      />
    </UCard>
    <div class="grid items-start gap-6 lg:grid-cols-2">
      <UCard>
        <template #header>
          <h2 class="font-semibold text-highlighted">
            Смена пароля
          </h2>
        </template>
        <UForm
          :state="password"
          class="space-y-4"
          @submit="changePassword"
        >
          <UAlert
            v-if="passwordError"
            :description="passwordError"
            color="error"
          />
          <UFormField
            label="Текущий пароль"
            name="current_password"
            required
          >
            <UInput
              v-model="password.current_password"
              type="password"
              autocomplete="current-password"
              required
              class="w-full"
            />
          </UFormField>
          <UFormField
            label="Новый пароль"
            name="new_password"
            description="От 12 до 256 символов."
            required
          >
            <UInput
              v-model="password.new_password"
              type="password"
              autocomplete="new-password"
              :minlength="12"
              :maxlength="256"
              required
              class="w-full"
            />
          </UFormField>
          <UFormField
            label="Повторите новый пароль"
            name="confirmation"
            required
          >
            <UInput
              v-model="password.confirmation"
              type="password"
              autocomplete="new-password"
              required
              class="w-full"
            />
          </UFormField>
          <p class="text-sm text-muted">
            После смены пароля все сеансы будут завершены.
          </p>
          <UButton
            type="submit"
            label="Изменить пароль"
            :loading="saving"
          />
        </UForm>
      </UCard>
      <UCard>
        <template #header>
          <h2 class="font-semibold text-highlighted">
            Ваши разрешения
          </h2>
        </template>
        <ul class="space-y-2 text-sm text-muted">
          <li
            v-for="permission in auth.session.value?.permissions"
            :key="permission"
            class="flex items-center gap-2"
          >
            <UIcon
              name="i-lucide-check"
              class="shrink-0 text-primary"
            />{{ permissionLabels[permission] || permission }}
          </li>
        </ul>
        <p
          v-if="!auth.session.value?.permissions.length"
          class="text-sm text-muted"
        >
          Разрешения пока не назначены. Обратитесь к администратору.
        </p>
      </UCard>
    </div>
    <UModal
      v-model:open="open"
      title="Новый API-ключ"
      description="Выберите только необходимые интеграции разрешения."
      :dismissible="!saving"
      :ui="{ content: 'sm:max-w-xl' }"
      scrollable
      @after:leave="secret = ''"
    >
      <template #body>
        <div
          v-if="secret"
          class="space-y-4"
        >
          <UAlert
            title="Сохраните ключ сейчас"
            description="Это единственный раз, когда секрет показывается целиком."
            color="warning"
            icon="i-lucide-key-round"
          />
          <code class="block rounded-lg border border-default bg-elevated p-4 text-sm break-all select-all">{{ secret }}</code>
          <UButton
            label="Скопировать ключ"
            icon="i-lucide-copy"
            @click="copySecret"
          />
          <p class="text-sm text-muted">
            Передавайте его в заголовке Authorization: Bearer &lt;ключ&gt;.
          </p>
          <UButton
            label="Готово"
            color="neutral"
            variant="outline"
            @click="open = false"
          />
        </div>
        <UForm
          v-else
          :state="key"
          class="space-y-5"
          @submit="createKey"
        >
          <UAlert
            v-if="formError"
            :description="formError"
            color="error"
          />
          <UFormField
            label="Название"
            name="name"
            required
          >
            <UInput
              v-model="key.name"
              required
              :maxlength="100"
              class="w-full"
            />
          </UFormField>
          <UFormField
            label="Действует до"
            name="expires"
            hint="Необязательно"
          >
            <UInput
              v-model="key.expires"
              type="datetime-local"
              class="w-full"
            />
          </UFormField>
          <UFormField
            label="Разрешения"
            name="permissions"
          >
            <UCheckboxGroup
              v-model="key.permissions"
              :items="permissions"
            />
          </UFormField>
          <UFormField
            label="Доступные функции"
            name="function_ids"
          >
            <KeyFunctionSelect v-model="key.function_ids" />
          </UFormField>
          <UButton
            type="submit"
            label="Создать ключ"
            :loading="saving"
          />
        </UForm>
      </template>
    </UModal>
    <UModal
      v-model:open="editing"
      title="Доступные функции"
      :description="`API-ключ «${editTarget?.name}»`"
      :dismissible="!saving"
      :ui="{ content: 'sm:max-w-xl' }"
      scrollable
    >
      <template #body>
        <UForm
          :state="{ function_ids: editFunctions }"
          class="space-y-5"
          @submit="saveFunctions"
        >
          <UAlert
            v-if="editError"
            :description="editError"
            color="error"
          />
          <KeyFunctionSelect v-model="editFunctions" />
          <UButton
            type="submit"
            label="Сохранить функции"
            :loading="saving"
          />
        </UForm>
      </template>
    </UModal>
    <UModal
      v-model:open="revokeOpen"
      title="Отозвать API-ключ?"
      :description="`Интеграции с ключом «${revokeTarget?.name}» потеряют доступ.`"
      :dismissible="!saving"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            label="Отмена"
            color="neutral"
            variant="ghost"
            @click="revokeTarget = null"
          /><UButton
            label="Отозвать"
            color="error"
            :loading="saving"
            @click="revoke"
          />
        </div>
      </template>
    </UModal>
  </UContainer>
</template>
