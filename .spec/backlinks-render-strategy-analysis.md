# 反向链接数据源方案对比分析

## 背景问题

**当前问题**：增量构建（`reset=false`）时，反向链接计算不准确。

**根因**：构建时 `ContentPage` 传递的 `allFiles` 仅包含当前批次的变化文件，而非完整文件列表，导致 `Backlinks` 组件无法正确计算所有引用当前页面的文档。

---

## 方案对比总览

| 维度 | 方案A：构建时绘制 | 方案B：运行时动态绘制 |
|------|-----------------|---------------------|
| 数据来源 | 构建时 `allFiles` | 预计算的局部图谱 JSON |
| 计算时机 | 构建阶段 | 页面加载阶段 |
| 增量构建支持 | ❌ 需修复 | ✅ 天然支持 |
| 前端复杂度 | 低 | 中 |
| 首屏性能 | ✅ 好 | ⚠️ 需额外加载 |
| 实时性 | 构建时快照 | 取决于 JSON 时效 |

---

## 方案A：构建时绘制（当前方案）

### 数据流

```
构建阶段:
  allFiles (完整文件列表)
    ↓
  allFiles.filter(f → f.links?.includes(slug))
    ↓
  buildAggregationTree()
    ↓
  序列化 SerializedNode → 嵌入 HTML
    ↓
页面加载:
  直接渲染，无需额外处理
```

### 优点

1. **首屏性能好**：数据已嵌入 HTML，无额外网络请求
2. **SEO 友好**：反向链接内容对搜索引擎可见
3. **前端简单**：无需 JavaScript 渲染逻辑
4. **用户无需等待**：数据加载与页面同步

### 缺点

1. **增量构建问题**：`allFiles` 不完整导致计算错误
2. **HTML 体积增大**：每个页面都包含完整聚合数据
3. **修改聚合配置需全量重构建**：用户无法实时调整分组方式
4. **构建时 CPU 消耗**：大量文件的聚合计算集中在构建阶段

### 修复方案（不改变架构）

**核心问题**：`build.ts` 中为 `ContentPage` 传递的内容不完整。

**修复点**：
```typescript
// build.ts 当前逻辑
contentToPass = filterContent(ctx, parsedFiles) // 只传变化文件

// 修复方案：为 ContentPage 传递完整文件列表
if (emitter.name === "ContentPage") {
  contentToPass = filteredContent // 使用 allParsedFiles 的过滤结果
}
```

**预估工作量**：修改 1 处代码

---

## 方案B：运行时动态绘制

### 数据流

```
构建阶段:
  GraphLocalEmitter.generate() → graph/local/{hash}/{slug}.json
    ↓ (每页包含 nodes + edges，edges 已包含入边信息)
  无需额外处理

页面加载:
  加载 graph/local/{hash}/{slug}.json
    ↓
  过滤 edges.filter(e → e.target === currentSlug)
    ↓
  前端 buildAggregationTree()
    ↓
  动态渲染 DOM
```

### 优点

1. **天然支持增量构建**：JSON 文件独立更新，不依赖 allFiles
2. **数据一致性**：每个页面的局部图谱独立、可追溯
3. **可扩展性**：用户可动态调整聚合配置（如切换按文件夹/按日期分组）
4. **构建性能提升**：聚合计算从构建阶段转移到客户端

### 缺点

1. **额外网络请求**：每个页面需加载局部图谱 JSON
2. **前端复杂度增加**：需实现聚合算法和 DOM 渲染
3. **SEO 影响**：反向链接依赖 JavaScript 渲染
4. **首屏加载延迟**：需等待 JSON 加载完成才显示反向链接
5. **缓存策略**：需合理设置缓存，避免每次都重新请求

### 实现细节

#### 1. 复用现有 GraphLocalEmitter

`GraphLocalEmitter` 已包含反向链接所需数据：

```typescript
// graph/local/{hash}/{slug}.json 结构
{
  "version": 1,
  "center": "current-page-slug",
  "depth": 1,
  "generatedAt": 1713273600000,
  "nodes": {
    "current-page-slug": { ... },
    "referrer-1": { ... },
    "referrer-2": { ... }
  },
  "edges": [
    { "source": "referrer-1", "target": "current-page-slug", "sourceField": "project" },
    { "source": "referrer-2", "target": "current-page-slug" }
  ]
}
```

**关键**：edges 中 `target === center` 的记录就是反向链接。

#### 2. 前端数据获取

```typescript
async function loadBacklinksJson(slug: string): Promise<BacklinksData> {
  const hash = await sha256(slug).then(h => h.slice(0, 4))
  const path = `${hash.slice(0,2)}/${hash.slice(2,4)}/${slug}`
  const response = await fetch(`/graph/local/${path}.json`)
  return response.json()
}
```

#### 3. 前端聚合计算

复用 `Backlinks.tsx` 中的 `buildAggregationTree` 逻辑，需迁移到 `backlinks.inline.ts`。

```typescript
// backlinks.inline.ts
function buildBacklinksFromGraph(data: LocalGraphData, config: AggregationConfig): SerializedNode {
  // 1. 过滤出反向链接
  const backlinks = data.edges
    .filter(e => e.target === data.center)
    .map(e => data.nodes[e.source])
    .filter(Boolean)

  // 2. 转换为 QuartzPluginData 格式（适配现有聚合逻辑）
  const files = backlinks.map(node => ({
    slug: node.slug,
    frontmatter: node.frontmatter,
    links: []
  }))

  // 3. 执行聚合
  return buildAggregationTree(files, config)
}
```

#### 4. 渲染流程

```typescript
document.addEventListener("nav", async () => {
  const slug = getCurrentSlug()
  const config = loadAggregationConfig() // 从页面 meta 或 JSON 读取
  const graphData = await loadBacklinksJson(slug)
  const tree = buildBacklinksFromGraph(graphData, config)
  renderBacklinks(tree)
})
```

---

## 详细利弊清单

### 方案A 修复（增量构建）

| 类别 | 内容 |
|------|------|
| **优势** | ✅ 改动最小（1-2处代码修改）<br>✅ 保留现有 SEO 优势<br>✅ 首屏性能不变<br>✅ 无需重写前端逻辑 |
| **劣势** | ⚠️ 依赖 allFiles 完整性（架构约束）<br>⚠️ 大量文件时构建耗时<br>⚠️ 修改聚合需重构建 |
| **风险** | 🟡 需验证 `allParsedFiles` 在增量模式下的完整性<br>🟡 需确认 `ContentIndex` 和 `ContentPage` 的数据一致性 |
| **测试要点** | 增量添加引用文档 → 验证目标页反向链接正确<br>增量修改引用文档 → 验证目标页反向链接更新<br>删除引用文档 → 验证目标页反向链接移除 |

### 方案B（运行时动态）

| 类别 | 内容 |
|------|------|
| **优势** | ✅ 天然支持增量构建（每个页面 JSON 独立）<br>✅ 可实现运行时聚合配置切换<br>✅ 构建性能提升<br>✅ 数据可单独缓存 |
| **劣势** | ❌ 额外网络请求（每个页面 +1 次）<br>❌ 前端复杂度增加<br>❌ SEO 影响（需预渲染或 SSR）<br>❌ 首屏加载延迟（需加载 JSON） |
| **新挑战** | 🔴 JSON 加载失败的处理<br>🔴 大量反向链接时的加载优化<br>🔴 与 SPA 路由的配合 |
| **资源消耗** | 内存：JSON 数据常驻（约几十 KB/页面）<br>网络：每次页面导航 +1 请求（可缓存）<br>CPU：前端聚合计算（客户端可接受） |

---

## 性能影响分析

### 方案A（修复后）

| 指标 | 影响 |
|------|------|
| HTML 体积 | 每个页面 +5-20KB（聚合数据） |
| 首屏加载 | 无额外延迟 |
| 构建时间 | 全量构建时增加 10-20%（聚合计算） |
| 增量构建 | 修复后与全量一致 |

### 方案B

| 指标 | 影响 |
|------|------|
| HTML 体积 | 无变化（数据外置） |
| 首屏加载 | +50-200ms（JSON 请求，取决于文件大小和网络） |
| 构建时间 | 减少 10-20%（聚合计算前移） |
| 增量构建 | 几乎无变化（JSON 按需生成） |
| 缓存命中 | 静态资源缓存，JSON 可长期缓存 |

---

## 用户体验影响

### 方案A（修复后）

| 场景 | 体验 |
|------|------|
| 新用户首次访问 | ✅ 无差异 |
| 增量更新后刷新 | ✅ 修复后正常显示 |
| SEO 效果 | ✅ 完整保留 |
| 无 JavaScript 环境 | ✅ 正常显示 |

### 方案B

| 场景 | 体验 |
|------|------|
| 新用户首次访问 | ⚠️ 首次加载稍慢（+100-300ms） |
| 增量更新后刷新 | ✅ 始终正确 |
| SEO 效果 | ❌ 需额外处理（如预渲染） |
| 无 JavaScript 环境 | ❌ 无反向链接显示 |
| 重复访问（缓存） | ✅ 无额外延迟 |
| 动态切换聚合维度 | ✅ 可实现（需 UI） |

---

## 推荐方案

### 短期：修复方案A

**理由**：
1. 改动量小，风险可控
2. 保留现有优势（SEO、首屏性能）
3. 可快速验证问题是否解决

**实施步骤**：
1. 修改 `build.ts`，确保 `ContentPage` 接收完整文件列表
2. 验证增量构建场景
3. 如仍有问题，再评估方案B

### 长期：考虑方案B

**触发条件**：
1. 方案A 修复后仍存在问题
2. 用户对动态聚合有强烈需求
3. 需要更好的增量构建性能

**前提条件**：
1. 实现 SSR 或预渲染解决 SEO 问题
2. 评估并优化 JSON 文件大小
3. 设计用户可配置的聚合 UI

---

## 实施检查清单

### 方案A 修复验证

```bash
# 测试用例
1. 全量构建 → 验证反向链接正常
2. 增量添加引用文档 → 验证目标页反向链接正确
3. 增量修改引用文档 → 验证目标页反向链接更新
4. 增量删除引用文档 → 验证目标页反向链接移除
5. reset=true 构建 → 验证与 reset=false 结果一致
```

### 方案B 迁移验证

```bash
# 测试用例
1. 全量构建 → 验证 JSON 文件生成正确
2. 检查反向链接 JSON 数据完整性
3. 验证前端加载和渲染逻辑
4. 验证增量构建后 JSON 更新
5. 性能测试：JSON 文件大小、网络请求时间
```

---

## 附录：关键代码位置

| 功能 | 文件位置 |
|------|---------|
| ContentPage emitter | `client/quartz/plugins/emitters/contentPage.tsx` |
| Backlinks 组件 | `client/quartz/components/Backlinks.tsx` |
| Backlinks 前端脚本 | `client/quartz/components/scripts/backlinks.inline.ts` |
| 局部图谱生成 | `client/quartz/plugins/emitters/graphLocal.tsx` |
| 构建入口 | `client/quartz/build.ts` |
| 聚合配置读取 | `client/quartz.layout.ts` |
