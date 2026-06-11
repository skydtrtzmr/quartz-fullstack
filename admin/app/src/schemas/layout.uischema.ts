import type { UISchemaElement } from '@jsonforms/core'

export const layoutUiSchema: UISchemaElement = {
  type: 'Categorization',
  options: {
    label: 'Quartz 布局配置',
  },
  elements: [
    {
      type: 'Category',
      label: '文件浏览器',
      elements: [
        {
          type: 'Control',
          scope: '#/properties/explorer/properties/sort',
        },
        {
          type: 'Control',
          scope: '#/properties/explorer/properties/aggregation',
          options: {
            detail: {
              type: 'VerticalLayout',
              elements: [
                {
                  type: 'Control',
                  scope: '#/properties/type',
                },
                {
                  type: 'Control',
                  scope: '#/properties/field',
                },
                {
                  type: 'Control',
                  scope: '#/properties/depth',
                },
                {
                  type: 'Control',
                  scope: '#/properties/granularity',
                },
              ],
            },
          },
        },
      ],
    },
    {
      type: 'Category',
      label: '反向链接',
      elements: [
        {
          type: 'Control',
          scope: '#/properties/backlinks/properties/hideWhenEmpty',
        },
        {
          type: 'Control',
          scope: '#/properties/backlinks/properties/sort',
        },
        {
          type: 'Control',
          scope: '#/properties/backlinks/properties/aggregation',
          options: {
            detail: {
              type: 'VerticalLayout',
              elements: [
                {
                  type: 'Control',
                  scope: '#/properties/type',
                },
                {
                  type: 'Control',
                  scope: '#/properties/field',
                },
                {
                  type: 'Control',
                  scope: '#/properties/depth',
                },
                {
                  type: 'Control',
                  scope: '#/properties/granularity',
                },
              ],
            },
          },
        },
      ],
    },
    {
      type: 'Category',
      label: '文件夹页',
      elements: [
        {
          type: 'Control',
          scope: '#/properties/folderPage/properties/sort',
        },
        {
          type: 'Control',
          scope: '#/properties/folderPage/properties/aggregation',
          options: {
            detail: {
              type: 'VerticalLayout',
              elements: [
                {
                  type: 'Control',
                  scope: '#/properties/type',
                },
                {
                  type: 'Control',
                  scope: '#/properties/field',
                },
                {
                  type: 'Control',
                  scope: '#/properties/depth',
                },
                {
                  type: 'Control',
                  scope: '#/properties/granularity',
                },
              ],
            },
          },
        },
      ],
    },
    {
      type: 'Category',
      label: '关系图谱',
      elements: [
        {
          type: 'Control',
          scope: '#/properties/graph/properties/colorBy',
        },
        {
          type: 'Control',
          scope: '#/properties/graph/properties/coreNodeLimit',
        },
        {
          type: 'Control',
          scope: '#/properties/graph/properties/expandCoresOnRegionOpen',
        },
        {
          type: 'Control',
          scope: '#/properties/graph/properties/filterNonCoreNodes',
        },
        {
          type: 'Control',
          scope: '#/properties/graph/properties/coreNodeFilter',
          options: {
            detail: {
              type: 'VerticalLayout',
              elements: [
                {
                  type: 'Control',
                  scope: '#/properties/type',
                },
                {
                  type: 'Control',
                  scope: '#/properties/field',
                },
                {
                  type: 'Control',
                  scope: '#/properties/depth',
                },
                {
                  type: 'Control',
                  scope: '#/properties/values',
                },
              ],
            },
          },
        },
        {
          type: 'Control',
          scope: '#/properties/graph/properties/regionRules',
          options: {
            detail: {
              type: 'VerticalLayout',
              elements: [
                {
                  type: 'Control',
                  scope: '#/properties/type',
                },
                {
                  type: 'Control',
                  scope: '#/properties/field',
                },
                {
                  type: 'Control',
                  scope: '#/properties/depth',
                },
                {
                  type: 'Control',
                  scope: '#/properties/granularity',
                },
              ],
            },
          },
        },
        {
          type: 'Control',
          scope: '#/properties/graph/properties/aggregation',
          options: {
            detail: {
              type: 'VerticalLayout',
              elements: [
                {
                  type: 'Control',
                  scope: '#/properties/type',
                },
                {
                  type: 'Control',
                  scope: '#/properties/field',
                },
                {
                  type: 'Control',
                  scope: '#/properties/depth',
                },
                {
                  type: 'Control',
                  scope: '#/properties/granularity',
                },
              ],
            },
          },
        },
      ],
    },
  ],
}
