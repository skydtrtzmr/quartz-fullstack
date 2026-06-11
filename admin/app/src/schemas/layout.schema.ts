import type { JsonSchema } from '@jsonforms/core'

export const layoutSchema: JsonSchema = {
  type: 'object',
  properties: {
    explorer: {
      type: 'object',
      properties: {
        aggregation: {
          $ref: '#/definitions/AggregationConfig',
          description: '聚合规则列表，按顺序执行分组',
        },
        sort: {
          $ref: '#/definitions/SortConfig',
          description: '排序配置',
        },
      },
      additionalProperties: false,
      description: '文件浏览器配置',
    },
    backlinks: {
      type: 'object',
      properties: {
        hideWhenEmpty: {
          type: 'boolean',
          description: '当无反向链接时隐藏整个区域',
        },
        aggregation: {
          $ref: '#/definitions/AggregationConfig',
          description: '聚合规则列表',
        },
        sort: {
          $ref: '#/definitions/SortConfig',
          description: '排序配置',
        },
      },
      additionalProperties: false,
      description: '反向链接组件配置',
    },
    folderPage: {
      type: 'object',
      properties: {
        aggregation: {
          $ref: '#/definitions/AggregationConfig',
          description: '聚合规则列表',
        },
        sort: {
          $ref: '#/definitions/SortConfig',
          description: '排序配置',
        },
      },
      additionalProperties: false,
      description: '文件夹页配置',
    },
    graph: {
      type: 'object',
      properties: {
        aggregation: {
          $ref: '#/definitions/AggregationConfig',
          description: '聚合规则列表',
        },
        colorBy: {
          type: 'string',
          description: '按字段着色的字段名',
        },
        coreNodeFilter: {
          $ref: '#/definitions/CoreNodeFilterConfig',
          description: '核心节点过滤规则，满足任一规则即为核心节点（OR 关系）',
        },
        coreNodeLimit: {
          type: 'number',
          description: '核心节点数量上限',
        },
        regionRules: {
          $ref: '#/definitions/AggregationConfig',
          description: '区域规则列表，用于图谱区域折叠/展开',
        },
        expandCoresOnRegionOpen: {
          type: 'boolean',
          description: '区域展开时是否同时展开核心节点',
        },
        filterNonCoreNodes: {
          type: 'boolean',
          description: '是否过滤非核心节点',
        },
      },
      additionalProperties: false,
      description: '关系图谱配置',
    },
  },
  additionalProperties: false,
  description: '布局配置，对应 quartz.layout.json 的结构',
  definitions: {
    AggregationConfig: {
      type: 'array',
      items: {
        $ref: '#/definitions/AggregationRule',
      },
      description: '聚合配置：规则列表',
    },
    AggregationRule: {
      type: 'object',
      properties: {
        type: {
          $ref: '#/definitions/AggregationType',
          description: '聚合维度类型',
        },
        field: {
          type: 'string',
          description: '字段名（field/date 用，folder 可省略）',
        },
        depth: {
          type: 'number',
          description: '文件夹截取深度（仅 folder 有效）',
        },
        granularity: {
          type: 'string',
          enum: ['year', 'month', 'quarter'],
          description: '日期粒度（仅 date 有效）',
        },
      },
      required: ['type'],
      additionalProperties: false,
      description: '单条聚合规则',
    },
    AggregationType: {
      type: 'string',
      enum: ['folder', 'field', 'date'],
      description: '聚合维度类型',
    },
    SortConfig: {
      type: 'object',
      properties: {
        type: {
          $ref: '#/definitions/SortMethod',
          description: "排序类型，默认 'natural'",
        },
        order: {
          $ref: '#/definitions/SortOrder',
          description: '排序方向，默认取决于 type',
        },
        field: {
          type: 'string',
          description: '排序字段，默认值由 type 决定',
        },
      },
      required: ['type', 'order', 'field'],
      additionalProperties: false,
      description: '排序配置',
    },
    SortMethod: {
      type: 'string',
      enum: ['natural', 'lexical', 'date', 'numeric'],
      description: '排序算法类型',
    },
    SortOrder: {
      type: 'string',
      enum: ['asc', 'desc'],
      description: '排序方向',
    },
    CoreNodeFilterConfig: {
      type: 'array',
      items: {
        $ref: '#/definitions/CoreNodeFilterRule',
      },
      description: '核心节点过滤配置：规则列表，满足任一规则即为核心节点（OR 关系）',
    },
    CoreNodeFilterRule: {
      type: 'object',
      properties: {
        type: {
          type: 'string',
          enum: ['folder', 'field'],
          description: '过滤维度类型',
        },
        field: {
          type: 'string',
          description: '字段名（field 用，folder 可省略）',
        },
        depth: {
          type: 'number',
          description: '文件夹截取深度（仅 folder 有效）',
        },
        values: {
          type: 'array',
          items: {
            type: 'string',
          },
          description: '精确匹配值列表（满足任一值即命中）',
        },
      },
      required: ['type'],
      additionalProperties: false,
      description: '单条核心节点过滤规则',
    },
  },
}
