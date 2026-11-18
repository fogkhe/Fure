<script setup lang="ts">
const { t } = useI18n()
const props = defineProps<{
  value: unknown
  title?: string
  text?: boolean
}>()
const toast = useToast()
const content = computed(() => props.value === undefined ? '—' : props.text && typeof props.value === 'string' ? props.value : (JSON.stringify(props.value, null, 2) ?? '—'))
async function copy() {
  try {
    await navigator.clipboard.writeText(content.value)
    toast.add({ title: t('ui.copied'), icon: 'i-lucide-check', color: 'success' })
  } catch {
    toast.add({ title: t('ui.couldNotCopy'), description: t('ui.selectAndCopyTheTextManually'), color: 'error' })
  }
}
</script>

<template>
  <div class="overflow-hidden rounded-xl border border-default bg-elevated/30">
    <div class="flex items-center justify-between gap-3 border-b border-default px-4 py-2.5">
      <span class="text-xs font-medium tracking-wide text-muted">{{ title || 'JSON' }}</span>
      <UButton
        icon="i-lucide-copy"
        color="neutral"
        variant="ghost"
        size="xs"
        :aria-label="t('ui.copy')"
        @click="copy"
      />
    </div>
    <pre
      class="max-h-96 overflow-auto p-4 text-sm leading-6 whitespace-pre-wrap break-words"
      :class="{ 'font-sans': text }"
    >{{ content }}</pre>
  </div>
</template>
