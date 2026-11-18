import { expect, test, login, password } from './fixtures'
import type { APIRequestContext, Page } from '@playwright/test'

const python = 'from pydantic import BaseModel\n\nclass Input(BaseModel):\n    name: str\n\nasync def function(input: Input) -> str:\n    return f"Hello, {input.name}!"\n'

async function seed(request: APIRequestContext, name: string, code: string, timeout: number | null = 30) {
  const response = await request.post('/api/v1/functions', { data: { name } })
  expect(response.ok()).toBeTruthy()
  const record = await response.json()
  const revisionResponse = await request.post('/api/v1/revisions', { data: { function_id: record.id, implementation: { type: 'python', code }, runner_options: { type: 'inline_python', timeout } } })
  expect(revisionResponse.ok()).toBeTruthy()
  const revision = await revisionResponse.json()
  expect((await request.patch(`/api/v1/functions/${record.id}`, { data: { revision_id: revision.id } })).ok()).toBeTruthy()
  return { record, revision }
}

async function run(page: Page) {
  await page.getByRole('tab', { name: 'Запустить', exact: true }).click()
  await page.getByRole('button', { name: 'Запустить', exact: true }).click()
}

test.beforeEach(async ({ context }) => {
  await login(context.request)
})

test('workspace icons render without runtime icon requests', async ({ page, request }) => {
  const response = await request.post('/api/v1/functions', { data: { name: 'draft_icons_ui' } })
  expect(response.status()).toBe(201)
  const iconRequests: string[] = []
  await page.route(/\/(?:api\/_nuxt_icon\/|api\.iconify\.design\/)/, (route) => {
    iconRequests.push(route.request().url())
    return route.abort()
  })
  await page.goto('/')
  const logout = page.getByRole('button', { name: 'Выйти', exact: true }).locator('.iconify')
  const draft = page.getByRole('link', { name: 'draft_icons_ui', exact: true }).getByText('Без реализации', { exact: true }).locator('.iconify')
  for (const icon of [logout, draft]) {
    await expect(icon).toBeVisible()
    await expect.poll(() => icon.evaluate(element => getComputedStyle(element).maskImage)).toContain('data:image/svg+xml')
  }
  expect(iconRequests).toEqual([])
})

test('create, version, execute, rename, delete and restore a function', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await page.getByRole('button', { name: 'Новая функция', exact: true }).first().click()
  const create = page.getByRole('dialog')
  await create.getByLabel('Имя функции').fill('greet_ui')
  await create.getByLabel('Описание').fill('Приветствие с историей версий')
  await create.getByRole('button', { name: 'Создать функцию' }).click()
  const editor = page.getByRole('dialog')
  await expect(editor.getByRole('textbox', { name: 'Python-код' })).toHaveValue(/async def function/)
  await editor.getByRole('button', { name: 'Сохранить версию' }).click()
  await expect(editor).not.toBeVisible()
  await expect(page.getByText('Готова к запуску', { exact: true })).toBeVisible()
  await run(page)
  await expect(page.getByText('Hello, world!', { exact: true })).toBeVisible()
  const detailLink = page.getByRole('link', { name: 'Открыть запись запуска' })
  await expect(detailLink).toHaveAttribute('href', /\/runs\/.+/)
  await page.evaluate(() => window.scrollTo(0, 0))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
  await page.screenshot({ path: info.outputPath('execution-desktop.png'), fullPage: true })
  await detailLink.click()
  await expect(page.getByText('Успешно', { exact: true })).toBeVisible()
  await expect(page.getByText('Hello, world!', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'greet_ui', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Новая версия', exact: true })).toHaveCount(0)
  await page.getByRole('tab', { name: 'Версии', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Новая версия', exact: true })).toHaveCount(1)
  await page.getByRole('button', { name: 'Новая версия', exact: true }).click()
  await page.getByRole('textbox', { name: 'Python-код' }).fill(python.replace('Hello', 'Goodbye'))
  await page.getByLabel('Сделать текущей версией').uncheck()
  const created = page.waitForResponse(response => response.url().endsWith('/api/v1/revisions') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Сохранить версию' }).click()
  const version = await (await created).json()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.getByRole('tab', { name: 'Версии', exact: true }).click()
  await page.getByRole('button').filter({ hasText: `#${version.id.slice(-8)}` }).click()
  await page.getByRole('button', { name: 'Выбрать текущей' }).click()
  await expect(page.getByRole('button', { name: 'Выбрать текущей' })).not.toBeVisible()
  await run(page)
  await expect(page.getByText('Goodbye, world!', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Настройки', exact: true }).click()
  await page.getByLabel('Имя функции').fill('greet_renamed')
  await page.getByRole('switch', { name: 'Функция включена' }).uncheck()
  await page.getByRole('button', { name: 'Сохранить изменения' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('greet_renamed')
  await page.getByRole('tab', { name: 'Запустить', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Запустить', exact: true })).toBeDisabled()
  await page.getByRole('tab', { name: 'Настройки', exact: true }).click()
  await page.getByRole('button', { name: 'Удалить функцию', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(page.getByText('Удалена', { exact: true })).toBeVisible()
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Статус функций' }).click()
  await page.getByRole('option', { name: 'Удалённые', exact: true }).click()
  await page.getByRole('link', { name: 'greet_renamed', exact: true }).click()
  await page.getByRole('tab', { name: 'Настройки', exact: true }).click()
  await page.getByRole('button', { name: 'Восстановить', exact: true }).click()
  await expect(page.getByText('Функция удалена', { exact: true })).not.toBeVisible()
  await page.getByRole('tab', { name: 'История', exact: true }).click()
  await expect(page.getByRole('table')).toContainText('Успешно')
  expect(errors).toEqual([])
})

test('execution failures keep their history and run identifier', async ({ page, request }) => {
  const { record } = await seed(request, 'failed_ui', 'async def function(input: None) -> str:\n    raise ValueError("example failure")\n')
  await page.goto(`/functions/${record.id}`)
  await run(page)
  await expect(page.getByText('Не удалось выполнить запуск', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Открыть запись запуска' }).click()
  await expect(page.getByText('Ошибка', { exact: true })).toBeVisible()
  await expect(page.getByText('execution_error', { exact: true }).first()).toBeVisible()
})

test('active execution can be cancelled from history', async ({ page, context, request }) => {
  const { record } = await seed(request, 'cancel_ui', 'import asyncio\n\nasync def function(input: None) -> str:\n    await asyncio.sleep(60)\n    return "done"\n', null)
  await page.goto(`/functions/${record.id}`)
  const response = page.waitForResponse(value => value.url().includes(`/api/v1/functions/${record.id}/run`) && value.request().method() === 'POST')
  await run(page)
  expect((await response).status()).toBe(202)
  const history = await context.newPage()
  await history.goto(`/runs?function_id=${record.id}`)
  await expect(history.getByText('Выполняется', { exact: true })).toBeVisible()
  await history.getByRole('button', { name: 'Отменить запуск', exact: true }).click()
  await history.getByRole('dialog').getByRole('button', { name: 'Отменить запуск', exact: true }).click()
  await expect(history.getByText('Отменён', { exact: true })).toBeVisible()
  await expect(page.getByText('Запуск отменён', { exact: true })).toBeVisible()
  await history.getByRole('link', { name: 'Открыть запуск', exact: true }).click()
  await expect(history.getByText('Отменён', { exact: true })).toBeVisible()
})

test('run panel cancels its own execution and supports retry after cancellation errors', async ({ page, request }) => {
  const { record } = await seed(request, 'cancel_panel_ui', 'import asyncio\n\nasync def function(input: None) -> str:\n    await asyncio.sleep(60)\n    return "done"\n', null)
  await page.goto(`/functions/${record.id}`)
  const submitted = page.waitForResponse(response => response.url().includes(`/api/v1/functions/${record.id}/run`) && response.request().method() === 'POST')
  await run(page)
  const response = await submitted
  expect(response.status()).toBe(202)
  const execution = await response.json()
  const cancelButton = page.getByRole('button', { name: 'Отменить', exact: true })
  await expect(cancelButton).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Запустить', exact: true })).toHaveCount(0)
  await cancelButton.click()
  const dialog = page.getByRole('dialog', { name: 'Отменить запуск?' })
  await dialog.getByRole('button', { name: 'Назад', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(cancelButton).toBeEnabled()
  const cancelUrl = `**/api/v1/runs/${execution.id}/cancel`
  await page.route(cancelUrl, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary cancellation failure' }) }))
  await cancelButton.click()
  await dialog.getByRole('button', { name: 'Отменить запуск', exact: true }).click()
  await expect(page.getByText('Не удалось отменить запуск', { exact: true })).toBeVisible()
  expect((await (await request.get(`/api/v1/runs/${execution.id}`)).json()).status).toMatch(/pending|running/)
  await page.unroute(cancelUrl)
  await dialog.getByRole('button', { name: 'Отменить запуск', exact: true }).click()
  await expect(page.getByText('Запуск отменён', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Запустить', exact: true })).toBeEnabled()
  expect((await (await request.get(`/api/v1/runs/${execution.id}`)).json()).status).toBe('cancelled')
  const next = page.waitForResponse(value => value.url().includes(`/api/v1/functions/${record.id}/run`) && value.request().method() === 'POST')
  await run(page)
  const nextExecution = await (await next).json()
  expect(nextExecution.id).not.toBe(execution.id)
  await expect(page.getByText('Запуск отменён', { exact: true })).toHaveCount(0)
  await request.post(`/api/v1/runs/${nextExecution.id}/cancel`)
  await expect(page.getByText('Запуск отменён', { exact: true })).toBeVisible()
})

test('run panel respects cancellation and history permissions', async ({ page, context, request }) => {
  const { record } = await seed(request, 'limited_panel_ui', 'import asyncio\n\nasync def function(input: None) -> str:\n    await asyncio.sleep(1)\n    return "limited result"\n', null)
  for (const history of [true, false]) {
    const permissions = ['functions.read', 'functions.run', ...(history ? ['runs.read'] : [])]
    const roleResponse = await request.post('/api/v1/roles', { data: { name: `panel-${history}`, permissions } })
    expect(roleResponse.status()).toBe(201)
    const role = await roleResponse.json()
    const username = `panel-${history}`
    expect((await request.post('/api/v1/users', { data: { username, password, role_ids: [role.id] } })).status()).toBe(201)
    await login(context.request, username)
    await page.goto(`/functions/${record.id}`)
    const completed = page.waitForResponse(response => response.url().includes(`/api/v1/functions/${record.id}/run`) && response.request().method() === 'POST')
    await run(page)
    await expect(page.getByRole('button', { name: 'Отменить', exact: true })).toHaveCount(0)
    expect((await completed).status()).toBe(history ? 202 : 200)
    await expect(page.getByText('limited result', { exact: true })).toBeVisible()
  }
})

test('Jinja editor derives input schema and stores structured output options', async ({ page, request }) => {
  const functionResponse = await request.post('/api/v1/functions', { data: { name: 'jinja_ui' } })
  const record = await functionResponse.json()
  await page.goto(`/functions/${record.id}`)
  await page.getByRole('tab', { name: 'Версии', exact: true }).click()
  await page.getByRole('button', { name: 'Новая версия', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('combobox', { name: 'Реализация', exact: true }).click()
  await page.getByRole('option', { name: 'Jinja · OpenAI', exact: true }).click()
  await dialog.getByRole('textbox', { name: 'Jinja-шаблон' }).fill('Hello {{ name }}')
  await dialog.getByLabel('Адрес API').fill('http://127.0.0.1:9/v1')
  await dialog.getByLabel('Модель', { exact: true }).fill('test-model')
  await dialog.getByLabel('API ключ', { exact: true }).fill('fure-e2e-secret')
  const mode = dialog.getByRole('combobox', { name: 'Редактор схемы', exact: true })
  await expect(mode).toContainText('Поля')
  await dialog.getByRole('button', { name: 'Добавить поле', exact: true }).click()
  await dialog.getByLabel('Имя поля', { exact: true }).fill('greetings')
  await dialog.getByRole('combobox', { name: 'Тип', exact: true }).click()
  await page.getByRole('option', { name: 'Массив', exact: true }).click()
  const item = dialog.getByRole('group', { name: 'Схема элемента массива', exact: true })
  await item.getByRole('combobox', { name: 'Тип', exact: true }).click()
  await page.getByRole('option', { name: 'Объект', exact: true }).click()
  await item.getByRole('button', { name: 'Добавить поле', exact: true }).click()
  await item.getByLabel('Имя поля', { exact: true }).fill('greeting')
  const field = item.getByRole('group', { name: 'Поле 1', exact: true })
  await field.getByRole('checkbox', { name: 'Разрешить null', exact: true }).check()
  const allowed = field.getByPlaceholder('Введите значение и нажмите Enter')
  await allowed.fill('hello')
  await allowed.press('Enter')
  const schema = {
    type: 'object',
    properties: {
      greetings: {
        type: 'array',
        items: {
          type: 'object',
          properties: { greeting: { type: ['string', 'null'], enum: ['hello', null] } },
          required: ['greeting'],
          additionalProperties: false
        }
      }
    },
    required: ['greetings'],
    additionalProperties: false
  }
  await mode.click()
  await page.getByRole('option', { name: 'JSON', exact: true }).click()
  const schemaJson = dialog.getByRole('textbox', { name: 'Выходная схема', exact: true })
  await expect(schemaJson).toHaveValue(JSON.stringify(schema, null, 2))
  await mode.click()
  await page.getByRole('option', { name: 'Поля', exact: true }).click()
  const saved = page.waitForResponse(response => response.url().endsWith('/api/v1/revisions') && response.request().method() === 'POST')
  await dialog.getByRole('button', { name: 'Сохранить версию' }).click()
  const revision = await (await saved).json()
  expect(revision.implementation.input_schema).toMatchObject({ type: 'object', required: ['name'] })
  expect(revision.implementation.input_schema.properties).toHaveProperty('name')
  expect(revision.implementation.output_schema).toEqual(schema)
  expect(revision.runner_options).not.toHaveProperty('api_key')
  expect(revision.runner_options.structured_outputs).toBe(true)
  expect(revision.runner_options.reasoning_end_tags).toEqual([])
  await expect(dialog).not.toBeVisible()
  await page.getByRole('button', { name: 'Новая версия', exact: true }).click()
  await expect(page.getByLabel('API ключ', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('Модель', { exact: true })).toHaveValue('test-model')
  await expect(item.getByLabel('Имя поля', { exact: true })).toHaveValue('greeting')
})

test('mobile layout, theme and recoverable API errors', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('functions-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: 'Переключить тему' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.screenshot({ path: info.outputPath('functions-dark.png'), fullPage: true })
  await page.route('**/api/v1/functions?**', route => route.abort('connectionrefused'))
  await page.reload()
  await expect(page.getByRole('button', { name: 'Повторить', exact: true })).toBeVisible()
  await page.unroute('**/api/v1/functions?**')
  await page.getByRole('button', { name: 'Повторить', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Повторить', exact: true })).not.toBeVisible()
})
