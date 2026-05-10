# 图谱聚合功能规格

## 一、概述

本文档描述图谱（力导向图）的聚合功能实现。聚合用于将大量边缘节点分组为聚合节点，降低图谱视觉复杂度。

### 配置来源

通过 `quartz.layout.json` 中 `graph.aggregation` 配置，与 `backlinks.aggregation` 使用**完全相同的结构**（`AggregationConfig`）：

```json
{
  "graph": {
    "aggregation": {
      "fields": [
        { "field": "date", "granularity": "year", "order": 1 },
        { "field": "type", "order": 2 }
      ]
    }
  }
}
```

---

## 二、核心概念

### 2.1 节点分类

| 类型 | 定义 | 示例 |
|------|------|------|
| 核心节点 | 链接数 > 1 的节点 | 有多个入链/出链的页面 |
| 边缘节点 | 链接数 = 1 的节点 | 只有一个引用的页面 |
| 单链接边缘节点 | 仅与一个核心节点相连的边缘节点（聚合候选） | |
| 聚合节点 | 替代一组边缘节点的虚拟节点 | `agg:{coreId}:{field}:{key}` |
| 子级聚合节点 | 在聚合节点展开后再按下一字段分组的节点 | `agg:sub:{parentId}:{field}:{key}` |

### 2.2 聚合条件

- 仅对**单链接边缘节点**进行聚合（避免多核心归属冲突）
- 同一分组内的节点数量必须 **> 1** 才创建聚合节点
- 虚拟节点（无 filePath）参与普通字段聚合

### 2.3 数据结构

```typescript
/** 聚合节点信息（构建时创建一级，展开时创建子级） */
interface AggregationNodeInfo {
  node: NodeData              // 聚合节点本身
  coreId: SimpleSlug          // 所属核心节点 ID（子级则指向父聚合节点）
  childNodes: NodeData[]      // 直接子节点
  childLinks: LinkData[]      // 子节点的边
  remainingFields: FieldAggregation[]  // 剩余未处理的字段层级
  currentField: string        // 当前层使用的字段名
}
```

```typescript
/** NodeData 中与聚合相关的字段 */
interface NodeData {
  isAggregation?: boolean      // 是否为聚合节点
  aggCollapsedRadius?: number  // 收起时的半径（基于子节点数量 sqrt 增长）
  aggExpandedRadius?: number   // 展开后的半径（动态调整）
  aggChildCount?: number       // 包含的子节点数量
}
```

---

## 三、多级聚合流程

### 3.1 构建时（一级聚合）

1. 遍历每个核心节点的单链接边缘节点
2. 按 `fields[0]` 字段值分组
3. 分组大小 > 1 的创建一级聚合节点
4. 存储 `remainingFields = fields.slice(1)`
5. 将聚合节点替换原始边缘节点加入 `nodeToEdgeNodes`

### 3.2 展开时（子级聚合）

用户点击一级聚合节点:

1. `expandNode()` 检测 `remainingFields.length > 0`
2. 调用 `createSubAggNodes()` 递归创建子级聚合：
   - 按 `remainingFields[0]` 对子节点分组
   - 分组大小 > 1 → 创建子级聚合节点（存储 `remainingFields[1:]`）
   - 分组大小 = 1 → 直接作为叶子节点
   - 子级聚合节点注册到全局映射
3. 子级聚合节点在父级圆圈内黄金角螺旋排列
4. 调用 `resizeAncestorCircles()` 递归调整父级圆圈大小

### 3.3 收起时

用户点击聚合节点收起:

1. 递归收起所有子级聚合节点（清理渲染 + 映射）
2. 移除子级聚合节点自身的渲染对象（nodeRenderData + graphData.nodes）
3. 清理子级聚合的全局映射（aggNodeInfoMap 等）
4. 调用 `resizeAncestorCircles()` 通知父级缩小

---

## 四、动态圆圈大小

### 4.1 展开时初次计算

```typescript
const expandedR = Math.min(200, Math.max(35, Math.sqrt(childCount) * 14.14))
```

基于子节点数量，使用 sqrt 增长，限定在 [35, 200] 范围。

### 4.2 子级展开/收起后重算

`resizeAncestorCircles(childId)`：

1. 沿 `aggToCoreMap` 父链向上遍历
2. 对每个祖先，遍历所有子节点
3. 计算每个子节点所需距离 = `子节点圆心距离 + 子节点自身半径`
4. 取最大值作为新半径 = `max(所有子节点所需距离 + 12px padding, 35)`
5. 若新半径 ≠ 旧半径（相差 > 2px），更新背景圆圈的绘制和 hitArea

### 4.3 碰撞约束

模拟 tick 中，子节点被约束在父圆圈内：

```typescript
const boundR = expandedR * 0.85
const childRadius = child.isAggregation
  ? (child.aggExpandedRadius ?? child.aggCollapsedRadius ?? nodeRadius(child))
  : nodeRadius(child)
const maxDist = Math.max(0, boundR - childRadius)
```

考虑子节点自身半径，确保子节点的**整个视觉边界**不超出父圆圈。

---

## 五、全局映射

| 映射 | key | value | 说明 |
|------|-----|-------|------|
| `aggNodeInfoMap` | 聚合节点 ID | `AggregationNodeInfo` | 聚合节点完整信息 |
| `aggNodeToChildNodes` | 聚合节点 ID | `NodeData[]` | 直接子节点列表 |
| `aggNodeToChildLinks` | 聚合节点 ID | `LinkData[]` | 子节点的边 |
| `aggToCoreMap` | 聚合节点 ID | 核心节点 ID | 父级关联（子级→父聚合） |
| `subAggNodesMap` | 父聚合 ID | 子聚合 ID 数组 | 追踪展开时创建的子级 |
| `expandedAggChildren` | 已展开的聚合 ID | 子节点 ID Set | 用于碰撞检测跳过父子碰撞 |

---

## 六、字段值提取

```typescript
function getFieldValue(nodeDetails, field, granularity): string {
  if (field === "date") {
    // 支持 year/month/quarter 粒度
    // fallback: frontmatter.date → dates.date
  }
  // 普通字段: frontmatter[field]
  // 数组字段: 取第一个值
  // 空值 → "(无)"
}
```

### 数组字段特殊处理（仅一级聚合）

`tags` 等多值字段的每个值独立成为一个分组，同一节点可同时出现在多个分组中（仅限一级聚合，子级聚合不支持多值字段展开）。

---

## 七、ID 命名规则

| 节点类型 | ID 格式 | 示例 |
|----------|---------|------|
| 一级聚合节点 | `agg:{coreId}:{field}:{key}` | `agg:page1:date:2025年` |
| 子级聚合节点 | `agg:sub:{parentId}:{field}:{key}` | `agg:sub:agg:page1:date:2025年:type:A` |

---

## 八、设计决策

### 8.1 子节点边不渲染（有意设计）

聚合节点展开后，子节点之间的边不渲染。聚合区域本身与核心节点的连线足以表达关系，渲染内部边反而增加视觉噪音。

### 8.2 逐级展开 vs 递归展开

多级聚合采用**逐级展开**策略：点击一级聚合节点时，只按 `fields[1]` 创建子级聚合；点击子级聚合节点时，才按 `fields[2]` 继续分组。每次只处理一个字段层级，保证每级聚合都有独立的圆圈区域约束。

---

## 九、已修复问题（2026-05-08）

### 9.1 tick 约束只约束直接子节点

**问题**：嵌套展开时，深层子节点不受祖先聚合区域约束，可超出父级圆圈。

**修复**：tick 约束改为递归收集所有后代节点（DFS），对每个聚合节点约束其**所有后代**而非仅直接子节点。Map 遍历顺序保证外层先约束，内层后约束（内层约束更严格会覆盖外层）。

### 9.2 `createSubAggNodes` 递归创建所有层级

**问题**：原实现递归创建所有层级的子聚合节点，但只有一级聚合在展开时创建圆圈（`aggBg`），深层子聚合没有独立的约束区域。

**修复**：改为非递归，每次只处理一个字段层级。`remainingFields` 记录剩余字段供后续展开使用。

### 9.3 `expandNode` 调用 `createSubAggNodes` 参数错误

**问题**：传入 `aggregation.fields` 全量数组和计算 `fieldIndex`，三级以上递归展开时 fieldIndex 计算错误。

**修复**：改为使用 `aggInfo.remainingFields[0]` 和 `aggInfo.remainingFields.slice(1)` 直接传递，避免复杂的索引计算。

### 9.4 `collapseNode` 收起清理不彻底

**问题**：
- 使用 `aggNodeToChildNodes`（原始子节点）而非实际可见节点来确定要移除的节点
- 子级聚合节点自身的 `aggBg` 背景圆圈未被销毁
- `expandedAggChildren` 映射在子级聚合清理时未被同步删除

**修复**：
- 使用 `expandedAggChildren` 获取实际可见的所有子节点
- 分步清理：先递归收起已展开的子级聚合 → 清理所有子级聚合的渲染和映射 → 移除叶子节点
- 子级聚合清理时同步删除 `aggBg`、`expandedAggChildren`、`expandedNodeIds`

### 9.5 展开后标签 `isAggNode` 检查错误

**问题**：使用父节点的 `isAggNode` 判断子节点是否显示标签，导致子级聚合节点的标签也被错误显示。

**修复**：改为使用 `edgeNode.isAggregation` 检查子节点自身的类型。

---

## 十、未实现功能

- **文件夹聚合**：`aggregation.folder` 在图谱中的支持（仅配置层完成，渲染层未实现）
- **多值字段分布式聚合**：子级聚合不支持数组字段多值展开
- **跨核心聚合**：节点与多个核心相连时不参与聚合
- **三级以上深度布局优化**：深层展开后性能可能下降，目前无特殊优化

