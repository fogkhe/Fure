import type { JsonObject, JsonValue } from '~/types/api'

function object(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function sampleInput(schema: JsonObject): JsonValue {
  function sample(node: JsonObject, depth: number, name = ''): JsonValue {
    if (depth > 5) return null
    if ('default' in node) return node.default ?? null
    if ('const' in node) return node.const ?? null
    if (Array.isArray(node.enum) && node.enum.length) return node.enum[0] ?? null
    if (typeof node.$ref === 'string' && node.$ref.startsWith('#/')) {
      let target: JsonValue = schema
      for (const part of node.$ref.slice(2).split('/')) {
        if (!object(target)) return null
        target = target[part.replace(/~1/g, '/').replace(/~0/g, '~')] ?? null
      }
      return object(target) ? sample(target, depth + 1, name) : null
    }
    if (Array.isArray(node.anyOf)) {
      const choice = node.anyOf.find(item => object(item) && item.type !== 'null')
      return object(choice) ? sample(choice, depth + 1, name) : null
    }
    if (node.type === 'null') return null
    if (node.type === 'object' || object(node.properties)) {
      const properties = object(node.properties) ? node.properties : {}
      const required = Array.isArray(node.required) ? node.required : Object.keys(properties)
      return Object.fromEntries(required.filter((key): key is string => typeof key === 'string').map(key => [key, object(properties[key]) ? sample(properties[key], depth + 1, key) : key === 'name' ? 'world' : '']))
    }
    if (node.type === 'array') return []
    if (node.type === 'boolean') return false
    if (node.type === 'integer' || node.type === 'number') return typeof node.minimum === 'number' ? node.minimum : 0
    return name === 'name' ? 'world' : ''
  }
  return sample(schema, 0)
}

export function parseObject(source: string): JsonObject {
  const value: JsonValue = JSON.parse(source)
  if (!object(value)) throw new Error('Схема должна быть JSON-объектом, например {}.')
  return value
}
