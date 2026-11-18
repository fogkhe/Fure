<script setup lang="ts">
import type { SessionRecord } from '~/types/api'

const { errorMessage } = useFormatting()
const { t } = useI18n()

useSeoMeta({ title: () => t('ui.signIn') })
const auth = useAuth()
const state = reactive({ username: '', password: '' })
const saving = ref(false)
const error = ref('')
async function login() {
  saving.value = true
  error.value = ''
  try {
    auth.session.value = await $fetch<SessionRecord>('/api/v1/auth/login', {
      method: 'POST', retry: 0, headers: { 'X-Fure-Client': 'web' }, body: state
    })
    state.password = ''
    auth.loaded.value = true
    clearNuxtData()
    await navigateTo(auth.home())
  } catch (problem) {
    error.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UContainer class="flex min-h-[70vh] items-center justify-center py-12">
    <UCard class="w-full max-w-md">
      <template #header>
        <div class="mb-5 flex size-12 items-center justify-center rounded-xl bg-primary/10">
          <UIcon
            name="i-lucide-key-round"
            class="size-6 text-primary"
          />
        </div>
        <h1 class="text-2xl font-semibold text-highlighted">
          {{ t('ui.signInToFure') }}
        </h1>
        <p class="mt-2 text-sm text-muted">
          {{ t('ui.yourFunctionsVersionsAndRuns') }}
        </p>
      </template>
      <UForm
        :state="state"
        class="space-y-5"
        @submit="login"
      >
        <UAlert
          v-if="error"
          :description="error"
          color="error"
          icon="i-lucide-circle-alert"
        />
        <UFormField
          :label="t('ui.username')"
          name="username"
          required
        >
          <UInput
            v-model="state.username"
            autocomplete="username"
            autofocus
            required
            :disabled="saving"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('ui.password')"
          name="password"
          required
        >
          <UInput
            v-model="state.password"
            type="password"
            autocomplete="current-password"
            required
            :disabled="saving"
            class="w-full"
          />
        </UFormField>
        <UButton
          type="submit"
          :label="t('ui.signIn2')"
          icon="i-lucide-log-in"
          block
          :loading="saving"
        />
      </UForm>
      <template #footer>
        <p class="text-sm text-muted">
          {{ t('ui.accountsAreCreatedByAnAdministratorForInitialSetup') }} <code class="text-xs">python -m fure.cli create-admin admin</code>.
        </p>
      </template>
    </UCard>
  </UContainer>
</template>
