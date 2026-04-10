# 最终测试：完整的竞态条件修复

## 所有修改汇总

### 第一步：Simulation 全局追踪
- `activeSimulations`: Set 追踪所有活跃的 D3 simulation
- `forceStopAllSimulations()`: 强制停止所有泄漏的 simulation

### 第二步：RAF 可取消
- `activeRafIds`: Set 追踪所有已调度的 RAF ID
- `cancelAllRafs()`: 取消所有 RAF 回调
- 修改 `animate()` 函数，确保 generation 过期时不再调度下一帧

### 第三步：调试日志增强
- `renderGraph` 开始时打印资源状态
- `Pixi` 初始化计时
- `cleanupLocalGraphs` 前后打印资源状态

## 预期日志输出

### 正常加载（首屏）
```
[Graph] renderGraph start for work/问答/MAPWD8, gen=0, resources: sims=0, rafs=0
[Graph] Simulation added to tracking, total: 1
[Graph] Pixi initialized in 743.21ms
[Graph] Rendered graph for work/问答/MAPWD8. Containers: 1
[Graph] renderGraph 函数即将返回
```

### 快速导航（不等 D3 收敛）
```
[Graph] cleanupLocalGraphs, new generation: 1, resources before cleanup: sims=1, rafs=1
[Graph] Force stopping 1 leaked simulations
[Graph] Cancelling 1 RAF callbacks
[Graph] cleanupLocalGraphs completed, resources after: sims=0, rafs=0
[Graph] renderGraph start for work/问答/MAPWD6, gen=1, resources: sims=0, rafs=0
[Graph] Simulation added to tracking, total: 1
[Graph] Pixi initialized in 380.50ms
```

### 检测到过期渲染
```
[Graph] Pixi initialized in 534.21ms
[Graph] Stale render (after Pixi init, took 534.21ms), destroying app
[Graph] Resources before cleanup: simulations=1, rafs=1
[Graph] Simulation cleaned up, remaining: 0
```

## 完整测试步骤

### 测试 1：正常加载
1. 刷新页面
2. 等待 D3 simulation 收敛（"D3 simulation 布局计算完成"）
3. 点击目录跳转
4. **预期**：Pixi 初始化时间正常（< 1000ms）

### 测试 2：快速导航（关键）
1. 刷新页面
2. **不等** D3 收敛，立即点击目录跳转
3. **预期**：
   - 看到 `Force stopping X leaked simulations`
   - 看到 `Cancelling Y RAF callbacks`
   - 后续页面渲染速度正常

### 测试 3：压力测试
1. 刷新页面
2. 连续快速点击目录跳转 5-10 次（每次都不等 D3 收敛）
3. **预期**：
   - 每次都能看到 cleanup 日志
   - `sims` 和 `rafs` 数量不会持续累积
   - 浏览器保持流畅，不卡顿
   - Pixi 初始化时间稳定（不递增）

### 测试 4：资源泄漏检查
1. 打开 Chrome DevTools → Performance Monitor
2. 观察 JS event listeners 和 Memory 使用
3. 连续快速导航
4. **预期**：
   - Event listeners 数量不持续增长
   - Memory 使用稳定（可能会有 GC 波动，但无明显泄漏趋势）

## 如何判断完全成功

✅ **全部成功标志**：
1. 所有测试场景都有预期的日志输出
2. Pixi 初始化时间稳定（不随导航次数递增）
3. 浏览器在快速导航后保持流畅
4. Performance Monitor 显示无资源泄漏

⚠️ **部分成功**（可接受）：
- 偶尔看不到 `Force stopping` 日志（说明 generation 检查在更早阶段拦截了）
- 但 Pixi 初始化时间仍然稳定

❌ **失败标志**：
- `sims` 或 `rafs` 数量持续递增
- Pixi 初始化时间越来越长
- 浏览器在快速导航后变卡
- 没有看到任何 cleanup 日志

## 如果失败，检查点

1. **确认代码已部署**：检查浏览器 Sources 面板中的代码是否包含修改
2. **确认 prenav 事件触发**：添加 `console.log` 在 `prenav` 监听器中
3. **确认 generation 递增**：检查 `cleanupLocalGraphs` 日志中的 generation 值
4. **检查 Pixi 版本**：确认 Pixi 的 `app.destroy()` 是否正确释放资源
