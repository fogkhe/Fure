export default defineEventHandler(async (event) => {
  const path = getRouterParam(event, 'path') || ''
  if (!/^(v1\/(functions|revisions|runs|run|auth|users|roles|keys)(\/|$)|health$|openapi\.json$)/.test(path)) {
    throw createError({ statusCode: 404, statusMessage: 'Not found' })
  }
  const config = useRuntimeConfig(event)
  const target = `${config.apiBase.replace(/\/+$/, '')}/${path}${getRequestURL(event).search}`
  try {
    return await proxyRequest(event, target)
  } catch {
    throw createError({
      statusCode: 502,
      statusMessage: 'Backend unavailable',
      data: { detail: 'Could not connect to Fure API. Check that the backend is running.' }
    })
  }
})
