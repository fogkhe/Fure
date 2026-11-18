<script setup lang="ts">
const { errorMessage } = useFormatting()
const { t } = useI18n()
defineProps<{
  error: unknown
}>()
defineEmits<{
  retry: []
}>()
</script>

<template>
  <UAlert
    :title="t('ui.couldNotLoadData')"
    :description="errorMessage(error)"
    color="error"
    variant="subtle"
    icon="i-lucide-wifi-off"
    :actions="[{ label: t('ui.retry'), color: 'error', variant: 'outline', onClick: () => $emit('retry') }]"
  />
</template>
