# Quartz Graph: v4 (client) vs v5 (quartz-community/graph) 实现对比

## 1. 整体架构

| 维度 | v4 (client) | v5 (社区插件) |
|------|-------------|---------------|
| **代码位置** | 内置: `quartz/components/` | 外部: `github:quartz-community/graph` |
| **Graph.tsx** | 有 | 有 (几乎相同) |
| **graph.inline.ts** | 有 2 个版本 (`graph`, `graph2`) | 有 1 个版本 |
| **inline 代码风格** | TypeScript (import 语法) | 纯 JavaScript (兼容浏览器) |
| **库加载** | bundler 打包 (esbuild) | CDN 动态加载 |

## 2. 库加载方式（关键差异）

### v4 (client)
```typescript
// 使用 ES6 import，由 esbuild 打包
import { forceSimulation, forceManyBody, ... } from "d3"
import { Text, Graphics, Application, ... } from "pixi.js"
```

### v5 (社区插件)
```javascript
// 动态加载 CDN
function loadScript(src) {
  return new Promise(function (resolve, reject) {
    var script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

Promise.all([
  loadScript("https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"),
  loadScript("https://cdn.jsdelivr.net/npm/pixi.js@8/dist/pixi.js"),
]).then(function () {
  initGraph();
});
```

## 3. 竞态处理（核心差异）

### v5 (社区插件) - 世代计数器方案
```javascript
// IIFE 顶部
var currentRenderGeneration = 0;

async function renderGraph(graph, fullSlug, renderGeneration) {
  // 检查是否被更新的渲染取代
  if (renderGeneration !== undefined && renderGeneration !== currentRenderGeneration) {
    console.log("[Graph] Stale render, skipping");
    return function () {};
  }
  // ... 渲染逻辑
}

function renderLocal() {
  cleanupLocal();
  var thisGeneration = ++currentRenderGeneration;  // 递增世代
  var slug = getSlugFromUrl();
  
  renderGraph(container, slug, thisGeneration)
    .then(function (cleanup) {
      // 只有世代匹配才注册 cleanup
      if (thisGeneration === currentRenderGeneration) {
        localCleanups.push(cleanup);
      }
    });
}

// 监听 prenav 进行清理
document.addEventListener("prenav", function () {
  cleanupLocal();
  cleanupGlobal();
});
```

### v4 (client) - graph.inline.ts
```typescript
// 无世代计数器，依赖 cleanup 数组
let localGraphCleanups: (() => void)[] = []

function cleanupLocalGraphs() {
  for (const cleanup of localGraphCleanups) {
    cleanup()
  }
  localGraphCleanups = []
}

// 问题：await renderGraph 期间导航，cleanup 数组为空
localGraphCleanups.push(await renderGraph(container as HTMLElement, slug))
```

### v4 (client) - graph2.inline.ts
```typescript
// 尝试使用全局标志，但方案不完整
if (!(window as any).graph2Initialized) {
  (window as any).graph2Initialized = true
  // IIFE 单例模式
}
// 没有世代计数器
```

## 4. 代码风格对比

| 特性 | v4 (client) | v5 (社区插件) |
|------|-------------|---------------|
| **语言** | TypeScript | JavaScript (无类型) |
| **模块系统** | ES6 import | 全局变量 (window.d3, window.PIXI) |
| **函数风格** | 箭头函数 + async/await | 传统函数 + Promise |
| **闭包** | IIFE 单例 | IIFE 单例 |
| **类型安全** | 有 | 无 (ts-nocheck) |

## 5. 功能特性对比

| 功能 | v4 (client) | v5 (社区插件) |
|------|-------------|---------------|
| **预计算局部图谱** | ✅ `GraphLocalEmitter` | ❌ 无 |
| **虚拟节点** | ✅ 支持 | ❌ 无 |
| **边标签 (sourceField)** | ✅ `graph2.inline.ts` | ❌ 无 |
| **展开/收起边缘节点** | ✅ `graph2.inline.ts` | ❌ 无 |
| **对象池优化** | ✅ `graph2.inline.ts` | ❌ 无 |
| **箭头方向指示** | ✅ `graph2.inline.ts` | ❌ 无 |
| **世代计数器防竞态** | ❌ 无 | ✅ 有 |
| **多域名 basePath** | ✅ 有 | ✅ 有 (从 `@quartz-community/utils` 导入) |

## 6. v5 社区插件的关键实现细节

### 6.1 世代计数器机制
```javascript
var currentRenderGeneration = 0;

function renderLocal() {
  cleanupLocal();
  var thisGeneration = ++currentRenderGeneration;  // 新渲染 = 新世代
  
  renderGraph(container, slug, thisGeneration)
    .then(function (cleanup) {
      // 只有是当前世代才保存 cleanup
      if (thisGeneration === currentRenderGeneration) {
        localCleanups.push(cleanup);
      }
    });
}

// 导航时递增世代，使旧渲染自我废弃
document.addEventListener("prenav", function () {
  currentRenderGeneration++;  // 关键！旧渲染会检测到这个变化
  cleanupLocal();
  cleanupGlobal();
});
```

### 6.2 renderGraph 内的检查点
```javascript
async function renderGraph(graph, fullSlug, renderGeneration) {
  // 检查点 1: 开始前
  if (renderGeneration !== currentRenderGeneration) {
    return function () {};
  }
  
  var data = await fetchData;
  // 检查点 2: 数据加载后
  if (renderGeneration !== currentRenderGeneration) {
    return function () {};
  }
  
  // ... 更多检查点
}
```

### 6.3 cleanup 时机
```javascript
document.addEventListener("prenav", function () {
  cleanupLocal();   // 导航前清理
  cleanupGlobal();
});
```

## 7. v5 相比 v4 的优缺点

### v5 优势
1. **竞态处理正确**：世代计数器机制有效避免了 async 竞态
2. **CDN 加载**：不依赖 bundler，部署更简单
3. **浏览器兼容性**：纯 JavaScript，无 ES6+ 语法

### v5 劣势
1. **功能缺失**：无预计算、无边标签、无展开/收起
2. **性能**：CDN 加载可能较慢，无对象池优化
3. **类型安全**：无 TypeScript 类型检查
4. **维护性**：代码压缩为单文件，难维护

## 8. 给你的建议

### 方案 A: 采用 v5 的世代计数器（推荐）
将 v5 的 `currentRenderGeneration` 机制移植到 v4 的 `graph.inline.ts`：

```typescript
// 在 graph.inline.ts 中添加
let renderGeneration = 0

async function renderGraph(graph: HTMLElement, fullSlug: FullSlug, gen: number) {
  if (gen !== renderGeneration) return () => {}
  
  await fetchData
  if (gen !== renderGeneration) return () => {}
  
  // ... 其他检查点
}

// cleanupLocalGraphs 中递增世代
function cleanupLocalGraphs() {
  renderGeneration++  // 关键！使旧渲染自我废弃
  for (const cleanup of localGraphCleanups) cleanup()
  localGraphCleanups = []
}
```

### 方案 B: 混合方案
保留 v4 的预计算系统，但采用 v5 的世代计数器防竞态。

### 方案 C: 贡献给社区
将你的 `GraphLocalEmitter` 预计算系统贡献给 `quartz-community/graph` 插件。

## 9. 关键代码差异行数

| 文件 | v4 (client) | v5 (社区插件) | 差异 |
|------|-------------|---------------|------|
| `graph.inline.ts` | ~680 行 | ~774 行 | v5 更完整 |
| `Graph.tsx` | ~135 行 | ~114 行 | 几乎相同 |
| 防竞态机制 | ❌ | ✅ | v5 胜出 |
| 预计算支持 | ✅ | ❌ | v4 胜出 |
