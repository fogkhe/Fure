<script setup lang="ts">
import type { Page, RoleRecord, UserRecord } from '~/types/api'

const { formatDate, errorMessage } = useFormatting()
const { t } = useI18n()

useSeoMeta({ title: () => t('ui.users') })
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
          {{ t('ui.accessManagement') }}
        </p><h1 class="text-3xl font-semibold text-highlighted">
          {{ t('ui.users') }}
        </h1><p class="mt-3 text-muted">
          {{ t('ui.assignRolesAndManageAccessToTheSharedCatalogue') }}
        </p>
      </div>
      <UButton
        :label="t('ui.newUser')"
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
      :loading="status === 'idle' || status === 'pending'"
      :columns="[{ accessorKey: 'username', header: t('ui.username') }, { id: 'roles', header: t('ui.roles') }, { id: 'status', header: t('ui.status') }, { id: 'created', header: t('ui.created') }, { id: 'actions' }]"
      :empty="t('ui.noUsersFound')"
      class="rounded-xl border border-default"
    >
      <template #username-cell="{ row }">
        <span class="font-medium text-highlighted">{{ row.original.username }}</span><UBadge
          v-if="row.original.id === auth.session.value?.user.id"
          :label="t('ui.you')"
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
          :label="row.original.enabled ? t('ui.active') : t('ui.blocked')"
          :color="row.original.enabled ? 'success' : 'neutral'"
          variant="subtle"
        />
      </template>
      <template #created-cell="{ row }">
        {{ formatDate(row.original.created_at) }}
      </template>
      <template #actions-cell="{ row }">
        <UButton
          :label="t('ui.edit')"
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
      :title="selected ? t('ui.user', { value1: selected.username }) : t('ui.newUser')"
      :description="t('ui.permissionsFromAllAssignedRolesAreCombined')"
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
            :label="t('ui.username')"
            name="username"
            :description="t('ui.lowercaseLatinLettersDigitsDotsHyphensAndUnderscores')"
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
            :label="selected ? t('ui.newPassword') : t('ui.password')"
            name="password"
            :required="!selected"
            :description="selected ? t('ui.leaveEmptyToKeepTheCurrentPasswordSettingA') : t('ui.use12256Characters')"
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
            :label="t('ui.roles')"
            name="role_ids"
          >
            <UCheckboxGroup
              v-model="state.role_ids"
              :items="roles?.items.map(role => ({ label: role.name, value: role.id })) || []"
            />
          </UFormField>
          <USwitch
            v-model="state.enabled"
            :label="t('ui.userEnabled')"
            :description="t('ui.blockingEndsAllSessionsAndRevokesAllApiKeys')"
          />
          <UButton
            type="submit"
            :label="selected ? t('ui.saveUser') : t('ui.createUser')"
            :loading="saving"
            :disabled="!!rolesError"
          />
        </UForm>
      </template>
    </UModal>
  </UContainer>
</template>
