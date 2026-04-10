# 局部图谱预计算方案

## 配置设计

在 `quartz.config.ts` 中新增配置：

```typescript
// quartz.config.ts
configuration: {
  // ... 其他配置
  graph: {
    precomputeLocal: true,      // 是否预计算局部图谱（构建时生成）
    localDepth: 1,              // 预计算的深度（1 或 2）
    fallbackToBfs: true,        // 预计算文件缺失时是否回退到 BFS 计算
  }
}
```

## 文件存储结构（处理2万文件问题）

使用分层目录避免单目录文件过多：

```
output/xm/static/graph/local/
├── a/
│   ├── ab/
│   │   └── abcdef123.json     # slug 为 abcdef123 的页面
│   └── cd/
│       └── cdxyz789.json
├── b/
│   └── ...
└── manifest.json              # 索引文件，记录哪些页面有预计算数据
```

### 分层策略选项

#### 策略A：MD5哈希分组（默认）
- 取 slug 的 MD5 前 2 位作为第一层目录
- 取 MD5 第 3-4 位作为第二层目录
- 2万文件分散到 256 * 256 = 65536 个子目录中
- 实际每目录平均只有 0.3 个文件，即使不均匀也不会超过 10 个

#### 策略B：首字母分组（简单直观）
- 按 slug 的首字符分组
- 数字 0-9 共 10 组，字母 a-z 共 26 组
- 中文通过拼音转换为首字母
- 共 36 个一级分组，结构简单可预测

```
output/xm/static/graph/local/
├── 0/                         # 以数字开头的slug
│   └── 2024-year-review.json
├── a/
│   ├── abcdef123.json
│   └── about-me.json
├── z/
│   └── zettelkasten.json
└── 中/                        # 中文(或其他未识别字符)
    └── 中文笔记.json
```

**配置方式**：
```typescript
graph: {
  precomputeLocal: true,
  localDepth: 1,
  indexStrategy: 'md5' | 'alphabet'  // 索引策略选择
}
```

## 数据结构

```typescript
interface LocalGraphData {
  version: number              // 数据格式版本，用于兼容性检查
  slug: string                 // 中心节点 slug
  depth: number                // 计算的深度
  generatedAt: number          // 生成时间戳
  nodes: Array<{
    id: string
    title: string
    tags: string[]
    isVirtual?: boolean        // 是否是虚拟节点
  }>
  edges: Array<{
    source: string
    target: string
    sourceField?: string       // frontmatter 字段名
  }>
}
```

## 运行时加载逻辑

```typescript
// graph2.inline.ts
async function loadLocalGraph(slug: string): Promise<LocalGraphData | null> {
  if (!config.graph.precomputeLocal) return null
  
  const hash = md5(slug).slice(0, 4)
  const dir1 = hash.slice(0, 2)
  const dir2 = hash.slice(2, 4)
  const path = `./graph/local/${dir1}/${dir2}/${slug}.json`
  
  try {
    const response = await fetch(path)
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

// 在 renderGraph 中使用
const precomputed = await loadLocalGraph(slug)
if (precomputed) {
  // 使用预计算数据
  nodes = precomputed.nodes
  edges = precomputed.edges
} else if (config.graph.fallbackToBfs) {
  // 回退到 BFS 计算
  nodes = calculateLocalGraphBFS(slug, depth)
}
```

## 与"聚合条件"的结合

后续聚合节点功能可以复用局部图谱数据：
- 聚合节点本质上是将多个节点合并为一个"虚拟节点"
- 局部图谱数据中已经包含了节点间的连接关系
- 可以在预计算阶段就标记出"属于同一聚合组的节点"
- 这样运行时聚合只需要做简单的分组，不需要重新分析连接关系

## 实施步骤

1. **✅ 新增 GraphLocalEmitter** - 构建时生成局部图谱数据
   - 文件: `client/quartz/plugins/emitters/graphLocal.tsx`
   - 测试: `client/quartz/plugins/emitters/graphLocal.test.ts` (12 tests passed)
   - TS检查: 通过

2. **✅ 新增配置选项** - quartz.config.ts 支持 precomputeLocal
   - cfg.ts 中已添加 GraphConfig 接口
   - domain_config.go 中 generateQuartzConfig 会传递配置

3. **✅ 修改 graph2.inline.ts** - 优先加载预计算数据，支持 fallback
   - 已实现预计算数据加载逻辑
   - LocalGraphData.nodes 格式与 contentIndex 一致 (Record<slug, ContentDetails>)
   - graph2.inline.ts 可用相同逻辑解析，无需额外转换
   - 深度不匹配时自动回退到 BFS 计算

4. **✅ 数据兼容性确认**
   - local graph nodes 格式与 contentIndex 条目完全一致
   - frontmatter 完整保留，边标签解析逻辑无需修改
   - 虚拟节点通过空 filePath 标识

5. **⏳ 性能测试** - 对比 BFS 和预计算的实际性能差异
   - 单元测试已通过
   - 需要实际构建后验证加载速度

## 生成的数据结构示例

```json
{
  "version": 1,
  "slug": "api-test-page",
  "depth": 1,
  "generatedAt": 1775307593018,
  "nodes": [
    { "id": "api-test-page", "title": "API测试页面", "tags": [] },
    { "id": "子文件夹/项目1", "title": "项目1", "tags": ["标签1"] }
  ],
  "edges": [
    { "source": "api-test-page", "target": "子文件夹/项目1", "sourceField": "project" }
  ]
}
```

## 文件存储路径示例 (MD5策略)

```
output/xm/static/graph/local/
├── 15/4a/子文件夹/项目2.json
├── 34/ea/api-test-page.json
├── 43/11/子文件夹/项目2的不存在页面.json
├── 66/66/.json
└── 9a/d6/测试yaml.json
```

---

## 代码规范（重要）

### 编码要求
1. **所有文件必须使用 UTF-8 编码**，禁止写入非 UTF-8 字符
2. **每次修改后必须做 TypeScript 静态检查**：`npx tsc --noEmit`
3. **能写测试的必须写 `.test.ts` 文件**进行自测
4. **复杂逻辑需要先在 .spec 中说明设计思路**

### 开发流程
1. 修复/编写代码 → 2. TS 静态检查 → 3. 写测试 → 4. 运行测试 → 5. 更新 .spec

### 与原先 contentIndex.json 的兼容性
- 第一阶段：生成的局部图谱数据结构需与原先 contentIndex 中的数据格式**保持一致**
- 确保与现有代码兼容后，再考虑优化构建流程
