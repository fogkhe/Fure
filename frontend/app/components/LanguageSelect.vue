<script setup lang="ts">
const { locale, setLocale, t } = useI18n()
const switching = ref(false)
async function change(value: string) {
  if ((value !== 'en' && value !== 'ru') || value === locale.value || switching.value) return
  switching.value = true
  try {
    await setLocale(value)
  } finally {
    switching.value = false
  }
}
</script>

<template>
  <USelect
    :model-value="locale"
    :items="[{ label: 'English', value: 'en' }, { label: 'Русский', value: 'ru' }]"
    :aria-label="t('language.select')"
    :disabled="switching"
    icon="i-lucide-languages"
    variant="ghost"
    size="sm"
    class="w-32"
    @update:model-value="change"
  />
</template>
