export default defineEventHandler(async (event) => {
  const path = getRouterParam(event, 'path') || ''
  if (!/^(v1\/(functions|revisions|runs|run|auth|users|roles|keys|variables)(\/|$)|health$|docs$|openapi\.json$)/.test(path)) {
    throw createError({ statusCode: 404, statusMessage: 'Not found' })
  }
  const config = useRuntimeConfig(event)
  const target = `${config.apiBase.replace(/\/+$/, '')}/${path}${getRequestURL(event).search}`
  try {
    if (path === 'openapi.json' && (event.method === 'GET' || event.method === 'HEAD')) {
      const schema = await $fetch<Record<string, unknown>>(target, { retry: 0 })
      return { ...schema, servers: [{ url: '/api' }] }
    }
    return await proxyRequest(event, target)
  } catch {
    throw createError({
      statusCode: 502,
      statusMessage: 'Backend unavailable',
      data: { detail: 'Could not connect to Fure API. Check that the backend is running.' }
    })
  }
})
