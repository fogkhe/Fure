import { apiErrorKeys } from '~/utils/apiErrors'

export function useFormatting() {
  const { t, locale } = useI18n()
  const language = computed(() => locale.value === 'ru' ? 'ru-RU' : 'en-US')

  function formatDate(value: string | null | undefined) {
    if (!value) return '—'
    return new Intl.DateTimeFormat(language.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  }

  function formatDuration(value: number | null | undefined) {
    if (value == null) return '—'
    const milliseconds = value < 1
    const number = new Intl.NumberFormat(language.value, { maximumFractionDigits: milliseconds ? 0 : 2 }).format(milliseconds ? value * 1000 : value)
    return t(milliseconds ? 'format.milliseconds' : 'format.seconds', { value: number })
  }

  function translateDetail(detail: string) {
    const key = apiErrorKeys[detail]
    if (key) return t(`errors.${key}`)
    if (detail.startsWith('Permission required: ')) return t('errors.permissionRequired', { permission: detail.slice('Permission required: '.length) })
    return detail
  }

  function errorMessage(error: unknown): string {
    const problem = error as { data?: { detail?: unknown, data?: { detail?: string } }, message?: string }
    const detail = problem?.data?.detail ?? problem?.data?.data?.detail
    if (typeof detail === 'string') return translateDetail(detail)
    if (Array.isArray(detail)) {
      return detail.map((item: { loc?: (string | number)[], msg?: string }) => `${item.loc?.filter(part => part !== 'body').join('.') || t('errors.request')}: ${item.msg ? translateDetail(item.msg) : t('errors.invalidValue')}`).join('\n')
    }
    if (error instanceof SyntaxError) return t('ui.invalidJson')
    if (error instanceof Error && error.message === 'schema.objectRequired') return t('errors.schemaObjectRequired')
    if (error instanceof Error && !('data' in error) && error.name === 'Error' && !error.message.includes('fetch')) return translateDetail(error.message)
    return t('errors.requestFailed')
  }

  return { formatDate, formatDuration, errorMessage, translateDetail }
}
