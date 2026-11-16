export function useApi() {
  const auth = useAuth()
  return $fetch.create({
    baseURL: '/api/v1',
    retry: 0,
    onRequest({ options }) {
      if (auth.session.value?.csrf_token)
        options.headers.set('X-CSRF-Token', auth.session.value.csrf_token)
    },
    async onResponseError({ response }) {
      if (response.status === 401 && import.meta.client) {
        auth.clear()
        await navigateTo('/login')
      }
    }
  })
}
