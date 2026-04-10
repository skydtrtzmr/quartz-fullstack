# Graph 竞态条件问题分析

## 问题现象

首屏没有等 D3 simulation 收敛就点目录跳转，后续所有跳转后的图谱渲染都会变慢。

## 关键日志分析 (`console首屏没有加载完2.log`)

### 时间线梳理

```
Line 27: [DEBUG] D3 simulation 初始化完成  ← MAPWD8 首屏
Line 30: [DEBUG] 开始初始化 Pixi Application
Line 31: [prenav] 保存滚动位置              ← ⚠️ 用户点击跳转！
...
Line 56: [DEBUG] Pixi Application 初始化完成  ← MAPWD6 新渲染
Line 57: [Graph] 渲染完成后发现世代已过期 (0 !== 1)，立即执行 cleanup
Line 60: [DEBUG] Pixi Application 初始化完成  ← ⚠️ MAPWD8 旧 Pixi 完成！
Line 61: [DEBUG] 启动动画循环                ← ⚠️ MAPWD8 旧 RAF 启动！
Line 66: [DEBUG] D3 simulation 布局计算完成   ← ⚠️ MAPWD8 simulation 后台运行到收敛
```

### 核心问题暴露

1. **旧渲染的 Pixi 不可取消**：`await app.init()` 一旦开始无法中断
   - Line 60: 即使 generation 已变，旧 Pixi 初始化完成后仍继续执行
   - Line 61: 旧 RAF 动画循环启动，且**永远不会停止**（因为 cleanup 函数未被注册）

2. **D3 Simulation 泄漏**：
   - Line 66: 第一个页面的 simulation 在后台继续运行直到收敛
   - `.stop()` 只是设置标志，**正在运行的 tick 不会立即停止**

3. **Cleanup 函数丢失**：
   ```typescript
   const cleanup = await renderGraph(container, slug, thisGeneration)
   if (cleanup && thisGeneration === renderGeneration) {
     localGraphCleanups.push(cleanup)  // ❌ 如果 generation 已变，cleanup 永远不会被调用！
   }
   ```

## 根本原因

### 1. RAF 循环自我延续

```typescript
function animate(time: number) {
  if (stopAnimation || !checkGeneration(generation)) {
    return  // ❌ 只是 return，RAF 已经调度了下一帧！
  }
  // ...
  requestAnimationFrame(animate)  // 这里会继续调度
}
```

即使 `checkGeneration` 返回 false，**已经调度的 RAF 回调仍会继续执行**。

### 2. D3 Simulation 不可取消

```typescript
const simulation = forceSimulation(...)  // 开始运行
// ... await app.init() 期间用户导航
simulation.stop()  // 设置停止标志，但当前 tick 会继续完成
```

### 3. 资源泄漏累积

每次快速导航都会泄漏：
- 1 个 RAF 循环（永远运行）
- 1 个 D3 simulation（运行到收敛）
- 1 个 Pixi Application（GPU/内存占用）

**多个 simulation 同时运行 = CPU 竞争 = 后续渲染变慢**

## 修复方案

### 方案 1: 全局追踪活跃 Simulation（推荐）

```typescript
// 模块顶部
const activeSimulations: Set<Simulation<any, any>> = new Set()
let activeRafIds: Set<number> = new Set()

// cleanupLocalGraphs 强制停止所有
function cleanupLocalGraphs() {
  renderGeneration++
  
  // 强制停止所有活跃 simulation
  for (const sim of activeSimulations) {
    sim.stop()
  }
  activeSimulations.clear()
  
  // 取消所有 RAF
  for (const rafId of activeRafIds) {
    cancelAnimationFrame(rafId)
  }
  activeRafIds.clear()
  
  // ... 原有 cleanup
}

// renderGraph 中
const simulation = forceSimulation(...)
activeSimulations.add(simulation)

let rafId: number | null = null
function animate(time: number) {
  if (stopAnimation || !checkGeneration(generation)) {
    if (rafId !== null) {
      activeRafIds.delete(rafId)
      rafId = null
    }
    return
  }
  // ...
  rafId = requestAnimationFrame(animate)
  activeRafIds.add(rafId)
}
```

### 方案 2: Pixi 初始化前检查（次要）

```typescript
const app = new Application()
const initPromise = app.init({...})

// 设置检查点，允许在初始化期间取消
await initPromise

if (!checkGeneration(generation)) {
  app.destroy()  // 立即销毁
  return () => {}
}
```

### 方案 3: 使用 AbortController（可选）

对于 fetch 请求可以使用 AbortController，但 Pixi 和 D3 不支持。

## 验证方法

修复后应该能在日志中看到：
1. `[Graph] Force stopped X simulations` - 强制停止旧 simulation
2. `[Graph] Cancelled Y RAF callbacks` - 取消 RAF 回调
3. 多次快速导航后，Pixi 初始化时间不再递增

## 相关文件

- `client/quartz/components/scripts/graph.inline.ts` - 主要修复目标
- `client/quartz/components/scripts/graph3.inline.ts` - 实际部署版本

---

# Explorer 竞态条件分析

## Explorer 异步操作盘点

Explorer 也存在异步操作，需要检查是否有类似问题：

### 1. 异步 Trie 构建

```typescript
// Line 963-989
async function initializeFileTree(opts: ParsedOptions): Promise<FileTrieNode> {
  const data = await fetchData  // 等待数据
  const entries = Object.entries(data) as [FullSlug, ContentDetails][]
  const trie = FileTrieNode.fromEntries(entries)  // 同步但耗时的操作
  // ...
  return trie
}
```

**潜在问题**：`FileTrieNode.fromEntries` 遍历 8621 条数据，可能阻塞主线程 500-900ms。

### 2. 缓存恢复后的异步初始化

```typescript
// Line 1176-1207: F5 刷新后的异步路径
const initExplorerAsync = async () => {
  const trie = await initializeFileTree(opts)  // 异步构建
  // ... 大量同步计算
  flatNodes = flattenTreeRoot(currentTrie)  // 遍历整棵树
  setupFlatVirtualScroll(explorerUl, currentSlug, opts)  // 设置 RAF 监听
}
setTimeout(() => initExplorerAsync(), 0)  // 延迟执行
```

**潜在问题**：
- `setTimeout(..., 0)` 让初始化推迟到事件循环末尾
- 如果用户在此期间导航，`initExplorerAsync` 仍会继续执行
- 但**后果不严重**：只是浪费 CPU 计算，不会产生持续的副作用（不像 Graph 的 RAF）

### 3. 虚拟滚动的 RAF

```typescript
// Line 664-684
function setupFlatVirtualScroll(explorerUl: Element, currentSlug: FullSlug, opts: ParsedOptions) {
  let ticking = false
  const handleScroll = () => {
    if (ticking || isNavigating) return
    ticking = true
    requestAnimationFrame(() => {
      updateFlatVirtualScroll(explorerUl as HTMLElement, currentSlug, opts)
      ticking = false
    })
  }
  explorerUl.addEventListener("scroll", handleScroll, { passive: true })
  window.addCleanup(() => explorerUl.removeEventListener("scroll", handleScroll))
}
```

**评估**：
- RAF 只在滚动时触发，不是持续运行
- 使用了 `window.addCleanup` 清理事件监听
- **风险较低**：不会造成 Graph 那样的持续资源泄漏

### 4. isNavigating 锁

```typescript
// Line 293-306, 1144-1153
isNavigating = true
// ... 执行 DOM 操作 ...
setTimeout(() => { isNavigating = false }, 100)  // 延迟解锁
```

**潜在问题**：
- `isNavigating` 是全局变量，没有 generation 机制
- 如果快速连续导航，可能出现状态混乱
- 但**后果有限**：最多是冗余的虚拟滚动更新

## Explorer vs Graph 对比

| 维度 | Graph | Explorer |
|------|-------|----------|
| 持续运行的 RAF | ✅ 有（每帧渲染） | ❌ 无（仅滚动时） |
| CPU 密集型后台任务 | ✅ D3 simulation | ⚠️ Trie 构建（一次性） |
| 不可取消的异步操作 | ✅ Pixi init | ❌ 无 |
| 资源泄漏累积 | ✅ 严重 | ⚠️ 轻微（计算浪费） |
| 清理机制 | ❌ 依赖 cleanup 函数 | ✅ addCleanup |

## 结论

**Explorer 的问题不严重**：
1. 没有持续运行的 RAF 循环
2. 没有不可取消的资源密集型操作
3. 异步操作主要是"一次性"的计算，不会持续占用资源

**但仍有优化空间**：
1. 给 `initExplorerAsync` 加上 generation 检查，避免浪费计算
2. 考虑使用 Web Worker 处理 Trie 构建（大站点时 900ms 会阻塞 UI）

## 建议修复（Explorer）

```typescript
// 添加 generation 机制
let explorerGeneration = 0

async function setupExplorer3(currentSlug: FullSlug) {
  const myGeneration = ++explorerGeneration  // 递增
  
  // ...
  
  const initExplorerAsync = async () => {
    if (explorerGeneration !== myGeneration) {
      console.log('[Explorer] Stale generation, skipping async init')
      return
    }
    // ...
  }
}
```

**优先级**：低。Graph 的问题是 P0，Explorer 是 P2。
