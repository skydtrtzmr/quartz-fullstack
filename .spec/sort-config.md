# 客户端排序配置方案

## 概述

为 Backlinks、Explorer、FolderContent 三个组件提供统一的排序配置能力，通过 `quartz.layout.json` 进行配置覆盖。

## 接口定义

```ts
interface SortConfig {
  by: "natural" | "alpha" | "date"
  order: "asc" | "desc"
  field?: string  // 可选，默认值见下方各类型说明
}
```

## 排序类型详解

### 1. natural / alpha（字符串排序）

**field 默认值**：`"title"`

**行为说明**：
- 按字符串排序，支持自然语言数字排序（`file1, file2, file10` 正确排序）
- `natural` 启用数字智能排序，`alpha` 仅按字母序

**降级处理**：
1. 读取 frontmatter 的 `title` 字段
2. 如果没有 `title`，fallback 到 `slug`（文件名）

**实现逻辑**：
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

### 2. date（日期排序）

**field 默认值**：`"date"`

**行为说明**：
- 按日期字段排序，默认使用用户手动指定的 `date` 字段
- 支持 `created`、`modified`、`published`、`date` 等日期字段

**降级处理（多层 fallback）**：
1. 尝试读取 frontmatter 中指定的 `field` 字段
2. 如果字段不存在、值为空、或不是日期类型 → fallback 到 `dates.date`
3. 如果 `dates.date` 也不存在 → fallback 到 `dates.modified`（文件修改时间，必有）

**实现逻辑**：
```ts
function getDateFieldValue(item: FileData, field: string): Date | null {
  // 1. 尝试指定字段
  const rawValue = item.frontmatter?.[field]
  if (rawValue !== undefined && rawValue !== null) {
    const date = new Date(rawValue)
    if (!isNaN(date.getTime())) return date
    // 不是有效日期，触发 fallback
    console.warn(`[SortConfig] field "${field}" 不是日期类型，fallback 到 modified`)
  }
  
  // 2. fallback 到 frontmatter date
  if (item.dates?.date) return item.dates.date
  
  // 3. 最后 fallback 到 modified（必有的文件修改时间）
  return item.dates?.modified ?? null
}
```

## 各组件默认值

| 组件 | by 默认 | order 默认 | field 默认 |
|------|---------|-----------|-----------|
| Backlinks | `natural` | `asc` | `title` |
| Explorer | `natural` | `asc` | `title` |
| FolderContent | `date` | `desc` | `date` |

## quartz.layout.json 配置示例

```json
{
  "backlinks": {
    "sort": {
      "by": "date",
      "order": "desc",
      "field": "date"
    },
    "hideWhenEmpty": false
  },
  "explorer": {
    "sort": {
      "by": "natural",
      "order": "asc"
    }
  },
  "folderPage": {
    "sort": {
      "by": "date",
      "order": "desc",
      "field": "published"
    }
  }
}
```

## 实现文件清单

| 文件 | 变更内容 | 状态 |
|------|---------|------|
| `quartz/util/sort.ts` | 公共类型定义 + 泛型比较器工厂（createStringComparator / createDateComparator） | ✅ 已完成 |
| `quartz/components/pages/FolderContent.tsx` | 接收 SortConfig，内部构建 SortFn，文件夹优先 | ✅ 已完成 |
| `quartz/plugins/emitters/folderPage.tsx` | 从 quartz.layout.ts 导入 folderPageSort 传给 FolderContent | ✅ 已完成 |
| `quartz.layout.ts` | LayoutConfig 加 sort 字段，导出 folderPageSort | ✅ 已完成 |
| `quartz/components/Explorer2.tsx` | 新增 sort 选项，映射到已有 sortFn | ⏳ 待实现 |
| `quartz/components/Backlinks.tsx` | 新增 sort 选项，构建时+运行时排序 | ⏳ 待实现 |

## 设计原则

1. **LayoutConfig 只传简单参数**（字符串/枚举），不传函数
2. **排序逻辑在各组件内部**，通过 getter 函数控制自己的数据访问
3. **JSON 可序列化**，方便 `quartz.layout.json` 配置覆盖
4. **降级处理一致**：无匹配值时自动 fallback，不报错
5. **方案 B**：公共 `quartz/util/sort.ts` 只放类型定义和泛型比较器工厂，各组件通过 getter 适配自己的数据结构
