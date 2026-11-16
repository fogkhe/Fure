<script setup lang="ts">
import type { FormError } from '@nuxt/ui'
import type { FunctionRecord } from '~/types/api'

const open = defineModel<boolean>('open', { default: false })
const api = useApi()
const auth = useAuth()
const state = reactive({ name: '', description: '' })
const saving = ref(false)
const error = ref('')
watch(open, (value) => {
  if (value) {
    state.name = ''
    state.description = ''
    error.value = ''
  }
})
function validate(): FormError[] {
  const errors: FormError[] = []
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(state.name))
    errors.push({ name: 'name', message: 'От 1 до 64 латинских букв, цифр, дефисов или подчёркиваний.' })
  if (state.description.length > 1000)
    errors.push({ name: 'description', message: 'Максимум 1000 символов.' })
  return errors
}
async function create() {
  if (saving.value)
    return
  saving.value = true
  error.value = ''
  try {
    const record = await api<FunctionRecord>('/functions', { method: 'POST', body: { name: state.name, description: state.description || null } })
    open.value = false
    await navigateTo(`/functions/${record.id}${auth.can('functions.update') ? '?newRevision=1' : ''}`)
  } catch (problem) {
    error.value = errorMessage(problem)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Новая функция"
    description="Задайте имя, затем добавьте реализацию на Python или Jinja."
    :dismissible="!saving"
  >
    <template #body>
      <UForm
        :state="state"
        :validate="validate"
        class="space-y-5"
        @submit="create"
      >
        <UAlert
          v-if="error"
          :description="error"
          color="error"
          icon="i-lucide-circle-alert"
        />
        <UFormField
          label="Имя функции"
          name="name"
          required
          description="Это имя будет использоваться для запуска через API."
        >
          <UInput
            v-model="state.name"
            placeholder="Например, greet"
            autofocus
            class="w-full"
            :disabled="saving"
          />
        </UFormField>
        <UFormField
          label="Описание"
          name="description"
          hint="Необязательно"
        >
          <UTextarea
            v-model="state.description"
            placeholder="Что делает эта функция?"
            :rows="3"
            class="w-full"
            :disabled="saving"
          />
        </UFormField>
        <div class="flex justify-end gap-2">
          <UButton
            label="Отмена"
            color="neutral"
            variant="ghost"
            :disabled="saving"
            @click="open = false"
          /><UButton
            type="submit"
            label="Создать функцию"
            icon="i-lucide-plus"
            :loading="saving"
          />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
