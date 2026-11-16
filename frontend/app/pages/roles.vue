<script setup lang="ts">
import type { Page, RoleRecord } from '~/types/api'

useSeoMeta({ title: 'Роли' })
const api = useApi()
const auth = useAuth()
const page = ref(1)
const { data, error, status, refresh } = await useAsyncData('roles', () => api<Page<RoleRecord>>('/roles', { query: { page: page.value - 1, size: 20 } }), { server: false, watch: [page] })
const { data: permissions, error: permissionsError, refresh: refreshPermissions } = await useAsyncData('permissions', () => api<string[]>('/roles/permissions'), { server: false })
const open = ref(false)
const selected = ref<RoleRecord | null>(null)
const saving = ref(false)
const formError = ref('')
const state = reactive({ name: '', permissions: [] as string[] })
function edit(role: RoleRecord | null) {
  selected.value = role
  Object.assign(state, { name: role?.name || '', permissions: [...(role?.permissions || [])] })
  formError.value = ''
  open.value = true
}
async function save() {
  saving.value = true
  formError.value = ''
  try {
    await api(selected.value ? `/roles/${selected.value.id}` : '/roles', { method: selected.value ? 'PATCH' : 'POST', body: state })
    open.value = false
    await auth.refresh()
    if (!auth.can('roles.manage')) {
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
const target = ref<RoleRecord | null>(null)
const deleting = computed({ get: () => !!target.value, set: (value: boolean) => {
  if (!value) target.value = null
} })
const deleteError = ref('')
async function remove() {
  if (!target.value) return
  saving.value = true
  deleteError.value = ''
  try {
    await api(`/roles/${target.value.id}`, { method: 'DELETE' })
    target.value = null
    await refresh()
  } catch (problem) {
    deleteError.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
watch(target, () => {
  deleteError.value = ''
})
</script>

<template>
  <UContainer class="space-y-7 py-8 sm:py-12">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="mb-3 text-sm font-medium text-primary">
          Управление доступом
        </p><h1 class="text-3xl font-semibold text-highlighted">
          Роли
        </h1><p class="mt-3 text-muted">
          Наборы разрешений для вашей команды.
        </p>
      </div><UButton
        label="Новая роль"
        icon="i-lucide-plus"
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
      :columns="[{ accessorKey: 'name', header: 'Название' }, { id: 'permissions', header: 'Разрешения' }, { id: 'actions' }]"
      empty="Ролей пока нет"
      class="rounded-xl border border-default"
    >
      <template #name-cell="{ row }">
        <span class="font-medium text-highlighted">{{ row.original.name }}</span><UBadge
          v-if="row.original.protected"
          label="Системная"
          color="neutral"
          variant="subtle"
          size="xs"
          class="ml-2"
        />
      </template>
      <template #permissions-cell="{ row }">
        <div class="flex max-w-3xl flex-wrap gap-1">
          <UBadge
            v-for="permission in row.original.permissions"
            :key="permission"
            :label="permissionLabels[permission] || permission"
            color="neutral"
            variant="subtle"
            size="xs"
          />
        </div>
      </template>
      <template #actions-cell="{ row }">
        <div
          v-if="!row.original.protected"
          class="flex gap-1"
        >
          <UButton
            icon="i-lucide-pencil"
            :aria-label="`Изменить роль ${row.original.name}`"
            color="neutral"
            variant="ghost"
            @click="edit(row.original)"
          /><UButton
            icon="i-lucide-trash-2"
            :aria-label="`Удалить роль ${row.original.name}`"
            color="error"
            variant="ghost"
            @click="target = row.original"
          />
        </div>
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
      :title="selected ? `Роль ${selected.name}` : 'Новая роль'"
      description="Изменения сразу применяются к пользователям и их API-ключам."
      :dismissible="!saving"
      scrollable
      :ui="{ content: 'sm:max-w-xl' }"
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
            label="Название роли"
            name="name"
            required
          >
            <UInput
              v-model="state.name"
              :maxlength="64"
              required
              class="w-full"
            />
          </UFormField>
          <PageError
            v-if="permissionsError"
            :error="permissionsError"
            @retry="refreshPermissions()"
          />
          <UFormField
            label="Разрешения"
            name="permissions"
          >
            <UCheckboxGroup
              v-model="state.permissions"
              :items="permissionItems(permissions || [])"
            />
          </UFormField>
          <UButton
            type="submit"
            :label="selected ? 'Сохранить роль' : 'Создать роль'"
            :loading="saving"
            :disabled="!!permissionsError"
          />
        </UForm>
      </template>
    </UModal>
    <UModal
      v-model:open="deleting"
      title="Удалить роль?"
      :description="`Роль «${target?.name}» можно удалить, если она не назначена пользователям.`"
      :dismissible="!saving"
    >
      <template #body>
        <UAlert
          v-if="deleteError"
          :description="deleteError"
          color="error"
        /><p
          v-else
          class="text-sm text-muted"
        >
          Удалённую роль нельзя восстановить.
        </p>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            label="Отмена"
            color="neutral"
            variant="ghost"
            @click="target = null"
          /><UButton
            label="Удалить роль"
            color="error"
            :loading="saving"
            @click="remove"
          />
        </div>
      </template>
    </UModal>
  </UContainer>
</template>
