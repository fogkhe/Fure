<script setup lang="ts">
defineProps<{
  error: unknown
}>()
defineEmits<{
  retry: []
}>()
</script>

<template>
  <UAlert
    title="Не удалось загрузить данные"
    :description="errorMessage(error)"
    color="error"
    variant="subtle"
    icon="i-lucide-wifi-off"
    :actions="[{ label: 'Повторить', color: 'error', variant: 'outline', onClick: () => $emit('retry') }]"
  />
</template>
