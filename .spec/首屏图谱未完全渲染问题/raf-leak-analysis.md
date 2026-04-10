# RAF 泄漏问题深度分析

## 什么是 RAF

RAF (requestAnimationFrame) 是浏览器提供的动画 API：

```javascript
// 告诉浏览器：下一帧重绘前执行回调
const rafId = requestAnimationFrame(callback);

// 不需要时可以取消
cancelAnimationFrame(rafId);
```

### RAF 循环模式

正常动画会形成自我延续的循环：

```javascript
function animate(time) {
  // 1. 更新画面
  updateAndRender();
  
  // 2. 调度下一帧（形成无限循环）
  requestAnimationFrame(animate);
}

// 启动循环
requestAnimationFrame(animate);
```

**关键问题**：如果调度前没有检查停止条件，这个循环会**永远运行**！

## 从日志看到的真相

### 首屏未加载完.log 时间线

```
[07:33] prenav 触发 → cleanup → rafs=0
[07:57] Simulation 创建
[08:31] Pixi init 开始
[08:31] prenav 触发 → 用户点击了！但 RAF=0（还没启动）
[08:31] cleanup 完成 → rafs=0
[08:31] 新页面 render 开始
...
[09:34] Pixi init 完成（旧渲染）
[09:36] 启动动画循环 ← 旧 RAF 启动！
...
[09:73] prenav 触发 → RAF=133！泄漏了！
```

### 根本原因

**prenav 和 RAF 启动存在竞态窗口**：

```
旧渲染流程：Pixi init → 启动 RAF → 每帧自我延续
                ↑
用户点击：   prenav（此时 RAF 可能还没启动）
                ↑
新渲染流程：开始执行

结果：旧 RAF 在新渲染之后启动， cleanup 永远清理不到！
```

### 泄漏数量分析

| 场景 | RAF 数量 | 说明 |
|------|---------|------|
| 首屏未加载完 | 133 | 快速跳转，RAF 刚启动就被打断 |
| 首屏完整加载 | 674 | 等待时间长，RAF 运行了更多帧 |

**674 个 RAF ≈ 11 秒 @ 60fps**（674/60 ≈ 11.2）

说明用户等了约 11 秒才点击，这期间 RAF 一直在运行！

## 为什么之前的修复无效

### 修复尝试 1：全局 RAF Set

```javascript
const activeRafIds = new Set();

function animate(time) {
  if (!checkGeneration(gen)) return;  // 检查世代
  
  // 渲染...
  
  const rafId = requestAnimationFrame(animate);
  activeRafIds.add(rafId);  // 记录 ID
}
```

**问题**：
- `checkGeneration` 在函数**开始**时检查
- 但 `requestAnimationFrame(animate)` 在函数**末尾**调度
- 如果调度时世代已过期，**下一帧的 animate 已经被调度了**！

### 泄漏路径

```
第 N 帧：
  animate() 开始
  checkGeneration(gen=0) → true（通过）
  渲染...
  requestAnimationFrame(animate) → 调度第 N+1 帧（ID=100）
  
用户导航：
  renderGeneration++ → 1
  
第 N+1 帧：
  animate() 开始
  checkGeneration(gen=0) → false（过期！）
  return（停止渲染）
  
  但是！animate 函数内部的 RAF 调度在 return 之前！
  等等，不对... 让我重新分析
```

**实际上代码是**：

```javascript
function animate(time) {
  if (appDestroyed || !checkGeneration(generation)) return;  // 第 1 行就检查
  
  // 渲染逻辑...
  
  // 只有检查通过才调度下一帧
  if (!appDestroyed && checkGeneration(generation)) {
    animationId = requestAnimationFrame(animate);
    activeRafIds.add(animationId);
  }
}
```

这个逻辑应该没问题... 那为什么还有 133/674 个 RAF？

## 真正的泄漏源

仔细看日志：

```
[09:34] Pixi Application 初始化完成
[09:36] 启动动画循环
[09:36] Rendered graph for ...
[09:36] renderGraph 函数即将返回
[09:73] cleanupLocalGraphs, rafs=133
```

从 "Pixi init 完成" 到 "cleanup" 有 **37 帧** 的时间（73-36=37ms @ 60fps）。

这意味着：**旧渲染的 RAF 在 cleanup 之前已经运行了很多帧！**

但等等，cleanup 时应该能清理到这些 RAF 啊？

### 关键发现

看代码中的 RAF 追踪逻辑：

```javascript
function animate(time) {
  if (appDestroyed || !checkGeneration(generation)) return;
  // ... 渲染 ...
  if (!appDestroyed && checkGeneration(generation)) {
    animationId = requestAnimationFrame(animate);
    activeRafIds.add(animationId);  // 添加到追踪
  }
}

// 启动时
animationId = requestAnimationFrame(animate);
if (animationId !== null) {
  activeRafIds.add(animationId);
}
```

**问题 1**：每次动画帧都创建新的 RAF ID，旧的 ID 没有从 Set 中删除！

```
第 1 帧：animationId = 1, activeRafIds = {1}
第 2 帧：animationId = 2, activeRafIds = {1, 2}  ← 1 没删除！
第 3 帧：animationId = 3, activeRafIds = {1, 2, 3}
...
第 N 帧：activeRafIds = {1, 2, 3, ..., N}  ← 爆炸！
```

**问题 2**：cleanup 时取消所有这些 ID，但很多 ID 对应的 RAF 已经执行过了：

```javascript
for (const rafId of activeRafIds) {
  cancelAnimationFrame(rafId);  // 取消已经执行的 RAF 是无效的
}
```

## 正确的 RAF 追踪方式

**只追踪当前活跃的 RAF，而不是历史所有 RAF！**

```javascript
let currentRafId = null;

function animate(time) {
  if (appDestroyed || !checkGeneration(generation)) {
    currentRafId = null;  // 清理引用
    return;
  }
  
  // 渲染...
  
  // 调度下一帧
  currentRafId = requestAnimationFrame(animate);
}

// 启动
currentRafId = requestAnimationFrame(animate);

// 清理时
cleanup = () => {
  if (currentRafId !== null) {
    cancelAnimationFrame(currentRafId);
    currentRafId = null;
  }
};
```

或者**只用一个 flag 控制，不追踪 ID**：

```javascript
let stopAnimation = false;

function animate(time) {
  if (stopAnimation) return;  // 简单有效！
  
  // 渲染...
  
  requestAnimationFrame(animate);  // 继续调度
}

// 清理时
cleanup = () => {
  stopAnimation = true;  // 下一帧就会停止
};
```

## 修复方案

### 方案 A：修复现有 RAF 追踪（复杂）
- 只追踪当前 RAF ID，不是历史所有
- 每次调度前删除旧的

### 方案 B：使用 stopAnimation flag（简单推荐）
- 不用 Set 追踪，只用布尔值
- cleanup 时设置 flag，下一帧自动停止

### 方案 C：首屏守护（最简单可靠）
- 等首屏完全加载后再允许导航
- 彻底避免竞态

## 推荐

**方案 B + 方案 C 结合**：
1. 简化 RAF 控制为 flag 模式
2. 添加首屏守护作为兜底
