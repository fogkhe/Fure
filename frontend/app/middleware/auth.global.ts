export default defineNuxtRouteMiddleware(async (to) => {
  const nuxtApp = useNuxtApp()
  // Keep the first client render consistent with the route and session that SSR
  // already resolved. Subsequent navigations refresh permissions as usual.
  if (import.meta.client && nuxtApp.isHydrating && nuxtApp.payload.serverRendered) return
  if (import.meta.server) useResponseHeader('Cache-Control').value = 'no-store'
  const auth = useAuth()
  try {
    await auth.refresh()
  } catch {
    // Let the page show a recoverable connection error, rather than logging out.
    return
  }
  if (!auth.session.value && to.path !== '/login')
    return navigateTo('/login')
  if (auth.session.value && to.path === '/login')
    return navigateTo(auth.home())
  if (to.path === '/variables' && !auth.can('variables.read') && !auth.can('variables.manage'))
    return navigateTo('/account')
  const permission = to.path === '/' || to.path.startsWith('/functions/')
    ? 'functions.read'
    : to.path.startsWith('/runs')
      ? 'runs.read'
      : to.path === '/users'
        ? 'users.manage'
        : to.path === '/roles' ? 'roles.manage' : null
  if (permission && auth.session.value && !auth.can(permission))
    return navigateTo('/account')
})
