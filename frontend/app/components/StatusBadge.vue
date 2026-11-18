<script setup lang="ts">
const { t } = useI18n()
const props = defineProps<{
  status: string
}>()
const states = computed(() => ({
  ready: { label: t('ui.readyToRun'), color: 'success', icon: 'i-lucide-circle-check' },
  draft: { label: t('ui.noImplementation'), color: 'neutral', icon: 'i-lucide-file' },
  disabled: { label: t('ui.disabled'), color: 'warning', icon: 'i-lucide-pause' },
  deleted: { label: t('ui.deleted'), color: 'neutral', icon: 'i-lucide-archive' },
  pending: { label: t('ui.pending'), color: 'neutral', icon: 'i-lucide-clock-3' },
  running: { label: t('ui.running2'), color: 'info', icon: 'i-lucide-loader-circle' },
  succeeded: { label: t('ui.succeeded2'), color: 'success', icon: 'i-lucide-check' },
  failed: { label: t('ui.failed2'), color: 'error', icon: 'i-lucide-circle-alert' },
  cancelled: { label: t('ui.cancelled2'), color: 'warning', icon: 'i-lucide-ban' }
} as const))
const state = computed(() => states.value[props.status as keyof typeof states.value] ?? states.value.draft)
</script>

<template>
  <UBadge
    :color="state.color"
    variant="subtle"
    :icon="state.icon"
    :class="{ 'animate-pulse': status === 'running' }"
  >
    {{ state.label }}
  </UBadge>
</template>
