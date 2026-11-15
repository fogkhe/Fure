export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function formatDuration(value: number | null | undefined) {
  if (value == null) return '—'
  return value < 1 ? `${Math.round(value * 1000)} мс` : `${value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} с`
}

export function shortId(value: string) {
  return value.slice(-8)
}

export function errorMessage(error: unknown): string {
  const problem = error as { data?: { detail?: unknown, data?: { detail?: string } }, message?: string }
  const detail = problem?.data?.detail ?? problem?.data?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item: { loc?: (string | number)[], msg?: string }) => `${item.loc?.filter(part => part !== 'body').join('.') || 'Запрос'}: ${item.msg || 'некорректное значение'}`).join('\n')
  }
  return 'Не удалось выполнить запрос. Проверьте подключение к API и попробуйте ещё раз.'
}
