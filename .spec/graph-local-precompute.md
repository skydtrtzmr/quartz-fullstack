# 图谱局部预计算技术文档

## 概述

本文档记录图谱局部预计算的实现原理、关键设计决策和 Slug 类型使用规范。

---

## 1. Promise 缓存机制

### 设计目标

`graph2.inline.ts` 和 `Backlinks.tsx` 都可能触发局部图谱数据请求，但无论谁先调用，最终只有一次网络请求。

### 工作原理

```typescript
// graph2.inline.ts
const localGraphPromiseCache = new Map<string, Promise<LocalGraphData>>()

export function fetchLocalGraphData(slug: FullSlug, depth: number): Promise<LocalGraphData> {
  const cacheKey = `${slug}::${depth}`
  const existing = localGraphPromiseCache.get(cacheKey)
  if (existing) return existing

  const promise = doFetch() // 实际请求
  localGraphPromiseCache.set(cacheKey, promise)
  return promise
}
```

### 执行顺序无关性

- 两者通过共享的 `localGraphPromiseCache` Map 实现请求幂等性
- 模块级缓存随页面刷新重置，无需担心跨会话污染

### SPA 导航兼容性

- 单页应用路由切换时，组件卸载/重建会触发新的 fetch 请求
- 但由于缓存基于 `slug + depth`，同页面重复访问不会重复请求

### Backlinks 复用方式

`Backlinks.tsx` 使用 `window.__localGraphCache.fetch()` 共享 `graph2.inline.ts` 中的缓存：

```typescript
export async function fetchBacklinksDetails(slug: FullSlug): Promise<ContentDetails[]> {
  const data = await window.__localGraphCache.fetch(slug, 1)
  return Object.values(data.nodes) || []
}
```

---

## 2. FullSlug vs SimpleSlug 使用规范

### 概念区分

| 类型 | 用途 | 示例 |
|------|------|------|
| **FullSlug** | 外部交互（文件路径、URL、网络请求） | `blog/my-post`、`docs/api-guide` |
| **SimpleSlug** | 内部图谱计算、预计算数据 | 同上，但不包含域名路由前缀 |

### 内部转换

两者通过 `simplifySlug()` 相互转换：

```typescript
import { simplifySlug, fullSlugToRelativeSlug } from "../util/path"

const simple = simplifySlug(full)  // FullSlug → SimpleSlug
const full = fullSlugToRelativeSlug(simple)  // SimpleSlug → FullSlug
```

### 各文件使用场景

#### graphLocal.tsx（构建时）

| 场景 | 类型 | 说明 |
|------|------|------|
| 输入参数 `centerSlug` | `SimpleSlug` | 与 graph2.inline.ts 的 `LocalGraphData.center` 类型一致 |
| 内部计算 | `SimpleSlug` | 图谱遍历、节点匹配 |
| 输出文件路径 `fp` | `FullSlug` | `graph/local/{hash}/{slug}.json` |
| JSON 内部 `center` | `SimpleSlug` | 预计算数据的中心节点标识 |

#### graph2.inline.ts（运行时）

| 场景 | 类型 | 说明 |
|------|------|------|
| URL 参数传递 | `FullSlug` | `data-graph-url={...}` |
| fetch 路径构建 | `FullSlug` | 请求预计算 JSON |
| cacheKey | `FullSlug` | 缓存标识 |
| 内部计算 `current` | `SimpleSlug` | 图谱节点遍历 |
| D3 图谱节点 data 属性 | `SimpleSlug` | `data-slug={node.data.slug}` |

### 设计原则

- **外部交互用 FullSlug**：URL、网络请求、文件路径
- **内部计算用 SimpleSlug**：图谱算法、数据结构
- **类型一致性**：预计算 JSON 的 `center` 类型必须与使用方一致，否则会导致查找失败

---

## 3. 深度配置统一

### 预计算配置

```typescript
// quartz.config.ts
Plugin.GraphLocalEmitter({
  depth: cfg.graph?.localDepth ?? 1  // 使用全局配置
})
```

### 运行时判断

```typescript
// graph2.inline.ts
const precomputeDepth = parseInt(element.dataset.precomputeDepth ?? '1', 10)
const shouldUsePrecompute = depth <= precomputeDepth
```

### 区分全局/局部图谱

| 条件 | 图谱类型 | 说明 |
|------|----------|------|
| `depth < 0` | 全局图谱 | 显示整个图谱 |
| `0 < depth <= precomputeDepth` | 局部图谱 | 显示预计算数据 |
| `depth > precomputeDepth` | 动态计算 | 实时 BFS 遍历 |

### 配置传递流程

```
quartz.config.ts (depth: cfg.graph.localDepth)
    ↓
GraphLocalEmitter (生成预计算 JSON)
    ↓
Graph.tsx (data-precompute-depth 属性)
    ↓
graph2.inline.ts (读取并判断是否使用预计算)
```

---

## 4. 预计算数据结构

### 文件路径

```
output/graph/local/{md5(0,2)}/{md5(2,2)}/{slug}.json
```

- MD5 哈希基于完整 slug（包含路径分隔符）
- slug 可能包含 `/`，会被正确哈希

### JSON 格式

```json
{
  "version": 1,
  "center": "page-slug",        // SimpleSlug 类型
  "depth": 1,
  "nodes": {
    "page-slug": { "title": "...", "filePath": "...", ... },
    "linked-page": { ... }
  },
  "edges": [
    { "source": "...", "target": "...", "sourceField": "project" }
  ]
}
```

### 节点类型

| 类型 | 判断条件 | 说明 |
|------|----------|------|
| 虚拟节点 | `filePath === ""` | 外部链接，无实际文件 |
| 常规节点 | `filePath !== ""` | 本地 markdown 文件 |

---

## 5. 实现状态

### ✅ 已完成

- [x] 单页 neighborhood 预计算
- [x] 数据结构与 contentIndex 对齐
- [x] 路径结构 MD5 哈希
- [x] Promise 缓存机制
- [x] 类型统一（SimpleSlug）

### ⏳ 进行中

- [ ] 性能测试

### 📋 待优化（已实现 ✅）

- ~~当前局部图谱请求：先 `fetchData()` 再尝试预计算 JSON~~
- ✅ **优化完成**：优先请求预计算 JSON，成功则跳过 `fetchData()` + BFS
- 收益：减少 1 次请求（预计算覆盖的场景）

#### 优化后执行流程

```
if (usePrecomputed) {  // depth > 0 && depth <= precomputeDepth
  // 1. 先尝试加载预计算 JSON
  const pdata = await fetchCachedLocalGraph()
  
  if (pdata && pdata.depth >= requiredDepth) {
    // ✅ 成功：直接使用预计算数据
    // 构建 graphData 从 localGraphData.nodes
    // 跳过 fetchData 和 BFS
    localGraphData = pdata
  }
}

if (!localGraphData) {
  // ❌ 预计算不可用：回退到 fetchData + BFS
  data = await fetchData
  // ... BFS 遍历
}

// 后续代码统一使用 graphData
```
