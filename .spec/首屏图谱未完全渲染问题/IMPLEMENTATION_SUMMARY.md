# Graph 竞态条件修复 - 实施总结

## 修改文件

- `client/quartz/components/scripts/graph.inline.ts`

## 修改内容概览

### 1. 新增全局追踪变量（Line 31-59）

```typescript
// 追踪活跃的 D3 simulation
const activeSimulations: Set<Simulation<NodeData, LinkData>> = new Set()

// 追踪已调度的 RAF ID
const activeRafIds: Set<number> = new Set()
```

### 2. 新增强制清理函数（Line 36-58）

```typescript
function forceStopAllSimulations() {...}
function cancelAllRafs() {...}
```

### 3. 修改 cleanupLocalGraphs（Line 715-735）

```typescript
function cleanupLocalGraphs() {
  renderGeneration++
  forceStopAllSimulations()  // 新增
  cancelAllRafs()            // 新增
  // ... 原有 cleanup 逻辑
}
```

### 4. 修改 renderGraph（多处）

- **开始处**（Line 121）：打印资源状态
- **创建 simulation 后**（Line 289-290）：添加到追踪
- **Pixi 初始化**（Line 480-491）：计时和过期检查
- **Animate 函数**（Line 685-698）：RAF ID 追踪和条件调度
- **Cleanup 函数**（Line 705-706）：从追踪中移除

## 测试步骤（按顺序）

### Step 1: 构建部署
```bash
cd client
npm run build  # 或您的构建命令
```

### Step 2: 基础功能测试
1. 打开页面，等待首屏完全加载
2. 点击目录跳转
3. 观察控制台日志，确认：
   - 正常渲染日志
   - Pixi 初始化时间合理（< 1000ms）

### Step 3: 快速导航测试（关键）
1. 刷新页面
2. **不等** D3 simulation 收敛（不等 "布局计算完成" 日志）
3. 立即点击目录跳转
4. 观察控制台，确认：
   - `Force stopping X leaked simulations`
   - `Cancelling Y RAF callbacks`
   - `resources after: sims=0, rafs=0`

### Step 4: 压力测试
1. 连续快速点击目录 5-10 次（每次都不等 D3 收敛）
2. 观察：
   - 浏览器是否保持流畅
   - Pixi 初始化时间是否稳定
   - 资源数量是否不累积

### Step 5: 性能监控（可选）
使用 Chrome DevTools Performance Monitor 观察：
- JS event listeners 数量
- Memory 使用情况

## 预期结果

| 场景 | 预期日志 | 预期性能 |
|------|----------|----------|
| 正常加载 | `Pixi initialized in XXXms` | 正常 |
| 快速导航 | `Force stopping...` + `Cancelling...` | 正常 |
| 压力测试 | 每次都有 cleanup 日志 | 不卡顿，时间稳定 |

## 回滚方案

如果出现问题，直接恢复修改前的 `graph.inline.ts`：

```bash
git checkout client/quartz/components/scripts/graph.inline.ts
```

## 相关文档

- `.spec/graph-race-condition-analysis.md` - 问题分析
- `.spec/test-step-1.md` - 第一步测试
- `.spec/test-step-2.md` - 第二步测试
- `.spec/test-final.md` - 完整测试
