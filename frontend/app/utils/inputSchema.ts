import type { JsonObject, JsonValue } from '~/types/api'

export function isJsonObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function parseInputJson(source: string): JsonValue {
  return JSON.parse(source, (_key, value) => {
    if (typeof value === 'number' && !Number.isFinite(value)) throw new SyntaxError('Non-finite JSON number')
    return value
  })
}

// Resolve only local references. Ambiguous compositions stay editable as JSON.
export function inputSchema(node: JsonObject, root: JsonObject, depth = 0): JsonObject {
  if (depth > 20) return {}
  const seen = new Set<string>()
  while (typeof node.$ref === 'string') {
    const ref = node.$ref
    if (!ref.startsWith('#/') || seen.has(ref)) return {}
    seen.add(ref)
    let target: JsonValue | undefined = root
    for (const part of ref.slice(2).split('/'))
      target = isJsonObject(target) ? target[part.replace(/~1/g, '/').replace(/~0/g, '~')] : undefined
    if (!isJsonObject(target)) return {}
    const { $ref: _ref, ...siblings } = node
    node = { ...target, ...siblings }
  }
  const alternatives = node.anyOf ?? node.oneOf
  if (Array.isArray(alternatives)) {
    const choices = alternatives.filter(item => isJsonObject(item) && item.type !== 'null')
    if (choices.length === 1 && alternatives.some(item => isJsonObject(item) && item.type === 'null')) {
      const { anyOf: _any, oneOf: _one, ...rest } = node
      return { ...rest, ...inputSchema(choices[0] as JsonObject, root, depth + 1), nullable: true }
    }
  }
  if (Array.isArray(node.type)) {
    const types = node.type.filter(type => type !== 'null')
    if (types.length === 1 && node.type.includes('null')) return { ...node, type: types[0]!, nullable: true }
  }
  return node
}

export function fieldSample(node: JsonObject, root: JsonObject): JsonValue {
  return sampleInput(node, root)
}
