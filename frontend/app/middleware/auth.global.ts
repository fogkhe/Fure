export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return
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
