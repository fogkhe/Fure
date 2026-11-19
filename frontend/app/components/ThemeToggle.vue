<script setup lang="ts">
const { t } = useI18n()
const colorMode = useColorMode()
let transitioning = false

async function toggle(event: MouseEvent) {
  if (transitioning || colorMode.forced) return

  const preference = colorMode.value === 'dark' ? 'light' : 'dark'
  const button = event.currentTarget
  if (!(button instanceof HTMLElement) || !document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) {
    colorMode.preference = preference
    return
  }

  const { left, top, width, height } = button.getBoundingClientRect()
  const x = left + width / 2
  const y = top + height / 2
  const root = document.documentElement
  const radius = Math.hypot(Math.max(x, root.clientWidth - x), Math.max(y, root.clientHeight - y))
  transitioning = true
  root.style.setProperty('--theme-reveal-origin', `${x}px ${y}px`)
  root.style.setProperty('--theme-reveal-radius', `${Math.ceil(radius)}px`)
  root.setAttribute('data-theme-reveal', '')

  try {
    const transition = document.startViewTransition(async () => {
      colorMode.preference = preference
      await nextTick()
    })
    // The browser can skip the animation, for instance when the tab is hidden.
    void transition.ready.catch(() => {})
    await transition.finished
  } catch {
    colorMode.preference = preference
  } finally {
    root.removeAttribute('data-theme-reveal')
    root.style.removeProperty('--theme-reveal-origin')
    root.style.removeProperty('--theme-reveal-radius')
    transitioning = false
  }
}
</script>

<template>
  <UButton
    type="button"
    size="sm"
    color="neutral"
    variant="ghost"
    square
    :aria-label="t('ui.switchTheme')"
    :disabled="colorMode.forced"
    @click="toggle"
  >
    <UIcon
      name="i-lucide-sun"
      class="size-5 dark:hidden"
    />
    <UIcon
      name="i-lucide-moon"
      class="hidden size-5 dark:block"
    />
  </UButton>
</template>
