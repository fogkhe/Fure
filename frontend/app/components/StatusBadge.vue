<script setup lang="ts">
const props = defineProps<{
  status: string
}>()
const states = {
  ready: { label: 'Готова к запуску', color: 'success', icon: 'i-lucide-circle-check' },
  draft: { label: 'Без реализации', color: 'neutral', icon: 'i-lucide-file-dashed' },
  disabled: { label: 'Выключена', color: 'warning', icon: 'i-lucide-pause' },
  deleted: { label: 'Удалена', color: 'neutral', icon: 'i-lucide-archive' },
  pending: { label: 'В очереди', color: 'neutral', icon: 'i-lucide-clock-3' },
  running: { label: 'Выполняется', color: 'info', icon: 'i-lucide-loader-circle' },
  succeeded: { label: 'Успешно', color: 'success', icon: 'i-lucide-check' },
  failed: { label: 'Ошибка', color: 'error', icon: 'i-lucide-circle-alert' },
  cancelled: { label: 'Отменён', color: 'warning', icon: 'i-lucide-ban' }
} as const
const state = computed(() => states[props.status as keyof typeof states] ?? states.draft)
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
