import type { SessionRecord, RunRecord } from '~/types/api'

export function useAuth() {
  const session = useState<SessionRecord | null>('session', () => null)
  const loaded = useState('session-loaded', () => false)
  const can = (permission: string) => session.value?.permissions.includes(permission) ?? false
  const home = () => can('functions.read') ? '/' : can('runs.read') ? '/runs' : '/account'
  const canCancel = (run: RunRecord) => run.user_id === session.value?.user.id ? can('runs.cancel') : can('runs.cancel_all')
  async function refresh() {
    try {
      session.value = await $fetch<SessionRecord>('/api/v1/auth/me', { retry: 0 })
    } catch (error) {
      if ((error as { statusCode?: number }).statusCode !== 401) throw error
      session.value = null
    }
    loaded.value = true
  }
  function clear() {
    session.value = null
    loaded.value = false
    clearNuxtData()
    useState<Record<string, string>>('function-names').value = {}
  }
  async function logout() {
    await useApi()('/auth/logout', { method: 'POST' })
    clear()
    await navigateTo('/login')
  }
  return { session, loaded, can, home, canCancel, refresh, clear, logout }
}
