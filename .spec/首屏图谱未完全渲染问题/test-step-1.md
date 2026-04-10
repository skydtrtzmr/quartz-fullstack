# 第一步测试：Simulation 全局追踪

## 修改内容

1. 添加了全局 `activeSimulations` Set 追踪所有活跃的 D3 simulation
2. 添加了 `forceStopAllSimulations()` 函数强制停止泄漏的 simulation
3. 在 `cleanupLocalGraphs()` 中调用强制停止
4. 在 `renderGraph` 中创建 simulation 时添加到追踪
5. 在 cleanup 函数中从追踪中移除

## 预期行为

快速导航时，控制台应该显示：
```
[Graph] Force stopping X leaked simulations
```

## 测试步骤

1. 构建并部署到测试环境
2. 打开浏览器控制台（F12）
3. **测试场景 A**：首屏加载完成后，等待 D3 simulation 收敛，然后点击目录跳转
   - 预期：`activeSimulations` 应该正常清理，大小为 0 或 1
   
4. **测试场景 B**（关键）：首屏加载后，**不等** "D3 simulation 布局计算完成" 就快速点击目录跳转
   - 预期：应该看到 `[Graph] Force stopping 1 leaked simulations`
   - 后续页面渲染应该**不会**变慢

5. 连续快速跳转 3-5 次，观察：
   - `activeSimulations` 大小是否保持在合理范围（0-1）
   - Pixi 初始化时间是否不再递增

## 如何判断成功

✅ **成功标志**：
- 看到 `Force stopping X leaked simulations` 日志
- 快速导航后后续页面渲染速度正常
- `activeSimulations.size` 不会持续累积

❌ **失败标志**：
- `activeSimulations.size` 持续递增
- 快速导航后 Pixi 初始化时间越来越长
- 没有 `Force stopping` 日志出现

## 已知限制（第一步）

- RAF 循环仍然可能泄漏（第二步修复）
- 这只是防止 simulation 泄漏，完整的 RAF 修复在第二步
