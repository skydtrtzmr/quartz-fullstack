# 排序配置规范

## 概述

为 Backlinks、Explorer、FolderContent 三个组件提供统一的排序配置能力，通过 `quartz.layout.json` 进行配置覆盖。

## 类型定义

```ts
/**
 * 排序算法类型
 * natural: 自然排序，识别文本中的数字序列（默认）
 * lexical: 字符编码排序
 * date: 日期排序，强制解析为时间戳比较
 * numeric: 数值排序，强制解析为浮点数比较
 */
type SortMethod = 'natural' | 'lexical' | 'date' | 'numeric';

/**
 * 排序方向
 * asc: 升序 (1-10, A-Z, 旧-新)
 * desc: 降序 (10-1, Z-A, 新-旧)
 */
type SortOrder = 'asc' | 'desc';

interface SortConfig {
  /** 排序类型，默认 'natural' */
  type: SortMethod;

  /** 排序方向，默认取决于 type */
  order: SortOrder;

  /** 排序字段，默认值由 type 决定 */
  field: string;
}
```

## field 默认值

| type | field 默认值 | 说明 |
|------|-------------|------|
| `date` | `'date'` | frontmatter 的 date 字段 |
| `numeric` | 无默认 | 必须显式指定字段 |
| `natural` | `'title'` | frontmatter 的 title 字段 |
| `lexical` | `'title'` | frontmatter 的 title 字段 |

## 降级逻辑（Fallback Chain）

### date 类型

1. 尝试 frontmatter 中指定的 `field` 字段
2. 如果字段不存在、值为空、或不是日期类型 → fallback 到 `dates.date`
3. 如果 `dates.date` 也不存在 → fallback 到 `dates.modified`（文件修改时间，必有）

```ts
function getDateFieldValue(item: FileData, field: string): Date | null {
  // 1. 尝试指定字段
  const rawValue = item.frontmatter?.[field]
  if (rawValue !== undefined && rawValue !== null) {
    const date = new Date(rawValue)
    if (!isNaN(date.getTime())) return date
    console.warn(`[SortConfig] field "${field}" 不是日期类型，fallback 到 modified`)
  }

  // 2. fallback 到 frontmatter date
  if (item.dates?.date) return item.dates.date

  // 3. 最后 fallback 到 modified（必有的文件修改时间）
  return item.dates?.modified ?? null
}
```

### natural / lexical 类型

1. 尝试 frontmatter 中指定的 `field` 字段
2. 如果是 `title` 字段且不存在 → fallback 到 `slug`（文件名）
3. 如果是其他字段且不存在 → fallback 到空字符串

```ts
function getStringFieldValue(item: FileData, field: string): string {
  if (field === "title") {
    // title 字段优先，没有则用 slug
    return item.frontmatter?.title ?? item.slug ?? ""
  }
  // 其他自定义字段
  return String(item.frontmatter?.[field] ?? "")
}
```

### numeric 类型

1. 尝试 frontmatter 中指定的 `field` 字段
2. 如果不存在 → fallback 到 0

```ts
function getNumericFieldValue(item: FileData, field: string): number {
  const rawValue = item.frontmatter?.[field]
  if (rawValue !== undefined && rawValue !== null) {
    const num = Number(rawValue)
    if (!isNaN(num)) return num
  }
  return 0
}
```

## order 默认值

| type | order 默认值 |
|------|-------------|
| `date` | `'desc'` |
| `numeric` | `'asc'` |
| `natural` | `'asc'` |
| `lexical` | `'asc'` |

## Tie-breaker（值相等时的兜底排序）

当排序字段值相等时，使用 title 做 natural 排序作为兜底，保证排序结果稳定：

| type | tie-breaker |
|------|-------------|
| `date` | 相等时 → title natural |
| `numeric` | 相等时 → title natural |
| `natural` | 无（已是最终降级） |
| `lexical` | 无（已是最终降级） |

## 各组件默认值

| 组件 | type 默认 | order 默认 | field 默认 |
|------|----------|-----------|-----------|
| Backlinks | `natural` | `asc` | `title` |
| Explorer | `natural` | `asc` | `title` |
| FolderContent | `natural` | `asc` | `title` |

## quartz.layout.json 配置示例

```json
{
  "backlinks": {
    "sort": {
      "type": "date",
      "order": "desc",
      "field": "date"
    },
    "hideWhenEmpty": false
  },
  "explorer": {
    "sort": {
      "type": "natural",
      "order": "asc"
    }
  },
  "folderPage": {
    "sort": {
      "type": "date",
      "order": "desc",
      "field": "published"
    }
  }
}
```

## 实现文件清单

| 文件 | 变更内容 | 状态 |
|------|---------|------|
| `quartz/util/sort.ts` | 公共类型定义 + 泛型比较器工厂（createStringComparator / createDateComparator / createNumericComparator） | ⏳ 待更新 |
| `quartz/components/pages/FolderContent.tsx` | 接收 SortConfig，内部构建 SortFn | ⏳ 待更新 |
| `quartz/plugins/emitters/folderPage.tsx` | 从 quartz.layout.ts 导入 folderPageSort 传给 FolderContent | ✅ 已完成 |
| `quartz.layout.ts` | LayoutConfig 加 sort 字段，导出 folderPageSort | ✅ 已完成 |
| `quartz/components/Explorer2.tsx` | 新增 sort 选项，映射到已有 sortFn | ⏳ 待实现 |
| `quartz/components/Backlinks.tsx` | 新增 sort 选项，构建时+运行时排序 | ⏳ 待实现 |

## 设计原则

1. **三个参数都是必选项，都有默认值**：type / order / field 都必须存在
2. **LayoutConfig 只传简单参数**（字符串/枚举），不传函数
3. **排序逻辑在各组件内部**，通过 getter 函数控制自己的数据访问
4. **JSON 可序列化**，方便 `quartz.layout.json` 配置覆盖
5. **降级处理一致**：无匹配值时自动 fallback，不报错
6. **tie-breaker 稳定**：当主排序字段值相等时，用 title natural 作为兜底
