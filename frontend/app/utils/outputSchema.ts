import type { JsonObject, JsonValue } from '~/types/api'
import { isJsonObject } from '~/utils/inputSchema'

export const outputTypes = ['string', 'integer', 'number', 'boolean', 'object', 'array'] as const
export type OutputType = typeof outputTypes[number]

export interface OutputField {
  id: number
  name: string
  node: OutputNode
}

export interface OutputNode {
  type: OutputType
  nullable: boolean
  description: string
  fields: OutputField[]
  items?: OutputNode
  choices: string[]
}

export function newOutputNode(type: OutputType): OutputNode {
  return {
    type,
    nullable: false,
    description: '',
    fields: [],
    choices: [],
    items: type === 'array' ? newOutputNode('string') : undefined
  }
}

export function readOutputSchema(schema: JsonObject): OutputNode | undefined {
  if (!Object.keys(schema).length) return newOutputNode('object')

  function read(value: JsonValue | undefined, depth: number): OutputNode | undefined {
    if (!isJsonObject(value) || depth > 10) return
    const { type, description, enum: choices, properties, required, additionalProperties, items, ...rest } = value
    if (Object.keys(rest).length || (description !== undefined && typeof description !== 'string')) return

    const base = Array.isArray(type) ? type.find(item => item !== 'null') : type
    if (!outputTypes.includes(base as OutputType)) return
    const node = newOutputNode(base as OutputType)
    node.nullable = Array.isArray(type)
    if (Array.isArray(type) && (type.length !== 2 || !type.includes('null'))) return
    node.description = description ?? ''

    if (base === 'object') {
      if (!isJsonObject(properties) || !Array.isArray(required) || additionalProperties !== false) return
      const entries = Object.entries(properties)
      if (required.length !== entries.length || entries.some(([name]) => !required.includes(name))) return
      for (const [name, child] of entries) {
        const field = read(child, depth + 1)
        if (!name.trim() || !field) return
        node.fields.push({ id: node.fields.length, name, node: field })
      }
    } else if (properties !== undefined || required !== undefined || additionalProperties !== undefined) {
      return
    }
    if (base === 'array') {
      const item = read(items, depth + 1)
      if (!item) return
      node.items = item
    } else if (items !== undefined) {
      return
    }
    if (choices !== undefined) {
      if (base !== 'string' || !Array.isArray(choices)) return
      const strings = choices.filter((choice): choice is string => typeof choice === 'string')
      const expectedLength = strings.length + (node.nullable ? 1 : 0)
      if (!strings.length || new Set(strings).size !== strings.length || choices.length !== expectedLength
        || (node.nullable && !choices.includes(null))) return
      node.choices = strings
    }
    return node
  }

  const root = read(schema, 0)
  if (root?.type === 'object' && !root.nullable && (root.fields.length || root.description)) return root
}

export function outputSchemaIssue(node: OutputNode, depth = 0): 'emptyName' | 'duplicateName' | 'depthLimit' | undefined {
  if (depth > 10) return 'depthLimit'
  const names = node.fields.map(field => field.name)
  if (names.some(name => !name.trim())) return 'emptyName'
  if (new Set(names).size !== names.length) return 'duplicateName'
  for (const field of node.fields) {
    const issue = outputSchemaIssue(field.node, depth + 1)
    if (issue) return issue
  }
  if (node.items) return outputSchemaIssue(node.items, depth + 1)
}

export function writeOutputSchema(node: OutputNode, root = true): JsonObject {
  if (root && !node.fields.length && !node.description) return {}
  const schema: JsonObject = { type: node.nullable ? [node.type, 'null'] : node.type }
  if (node.description) schema.description = node.description
  if (node.type === 'object') {
    schema.properties = Object.fromEntries(node.fields.map(field => [field.name, writeOutputSchema(field.node, false)]))
    schema.required = node.fields.map(field => field.name)
    schema.additionalProperties = false
  }
  if (node.items) schema.items = writeOutputSchema(node.items, false)
  if (node.choices.length) schema.enum = node.nullable ? [...node.choices, null] : [...node.choices]
  return schema
}
