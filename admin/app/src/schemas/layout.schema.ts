/**
 * 从原始 JSON Schema 文件自动加载并解析 $ref
 *
 * 这样修改 layout-config.schema.json 后，前端自动同步，无需手动维护两份
 */

import type { JsonSchema } from '@jsonforms/core'
import rawSchema from '../../../layout-config.schema.json'

/**
 * 将顶层 $ref 展开为内联结构
 * 原始 schema 结构为 { "$ref": "#/definitions/LayoutConfig", "definitions": {...} }
 * JSONForms 无法正确解析顶层 $ref + definitions 的组合
 * 需要将 $ref 指向的内容展开到根，definitions 保留为同级属性
 */
function resolveTopRef(schema: Record<string, unknown>): JsonSchema {
  const { $ref, definitions, ...rest } = schema
  if (!$ref || typeof $ref !== 'string' || !definitions || typeof definitions !== 'object') {
    return schema as JsonSchema
  }

  // 解析 "#/definitions/LayoutConfig" → "LayoutConfig"
  const refName = $ref.replace('#/definitions/', '')
  const resolved = (definitions as Record<string, unknown>)[refName]

  if (!resolved || typeof resolved !== 'object') {
    return schema as JsonSchema
  }

  // 将 $ref 指向的内容合并到根，definitions 保留
  return {
    ...resolved,
    definitions,
    ...rest, // 保留 $schema 等元信息
  } as JsonSchema
}

export const layoutSchema: JsonSchema = resolveTopRef(rawSchema)
