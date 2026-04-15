# 聚合功能设计文档

## 一、需求概述

反向链接和图谱都支持聚合功能，将关联节点按指定维度分组显示，提升大规模节点的可浏览性。

### 聚合维度

| 维度类型 | 说明 | 示例 |
|---------|------|------|
| 文件夹聚合 | 按物理路径层级分组 | `学习/编程/Go` → 三级折叠面板 |
| 字段聚合 | 按 frontmatter 属性值分组 | `project: X` |
| 日期聚合 | 按日期范围分组 | `2024-01`、`2024-Q1` |

### 设计约束

1. **文件夹聚合必须是第一级**：先按文件夹分组再按字段分组，反过来语义不合理
2. **字段聚合按 order 排序**：order 小的先匹配，决定节点的最终归属组
3. **嵌套效果统一**：最终都是折叠面板结构，逐级展开

---

## 二、配置结构

### TypeScript 类型定义

```typescript
// ===== 聚合类型 =====

type Granularity = "year" | "month" | "quarter"

// 文件夹聚合配置
interface FolderAggregation {
  type: "folder"
  depth?: number       // 展开层级深度，默认不限
}

// 字段聚合配置
interface FieldAggregation {
  type: "field"
  field: string         // frontmatter 字段名
  granularity?: Granularity  // 日期字段专用，普通字段忽略
  order: number         // 排序优先级，值越小越先匹配
}

// 聚合规则联合类型
type AggregationRule = FolderAggregation | FieldAggregation

// ===== 完整配置结构 =====

interface AggregationConfig {
  // 反向链接聚合
  backlinks?: {
    // 文件夹聚合（唯一，必须是第一级）
    folder?: {
      depth?: number
    }
    // 字段聚合列表（按 order 升序排列）
    fields?: FieldAggregation[]
  }

  // 图谱聚合
  graph?: {
    // 文件夹聚合（唯一）
    folder?: {
      depth?: number
    }
    // 字段聚合列表（按 order 升序排列）
    fields?: FieldAggregation[]
    // 着色字段（用于节点颜色区分）
    colorBy?: string
  }
}
```

### JSON 配置示例

```json
{
  "aggregation": {
    "backlinks": {
      "folder": { "depth": 2 },
      "fields": [
        { "field": "project", "order": 1 },
        { "field": "date", "granularity": "month", "order": 2 }
      ]
    },
    "graph": {
      "folder": { "depth": 1 },
      "fields": [
        { "field": "tags", "order": 1 }
      ],
      "colorBy": "project"
    }
  }
}
```

### 层级计算规则

```
总层级 = 文件夹层级（folder.depth 或实际深度）+ 字段聚合数（fields.length）
```

**示例 1**：
```json
{
  "folder": { "depth": 2 },
  "fields": [{ "field": "project", "order": 1 }]
}
```
- 总层级：2（文件夹）+ 1（字段）= 3 级
- 效果：`[文件夹1级] → [文件夹2级] → [project枚举]`

**示例 2**：
```json
{
  "folder": {},
  "fields": [
    { "field": "project", "order": 1 },
    { "field": "date", "granularity": "month", "order": 2 }
  ]
}
```
- 总层级：不限（文件夹）+ 2（字段）= 至少 2 级
- 效果：`[文件夹N级] → [project枚举] → [date月份]`

---

## 三、反向链接聚合实现

### 现有实现分析

当前 `Backlinks.tsx` 已实现：
- `groupBy: "folder" | "none"` 配置
- 基于 slug 路径构建树形结构
- 折叠面板交互

### 扩展点

| 组件 | 需要修改 | 说明 |
|------|---------|------|
| `Backlinks.tsx` | 重构分组逻辑 | 通用化分组算法，支持配置驱动 |
| `quartz.layout.ts` | 扩展 layout.json 读取 | 解析 `aggregation.backlinks` 配置 |
| `backlinks.scss` | 可能需要微调 | 确保样式兼容新的结构 |

### 核心数据结构

```typescript
// 聚合树节点
interface AggregationNode {
  key: string           // 分组键值（文件夹名 / 字段值）
  totalCount: number     // 包含的叶子节点总数
  children: AggregationNode[]  // 子聚合节点
  leaves: QuartzPluginData[]    // 直接关联的页面（叶子节点）
}

// 序列化格式（用于 JSON 传递）
interface SerializedAggregationNode {
  key: string
  totalCount: number
  children: SerializedAggregationNode[]
  leaves: { slug: string; title: string }[]
}
```

### 分组算法

```
function aggregate(files, rules):
  if rules is empty:
    return { key: "root", leaves: files, children: [], totalCount: files.length }

  rule = rules[0]
  groups = Map<key, files[]>

  for file in files:
    key = extractKey(file, rule)
    groups[key].push(file)

  result.children = []
  for key, groupFiles in groups:
    childNode = aggregate(groupFiles, rules[1:])
    childNode.key = key
    result.children.push(childNode)

  return result
```

### 字段值提取

```typescript
function extractKey(file: QuartzPluginData, rule: AggregationRule): string {
  if (rule.type === "folder") {
    // 按路径最后一段分组
    return file.slug?.split("/").pop() ?? "root"
  }

  if (rule.type === "field") {
    const value = file.frontmatter?.[rule.field]

    if (value === undefined || value === null) {
      return "(无)"
    }

    if (rule.granularity && value instanceof Date) {
      return formatDate(value, rule.granularity)
    }

    if (Array.isArray(value)) {
      // 多值字段：取第一个值作为主分组
      return String(value[0])
    }

    return String(value)
  }
}

function formatDate(date: Date, granularity: Granularity): string {
  const y = date.getFullYear()
  const m = date.getMonth() + 1

  switch (granularity) {
    case "year":   return `${y}年`
    case "month":  return `${y}-${String(m).padStart(2, "0")}`
    case "quarter": return `${y}-Q${Math.ceil(m / 3)}`
    default:        return `${y}-${String(m).padStart(2, "0")}`
  }
}
```

---

## 四、图谱聚合实现

### UI 效果

图谱聚合与反向链接不同，不是列表展示，而是：

1. **聚合节点**：代表一个分组，显示组内节点数量
2. **可展开**：点击聚合节点展开显示组内实际节点
3. **着色支持**：`colorBy` 字段决定节点颜色

### 交互模式

```
[初始状态]                    [展开 "Project A" 后]
┌─────────────────┐          ┌─────────────────┐
│  ● Node X       │          │  ● Node X       │
│                 │          │  ┌───────────┐   │
│  📁 Project A   │    →     │  │ Project A  │   │
│      (5)        │          │  │  ● Node 1  │   │
│                 │          │  │  ● Node 2  │   │
│  📁 Project B   │          │  │  ● ...     │   │
│      (3)        │          │  └───────────┘   │
└─────────────────┘          │  📁 Project B    │
                              └─────────────────┘
```

### 数据结构

```typescript
// 图谱聚合节点
interface GraphAggregationNode {
  key: string                    // 分组键值
  totalCount: number             // 包含的叶子节点数
  color?: string                 // 该组的统一颜色
  // 以下为展开后填充
  children?: GraphNode[]         // 子节点（展开后）
  edges?: GraphEdge[]             // 组内边
}

// 聚合节点渲染策略
interface GraphAggregationRenderer {
  collapsed: GraphAggregationNode   // 收起状态
  expanded: GraphNode[]             // 展开后替换为实际节点
}
```

### 实现要点

| 功能 | 实现方式 |
|------|---------|
| 聚合节点渲染 | D3 力导向图中添加虚拟节点类型 |
| 展开动画 | 点击后渐变替换为子节点，保留布局位置 |
| 折叠 | 逆向操作，子节点合并回聚合节点 |
| 着色 | `colorBy` 字段映射到预设调色板 |

---

## 五、配置读取

### quartz.layout.ts 扩展

```typescript
interface LayoutConfig {
  // ... 现有字段
  aggregation?: AggregationConfig
}

// 读取配置
let layoutCfg: LayoutConfig = {}
const settingsArg = process.argv.find((a) => a.startsWith("--settings="))
if (settingsArg) {
  const settingsPath = settingsArg.split("=").slice(1).join("=")
  const layoutJsonPath = path.join(settingsPath, "layout.json")
  // ... 现有读取逻辑
}

// 传递给组件
const backlinksCfg = {
  hideWhenEmpty: layoutCfg.backlinks?.hideWhenEmpty ?? false,
  aggregation: layoutCfg.aggregation?.backlinks,
}
```

### 组件接收配置

```typescript
interface BacklinksOptions {
  hideWhenEmpty: boolean
  aggregation?: AggregationConfig["backlinks"]
}
```

---

## 六、有环图处理（独立议题）

### 问题描述

全局图谱可能包含环形引用（A → B → C → A）。聚合展开时需要考虑：

1. **节点归属**：环形中一个节点可能同时属于多个聚合维度
2. **重复显示**：展开时同一节点可能在多处出现

### 处理策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| **首次匹配优先** | 节点按第一个匹配的聚合字段归组，后续不再重复分配 | 推荐默认策略 |
| **副本分配** | 同一节点可在多个聚合组中显示 | 需要特殊 UI 标识 |
| **DAG 裁剪** | 展开时只显示当前聚合分支内的可达节点 | 复杂图谱 |

### 推荐实现

采用 **首次匹配优先** 策略：

```typescript
function assignNodeToGroup(node: GraphNode, rules: AggregationRule[]): string {
  for (const rule of rules) {
    const key = extractKey(node, rule)
    if (key !== undefined && key !== "(无)") {
      return key  // 第一个匹配即为最终归属
    }
  }
  return "(未分类)"
}
```

### UI 标识

若采用副本分配策略，需在重复节点上添加视觉标识：

```
● Node A (出现在 2 个分组中)
```

---

## 七、实现计划

### Phase 1：配置结构与基础解析

- [ ] 在 `quartz.layout.ts` 中添加 `aggregation` 配置读取
- [ ] 定义 TypeScript 类型
- [ ] 创建配置验证函数

### Phase 2：反向链接聚合

- [ ] 重构 `Backlinks.tsx` 分组算法
- [ ] 实现文件夹聚合（复用现有逻辑）
- [ ] 实现字段聚合
- [ ] 集成 `aggregation.backlinks` 配置
- [ ] 样式适配

### Phase 3：图谱聚合

- [ ] 设计聚合节点渲染组件
- [ ] 实现展开/折叠交互
- [ ] 集成 `aggregation.graph` 配置
- [ ] 实现 `colorBy` 着色
- [ ] 处理有环情况

### Phase 4：测试与优化

- [ ] 多层级聚合测试
- [ ] 大规模节点性能测试
- [ ] 有环图场景测试
- [ ] UI/UX 优化

---

## 八、配置文件模板

### 最小配置（仅文件夹聚合）

```json
{
  "aggregation": {
    "backlinks": {
      "folder": {}
    }
  }
}
```

### 标准配置（文件夹 + 字段）

```json
{
  "aggregation": {
    "backlinks": {
      "folder": { "depth": 3 },
      "fields": [
        { "field": "project", "order": 1 },
        { "field": "tags", "order": 2 },
        { "field": "date", "granularity": "month", "order": 3 }
      ]
    },
    "graph": {
      "folder": { "depth": 1 },
      "fields": [
        { "field": "project", "order": 1 }
      ],
      "colorBy": "tags"
    }
  }
}
```

---

## 九、向后兼容

| 现有配置 | 迁移方式 |
|---------|---------|
| `backlinks.hideWhenEmpty` | 保持兼容 |
| `backlinks.groupBy: "folder" \| "none"` | 映射为 `aggregation.backlinks.folder: {}` 或 `null` |

迁移时自动转换：
- `groupBy: "folder"` → `aggregation.backlinks.folder: {}`
- `groupBy: "none"` → `aggregation.backlinks` 不设置
