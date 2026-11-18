<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { errorMessage } = useFormatting()
const { t, locale } = useI18n()
useHead(() => ({
  titleTemplate: '%s · Fure',
  htmlAttrs: { lang: locale.value },
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }]
}))
useSeoMeta({ description: () => t('ui.functionsImplementationVersionsAndRunHistoryInOnePlace') })
const auth = useAuth()
const toast = useToast()
const items = computed<NavigationMenuItem[]>(() => [
  ...(auth.can('functions.read') ? [{ label: t('ui.functions'), icon: 'i-lucide-square-function', to: '/', exact: true }] : []),
  ...(auth.can('runs.read') ? [{ label: t('ui.runs'), icon: 'i-lucide-activity', to: '/runs' }] : []),
  ...(auth.can('users.manage') ? [{ label: t('ui.users'), icon: 'i-lucide-users', to: '/users' }] : []),
  ...(auth.can('roles.manage') ? [{ label: t('ui.roles'), icon: 'i-lucide-shield', to: '/roles' }] : [])
])
async function logout() {
  try {
    await auth.logout()
  } catch (problem) {
    toast.add({ title: t('ui.couldNotSignOut'), description: errorMessage(problem), color: 'error' })
  }
}
const { data: health, error, refresh } = await useAsyncData('api-health', () => $fetch<{
  status: string
}>('/api/health', { retry: 0 }), { server: false })
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (document.visibilityState === 'visible')
      refresh()
  }, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <UApp
    :toaster="{ position: 'bottom-right' }"
  >
    <UHeader>
      <template #left>
        <NuxtLink
          to="/"
          :aria-label="t('ui.fureHome')"
          class="rounded-md focus-visible:outline-2 focus-visible:outline-primary"
        >
          <AppLogo />
        </NuxtLink>
        <UBadge
          label="workspace"
          color="neutral"
          variant="subtle"
          size="xs"
          class="hidden sm:inline-flex"
        />
      </template>
      <UNavigationMenu :items="items" />
      <template #right>
        <UTooltip :text="error ? t('ui.checkApiConnection') : t('ui.connectionToFureApi')">
          <UButton
            :label="error ? t('ui.apiUnavailable') : health ? t('ui.apiConnected') : t('ui.connecting')"
            :color="error ? 'error' : health ? 'primary' : 'neutral'"
            variant="ghost"
            size="xs"
            icon="i-lucide-circle"
            class="hidden md:inline-flex"
            @click="refresh()"
          />
        </UTooltip>
        <UColorModeButton :aria-label="t('ui.switchTheme')" />
        <UButton
          v-if="auth.session.value"
          to="/account"
          :label="auth.session.value.user.username"
          icon="i-lucide-user-round"
          color="neutral"
          variant="ghost"
          size="sm"
        />
        <UButton
          v-if="auth.session.value"
          icon="i-lucide-log-out"
          :aria-label="t('ui.signOut')"
          color="neutral"
          variant="ghost"
          @click="logout"
        />
      </template>
      <template #body>
        <UNavigationMenu
          :items="items"
          orientation="vertical"
        />
      </template>
    </UHeader>
    <UMain><NuxtPage /></UMain>
    <USeparator />
    <UFooter>
      <template #left>
        <LanguageSelect />
      </template>
      <template #right>
        <UButton
          to="/api/openapi.json"
          external
          target="_blank"
          label="OpenAPI"
          trailing-icon="i-lucide-arrow-up-right"
          size="xs"
          color="neutral"
          variant="ghost"
        />
      </template>
    </UFooter>
  </UApp>
</template>
