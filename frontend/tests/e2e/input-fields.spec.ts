import { expect, test, login } from './fixtures'
import type { APIRequestContext, Page } from '@playwright/test'

test.use({ interfaceLocale: 'en' })

const code = `from typing import Literal
from pydantic import BaseModel

class Address(BaseModel):
    city: str

class Input(BaseModel):
    name: str
    count: int
    active: bool
    mode: Literal["brief", "full"]
    address: Address
    tags: list[str]
    note: str | None = None
    extra: dict = {}

async def function(input: Input) -> dict:
    return input.model_dump()
`

async function seed(request: APIRequestContext, name: string, source = code) {
  const response = await request.post('/api/v1/functions', { data: { name } })
  expect(response.ok()).toBeTruthy()
  const record = await response.json()
  const created = await request.post('/api/v1/revisions', { data: { function_id: record.id, implementation: { type: 'python', code: source }, runner_options: { type: 'inline_python', timeout: 10 } } })
  expect(created.ok()).toBeTruthy()
  const revision = await created.json()
  expect((await request.patch(`/api/v1/functions/${record.id}`, { data: { revision_id: revision.id } })).ok()).toBeTruthy()
  return record
}

async function mode(page: Page, name: string) {
  await page.getByRole('combobox', { name: 'Input editor', exact: true }).click()
  await page.getByRole('option', { name, exact: true }).click()
}

test.beforeEach(async ({ context }) => {
  await login(context.request)
})

test('typed fields, references, arrays and nullable optional values produce the actual run payload', async ({ page, request }) => {
  const record = await seed(request, 'typed-fields-ui')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`/functions/${record.id}`)
  await expect(page.getByRole('combobox', { name: 'Input editor', exact: true })).toContainText('Fields')
  await page.getByRole('textbox', { name: 'Name (name)', exact: true }).fill('Alice\nBob')
  await page.getByRole('spinbutton', { name: 'Count (count)', exact: true }).fill('12')
  await page.getByRole('switch', { name: 'Active (active)', exact: true }).check()
  await page.getByRole('combobox', { name: 'Mode (mode)', exact: true }).click()
  await page.getByRole('option', { name: 'full', exact: true }).click()
  await page.getByRole('textbox', { name: 'City (city)', exact: true }).fill('London')
  await page.getByRole('button', { name: 'Add item', exact: true }).click()
  await page.getByRole('textbox', { name: 'tags[0]', exact: true }).fill('first')
  await page.getByRole('checkbox', { name: 'Include note in request', exact: true }).check()
  await page.getByRole('checkbox', { name: 'Send null for note', exact: true }).check()
  await mode(page, 'JSON')
  const editor = page.getByRole('textbox', { name: 'Input · JSON', exact: true })
  const expected = { name: 'Alice\nBob', count: 12, active: true, mode: 'full', address: { city: 'London' }, tags: ['first'], note: null }
  expect(JSON.parse(await editor.inputValue())).toEqual(expected)
  await mode(page, 'Fields')
  await page.getByRole('checkbox', { name: 'Send null for note', exact: true }).uncheck()
  await page.getByRole('textbox', { name: 'Note (note)', exact: true }).fill('keep this')
  await page.getByRole('checkbox', { name: 'Include extra in request', exact: true }).check()
  await page.getByRole('textbox', { name: 'Extra (extra)', exact: true }).fill('{"custom": [1, false]}')
  const submitted = page.waitForRequest(req => req.method() === 'POST' && req.url().includes(`/functions/${record.id}/run`))
  await page.getByRole('button', { name: 'Run', exact: true }).click()
  expect((await submitted).postDataJSON().input).toEqual({ ...expected, note: 'keep this', extra: { custom: [1, false] } })
  await expect(page.getByText('Succeeded', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('invalid JSON stays editable, unknown properties survive, and schema-free input uses JSON', async ({ page, request }) => {
  const record = await seed(request, 'json-roundtrip-ui')
  await page.goto(`/functions/${record.id}`)
  await mode(page, 'JSON')
  const editor = page.getByRole('textbox', { name: 'Input · JSON', exact: true })
  await editor.fill('{ broken')
  await mode(page, 'Fields')
  await expect(editor).toHaveValue('{ broken')
  await expect(page.getByRole('combobox', { name: 'Input editor', exact: true })).toContainText('JSON')
  const input = { name: '', count: 0, active: false, mode: 'brief', address: { city: 'X' }, tags: [], unknown: { untouched: true } }
  await editor.fill(JSON.stringify(input))
  await mode(page, 'Fields')
  // Unknown keys cause an honest JSON fallback rather than a form that drops them.
  const fallback = page.getByRole('textbox', { name: 'Input (Input)', exact: true })
  await fallback.fill('{ invalid')
  await page.getByRole('button', { name: 'Run', exact: true }).click()
  expect(await fallback.evaluate((el: HTMLTextAreaElement) => el.validity.valid)).toBe(false)
  await mode(page, 'JSON')
  await expect(fallback).toBeVisible()
  await fallback.fill(JSON.stringify(input))
  await mode(page, 'JSON')
  expect(JSON.parse(await editor.inputValue())).toEqual(input)
  const noSchema = await seed(request, 'no-fields-ui', 'async def function(input: None) -> str: return "ok"')
  await page.goto(`/functions/${noSchema.id}`)
  await expect(page.getByRole('combobox', { name: 'Input editor', exact: true })).toHaveCount(0)
  await expect(page.getByRole('textbox', { name: 'Input · JSON', exact: true })).toHaveValue('null')
})

test('untyped fields accept multiline text and parse JSON without changing explicit strings', async ({ page, request }) => {
  const record = await seed(request, 'text-or-json-fields-ui', `from typing import Any
from pydantic import BaseModel

class Input(BaseModel):
    message: Any
    payload: Any
    label: str

async def function(input: Input) -> dict:
    return input.model_dump()
`)
  await page.goto(`/functions/${record.id}`)
  const message = page.getByRole('textbox', { name: 'Message (message)', exact: true })
  const payload = page.getByRole('textbox', { name: 'Payload (payload)', exact: true })
  const label = page.getByRole('textbox', { name: 'Label (label)', exact: true })
  const text = '  First line\n\nSecond line  '
  await message.fill(text)
  await payload.fill('false')
  await label.fill('false')
  await mode(page, 'JSON')
  const editor = page.getByRole('textbox', { name: 'Input · JSON', exact: true })
  expect(JSON.parse(await editor.inputValue())).toEqual({ message: text, payload: false, label: 'false' })

  await editor.fill(JSON.stringify({ message: 'false', payload: null, label: 'false' }))
  await mode(page, 'Fields')
  await expect(message).toHaveValue('"false"')
  await mode(page, 'JSON')
  expect(JSON.parse(await editor.inputValue())).toEqual({ message: 'false', payload: null, label: 'false' })
  await mode(page, 'Fields')
  await message.fill(text)
  await payload.fill('{\n  "items": [1, true, null]\n}')
  const submitted = page.waitForRequest(req => req.method() === 'POST' && req.url().includes(`/functions/${record.id}/run`))
  await page.getByRole('button', { name: 'Run', exact: true }).click()
  expect((await submitted).postDataJSON().input).toEqual({ message: text, payload: { items: [1, true, null] }, label: 'false' })
  await expect(page.getByText('Succeeded', { exact: true })).toBeVisible()
})
