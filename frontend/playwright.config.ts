import { defineConfig, devices } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const data = fileURLToPath(new URL('./.data', import.meta.url))
mkdirSync(data, { recursive: true })
const python = `${root}.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`
const database = `${data}/e2e-${Date.now()}.db`.replaceAll('\\', '/')

export default defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  timeout: 90000,
  expect: { timeout: 10000 },
  use: {
    ...devices['Desktop Chrome'],
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    baseURL: 'http://127.0.0.1:3011',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  webServer: [
    {
      command: `"${python}" -m tests.e2e_server`,
      cwd: root,
      env: { DATABASE_URL: `sqlite+aiosqlite:///${database}` },
      url: 'http://127.0.0.1:8011/health',
      reuseExistingServer: false
    },
    {
      command: 'node .output/server/index.mjs',
      env: { NUXT_API_BASE: 'http://127.0.0.1:8011', HOST: '127.0.0.1', PORT: '3011' },
      url: 'http://127.0.0.1:3011',
      reuseExistingServer: false
    }
  ]
})
