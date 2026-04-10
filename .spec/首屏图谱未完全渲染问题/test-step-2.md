# 第二步测试：RAF 循环可取消

## 修改内容

1. 添加了全局 `activeRafIds` Set 追踪所有已调度的 RAF
2. 添加了 `cancelAllRafs()` 函数取消所有 RAF 回调
3. 修改 `animate` 函数：
   - 启动时记录 RAF ID
   - 继续调度下一帧前检查 generation
   - 调度时记录新的 RAF ID
4. 在 `cleanupLocalGraphs` 中调用 `cancelAllRafs()`

## 预期行为

快速导航时，控制台应该显示：
```
[Graph] Force stopping X leaked simulations
[Graph] Cancelling Y RAF callbacks
```

## 测试步骤

1. 构建并部署到测试环境
2. 打开浏览器控制台（F12）
3. **关键测试**：首屏加载后，**不等** D3 收敛就快速点击目录跳转
4. 观察日志：
   - 应该看到 `Cancelling X RAF callbacks`
   - 后续页面渲染应该正常速度

5. **压力测试**：连续快速跳转 5-10 次
   - 每次都应该看到 cleanup 日志
   - Pixi 初始化时间应该稳定（不递增）
   - 浏览器不应卡顿

## 如何判断成功

✅ **成功标志**：
- 看到 `Cancelling X RAF callbacks` 日志
- 快速连续导航后浏览器仍然流畅
- Pixi 初始化时间稳定

❌ **失败标志**：
- RAF 继续泄漏，`activeRafIds.size` 递增
- 快速导航后浏览器变卡
- Pixi 初始化时间持续增长

## 与前一步对比

| 指标 | 第一步 | 第二步 |
|------|--------|--------|
| Simulation 泄漏 | ✅ 修复 | ✅ 修复 |
| RAF 泄漏 | ❌ 未修复 | ✅ 修复 |
| 快速导航后流畅度 | 可能卡顿 | 应该流畅 |
