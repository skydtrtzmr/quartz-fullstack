# 图谱构建优化方案

## 问题分析

当前实现的问题：
1. **局部图谱**：每次访问页面都要 BFS 计算邻域（O(n) 遍历）
2. **全局图谱**：必须加载完整 contentIndex.json（包含所有 links）
3. **渲染卡顿**：节点数 > 200 时 Pixi.js 渲染性能下降

## 统一方案：三层数据架构

```
output/xm/static/
├── contentIndex.json          # 精简索引（只保留标题、标签、日期）
├── graph/
│   ├── manifest.json          # 图谱元数据（总节点数、边数、分片策略）
│   ├── nodes.json             # 所有节点基础信息（id, title, tags, x, y）
│   ├── edges.json             # 所有边（可压缩）
│   └── local/                 # 局部图谱预计算
│       ├── index.json         # 首页的局部图谱数据
│       ├── xm13.json
│       └── ...
```

## 数据层设计

### Layer 1: 精简索引 (contentIndex.json)
用于搜索、基础展示，不含 links：
```json
{
  "index": {
    "title": "首页",
    "tags": ["tag1"],
    "date": "2026-03-29",
    "wordCount": 100
  }
}
```

### Layer 2: 全局图谱数据 (graph/)
**nodes.json** - 节点基础信息（预计算布局坐标）：
```json
{
  "nodes": [
    {"id": "index", "title": "首页", "tags": ["tag1"], "x": 100, "y": 200, "links": 5},
    {"id": "xm13", "title": "项目", "tags": [], "x": -50, "y": 100, "links": 3}
  ]
}
```

**edges.json** - 边列表（压缩存储）：
```json
{
  "edges": [
    {"s": "index", "t": "xm13", "f": "project"},
    {"s": "xm13", "t": "tags/tag1"}
  ]
}
```
- `s`: source, `t`: target, `f`: field (可选)

### Layer 3: 局部图谱预计算 (graph/local/)
每个页面一个文件，包含 depth=1/2 的邻域：
```json
{
  "center": "index",
  "depth": 1,
  "nodes": [
    {"id": "index", "title": "首页", "x": 0, "y": 0},
    {"id": "xm13", "title": "项目", "x": 100, "y": 50}
  ],
  "edges": [
    {"s": "index", "t": "xm13", "f": "project"}
  ]
}
```

## 运行时数据流

### 局部图谱（侧边栏）
```
1. 页面加载
2. 加载 graph/local/{slug}.json（~5-20KB）
3. 直接使用 nodes/edges 渲染，无需计算
4. 如果文件不存在，回退到 BFS 计算（兼容旧数据）
```

**优势**：
- 加载时间：从 100-500ms（BFS）降到 10-30ms（直接加载）
- 内存占用：只加载当前页面相关节点（< 50 个）

### 全局图谱（弹窗）
```
方案 A：渐进加载（推荐）
1. 加载 manifest.json（了解数据规模）
2. 加载 nodes.json（所有节点位置）
3. 根据视口和缩放，选择性加载 edges 分片
4. 初始只渲染可视区域内的边

方案 B：核心节点优先
1. 加载 nodes.json，筛选 links > 2 的核心节点
2. 初始只渲染核心节点和它们之间的边
3. 用户双击节点时，加载该节点的所有边
```

## 构建时处理

### 新增 Emitter：GraphDataEmitter
在构建时为每个页面生成局部图谱：

```typescript
// 伪代码
for (const [slug, file] of allFiles) {
  // 预计算 depth=1 和 depth=2 的邻域
  const localGraph = calculateLocalGraph(slug, allFiles, depth=2)
  
  // 写入 graph/local/{slug}.json
  yield write({
    content: JSON.stringify(localGraph),
    slug: `graph/local/${slug}` as FullSlug,
    ext: ".json"
  })
}

// 同时生成全局图谱数据
yield write({
  content: JSON.stringify({nodes, edges}),
  slug: "graph/nodes" as FullSlug,
  ext: ".json"
})
```

### 布局预计算
使用 d3-force 在构建时预计算节点位置：
```typescript
const simulation = d3.forceSimulation(nodes)
  .force("link", d3.forceLink(edges).id(d => d.id))
  .force("charge", d3.forceManyBody())
  .force("center", d3.forceCenter(0, 0))

// 运行一定步数后保存位置
for (let i = 0; i < 300; i++) simulation.tick()
```

## 文件大小预估

| 文件 | 100页面 | 1000页面 |
|------|---------|----------|
| contentIndex.json | 50KB | 300KB |
| graph/nodes.json | 30KB | 200KB |
| graph/edges.json | 100KB | 1MB |
| graph/local/*.json | 平均 5KB/个 | 平均 5KB/个 |

## 实施步骤

1. **Phase 1**：局部图谱预计算（效果最明显）
   - 新增 GraphLocalEmitter
   - 修改 graph2.inline.ts 优先加载 local/*.json

2. **Phase 2**：全局图谱数据分离
   - 新增 GraphGlobalEmitter
   - 分离 nodes/edges，支持按需加载

3. **Phase 3**：布局预计算
   - 构建时运行 force simulation
   - 保存节点坐标，运行时无需重新布局

4. **Phase 4**：增量更新
   - 只重新计算变化页面的局部图谱
   - 支持 partialEmit

## 向后兼容

- 如果 graph/local/{slug}.json 不存在，回退到当前 BFS 计算
- 如果 graph/nodes.json 不存在，使用 contentIndex.json
