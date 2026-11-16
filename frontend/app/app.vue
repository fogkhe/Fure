<script setup lang="ts">
import { ru } from '@nuxt/ui/locale'
import type { NavigationMenuItem } from '@nuxt/ui'

useHead({
  titleTemplate: '%s · Fure',
  htmlAttrs: { lang: 'ru' },
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }]
})
useSeoMeta({ description: 'Функции, версии реализаций и история запусков в одном месте.' })
const auth = useAuth()
const toast = useToast()
const items = computed<NavigationMenuItem[]>(() => [
  ...(auth.can('functions.read') ? [{ label: 'Функции', icon: 'i-lucide-square-function', to: '/', exact: true }] : []),
  ...(auth.can('runs.read') ? [{ label: 'Запуски', icon: 'i-lucide-activity', to: '/runs' }] : []),
  ...(auth.can('users.manage') ? [{ label: 'Пользователи', icon: 'i-lucide-users', to: '/users' }] : []),
  ...(auth.can('roles.manage') ? [{ label: 'Роли', icon: 'i-lucide-shield', to: '/roles' }] : [])
])
async function logout() {
  try {
    await auth.logout()
  } catch (problem) {
    toast.add({ title: 'Не удалось выйти', description: errorMessage(problem), color: 'error' })
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
    :locale="ru"
    :toaster="{ position: 'bottom-right' }"
  >
    <UHeader>
      <template #left>
        <NuxtLink
          to="/"
          aria-label="Fure — главная"
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
        <UTooltip :text="error ? 'Проверить подключение к API' : 'Соединение с Fure API'">
          <UButton
            :label="error ? 'API недоступен' : health ? 'API подключен' : 'Подключение…'"
            :color="error ? 'error' : health ? 'primary' : 'neutral'"
            variant="ghost"
            size="xs"
            icon="i-lucide-circle"
            class="hidden md:inline-flex"
            @click="refresh()"
          />
        </UTooltip>
        <UColorModeButton aria-label="Переключить тему" />
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
          aria-label="Выйти"
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
        <p class="text-xs text-muted">
          Fure <span class="mx-2 text-dimmed">/</span> Function Runtime Environment
        </p>
      </template>
      <template #right>
        <UButton
          to="/api/openapi.json"
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
