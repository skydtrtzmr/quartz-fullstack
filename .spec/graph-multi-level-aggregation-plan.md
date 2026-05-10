# 多级聚合图谱实现计划

## 一、目标

在现有单级聚合基础上，实现**最多 2 级**的多级聚合，支持按配置 `fields` 数组中的多个字段逐级展开。

## 二、核心约束

1. **最多 2 级**：`fields` 数组长度 ≥ 2 时，最多处理前两个字段；超过 2 个字段的后续字段忽略。
2. **无视数组字段**：多级聚合场景中，任何层级的数组字段（如 `tags`）均跳过，不用于分组。仅限单值字段（如 `date`、`type`）参与多级聚合。
3. **叶子唯一**：每个原始叶子节点在多级聚合树中**只出现一次**。
4. **逐级展开**：点击一级聚合节点 → 出现二级聚合节点；点击二级聚合节点 → 出现叶子。

## 三、配置文件变更

`settings/{domain}/quartz.layout.json`：

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

## 四、代码实施步骤

### Step 1 —— 类型与数据结构（`graph2.inline.ts`）

- [x] `import { FieldAggregation } from "../Graph"`
- [x] `AggregationNodeInfo` 接口增加 `remainingFields: FieldAggregation[]` 和 `currentField: string`

### Step 2 —— 构建时一级聚合

- [x] 创建一级聚合节点时，存储 `remainingFields = fields.slice(1)` 和 `currentField = field`
- [x] `aggNodeInfoMap.set(aggId, { ..., remainingFields, currentField })`

### Step 3 —— `expandNode` 函数重构

聚合节点展开时，不再直接展开叶子，而是先检查 `remainingFields`：

1. **若 `remainingFields.length > 0`**（还有下一级）：
   - 按 `remainingFields[0]` 对 `childNodes` 分组
   - **跳过数组字段**：若字段值为数组，该叶子不参与二级分组，直接作为独立叶子加入
   - 若分组后只有一个 `“(无)”` 分组，直接显示原始叶子
   - 否则，为每个有效分组创建**子聚合节点**（`agg:sub:{parentId}:{field}:{key}`）
   - 子聚合节点注册到：
     - `aggNodeInfoMap`（含 `remainingFields.slice(1)`）
     - `aggNodeToChildNodes`
     - `aggToCoreMap`
   - 子聚合节点和剩余独立叶子作为 `edgeNodesToAdd`
   - 子节点使用黄金角螺旋在父圆圈内均匀分布，设置 `aggTargetOffset`

2. **若 `remainingFields.length === 0`**（最后一级）：
   - 保持现有逻辑，直接展开原始叶子

3. **普通核心节点展开**：
   - 保持现有逻辑不变

### Step 4 —— `collapseNode` 函数重构

1. 先**递归收起**所有已展开的子聚合节点（通过 `expandedAggChildren` 遍历）
2. 基于 `expandedAggChildren` 中的**实际可见子节点**来移除，而非 `aggNodeToChildNodes` 中的原始叶子
3. 清理子聚合节点时，同步从 `aggNodeInfoMap`、`aggNodeToChildNodes`、`aggToCoreMap` 中移除
4. 保持 `graphData.nodes` / `graphData.links` / `nodeRenderData` / `linkRenderData` 的清理逻辑

### Step 5 —— tick 约束兼容

现有 tick 约束逻辑已遍历 `expandedAggChildren`，对每对父子做：
- `aggTargetOffset` 强约束（子节点固定在父圆圈内目标位置）
- `boundR` 兜底边界（子节点不超出父圆圈）

多级场景下：
- 一级 → 二级：tick 把二级固定在一级圆圈内
- 二级 → 叶子：tick 把叶子固定在二级圆圈内

由于 `expandedAggChildren` 分别记录了两层关系，且 Map 遍历顺序保证外层先约束、内层后约束，**无需修改 tick 逻辑**。

### Step 6 —— 视觉层级

| 层级 | 节点类型 | 样式 |
|---|---|---|
| 一级聚合（未展开） | 聚合节点 | 双圆环 + 浅色填充（现有） |
| 一级聚合（已展开） | 背景圆圈 + 二级聚合节点 | 背景圆圈（现有），二级聚合节点用现有聚合节点样式 |
| 二级聚合（未展开） | 子聚合节点 | 双圆环 + 浅色填充（同一级） |
| 二级聚合（已展开） | 背景圆圈 + 叶子 | 背景圆圈（现有），叶子为小实心圆 |

## 五、已处理的设计决策

### 5.1 数组字段策略

多级聚合中，若某叶子在某层级的字段值为数组，**该叶子跳过此层级的分组**，直接作为独立节点加入父级。这样保证：
- 叶子不会被复制到多个分组
- 多值字段的叶子在多级聚合中直接暴露，不聚合

### 5.2 “(无)” 分组中断

若某层级分组后只有一个 `“(无)”` 分组（即所有叶子都没有该字段值），**该分支中断聚合**，直接显示原始叶子。

### 5.3 子聚合节点 ID 唯一性

```
一级：agg:{coreId}:{field}:{key}
二级：agg:sub:{parentAggId}:{field}:{key}
```

## 六、风险与应对

| 风险 | 应对方案 |
|---|---|
| 空间不足（圆圈里套圆圈） | 先实现看效果，若拥挤可增大一级圆圈半径或缩小二级圆圈 |
| 力模拟对无连接节点的排斥 | `aggTargetOffset` 强约束已抵消，每帧固定子节点位置 |
| 子聚合节点拖拽异常 | 被 `aggTargetOffset` 强约束的节点不可拖拽，符合预期 |
| 收起时残留映射 | `collapseNode` 中同步清理 `aggNodeInfoMap` 等映射 |

## 七、验收标准

- [ ] 配置 `fields: [date/year, type]` 后，图谱中出现一级聚合节点（如“2024年”）
- [ ] 点击一级聚合节点，展开为多个二级聚合节点（如“type=A”、“type=B”）
- [ ] 点击二级聚合节点，展开为原始叶子
- [ ] 收起二级聚合节点，叶子收回
- [ ] 收起一级聚合节点，二级聚合节点及叶子全部收回
- [ ] 拖拽一级聚合节点，二级聚合节点跟随移动，叶子跟随二级移动
- [ ] 聚合区域内子节点均匀分布，不出现抖动或圆周聚集
