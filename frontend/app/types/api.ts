export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }
export type JsonObject = { [key: string]: JsonValue }

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface FunctionRecord {
  id: string
  name: string
  description: string | null
  revision_id: string | null
  enabled: boolean
  deleted: boolean
  runnable: boolean
  input_schema: JsonObject
  output_schema: JsonObject
  created_at: string
  updated_at: string
  deleted_at: string | null
}

export type Implementation
  = | { type: 'python', code: string, input_schema: JsonObject, output_schema: JsonObject }
    | { type: 'jinja', template: string, input_schema: JsonObject, output_schema: JsonObject }

export type RunnerOptions
  = | { type: 'inline_python', timeout: number | null }
    | { type: 'openai_jinja', timeout: number | null, base_url: string, model: string }

export interface RevisionRecord {
  id: string
  function_id: string
  implementation: Implementation
  runner_options: RunnerOptions
  created_at: string
}

export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export interface RunResult {
  output: JsonValue
  meta: { input_tokens?: number | null, output_tokens?: number | null, total_tokens?: number | null }
  duration: number
}

export interface RunRecord {
  id: string
  function_id: string
  revision_id: string
  input: JsonObject | null
  status: RunStatus
  output: JsonValue
  meta: (RunResult['meta'] & { code?: string, message?: string }) | null
  duration: number | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}
