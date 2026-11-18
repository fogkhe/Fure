import { test as base, expect } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

export const password = 'fure-browser-test-password'

export async function login(request: APIRequestContext, username = 'admin') {
  const response = await request.post('/api/v1/auth/login', { data: { username, password }, headers: { 'X-Fure-Client': 'web' } })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

export const test = base.extend<{ interfaceLocale: 'en' | 'ru' | null }>({
  interfaceLocale: ['ru', { option: true }],
  context: async ({ context, interfaceLocale, baseURL }, use) => {
    if (interfaceLocale) await context.addCookies([{ name: 'fure_locale', value: interfaceLocale, url: baseURL! }])
    await use(context)
  },
  request: async ({ playwright, baseURL }, use) => {
    const guest = await playwright.request.newContext({ baseURL })
    const session = await login(guest)
    const request = await playwright.request.newContext({ baseURL, storageState: await guest.storageState(), extraHTTPHeaders: { 'X-CSRF-Token': session.csrf_token } })
    try {
      await use(request)
    } finally {
      await request.dispose()
      await guest.dispose()
    }
  }
})

export { expect }
