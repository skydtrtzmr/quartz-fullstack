# Settings 目录说明

本目录存放各业务域的配置文件，每个子目录代表一个独立的业务域（domain）。

## 目录结构

```
server/examples/settings/
├── README.md              # 本说明文件
├── quartz.config.json     # Quartz 运行时配置（示例）
├── quartz.layout.json     # 布局配置（示例）
```

## 配置文件说明

### 1. quartz.config.json

**作用**：供 Quartz Client 读取的运行时配置，对应 `quartz.config.ts` 的 configuration 字段。

**管理方式**：通过 Server API 管理
- `PUT /api/domain/{domain}` - 更新配置（传入 config 字段）
- `GET /api/domain/{domain}` - 获取配置

**注意**：请勿手动修改，会被 API 调用覆盖。

### 2. quartz.layout.json

**作用**：覆盖 Quartz 布局行为（排序、聚合等）。

**支持字段**：

| 字段 | 说明 |
|------|------|
| `explorer.sort` | 文件浏览器排序配置 |
| `folderPage.sort` | 文件夹页面排序配置 |
| `backlinks.hideWhenEmpty` | 无反向链接时是否隐藏 |
| `backlinks.sort` | 反向链接排序配置 |
| **聚合配置（backlinks / graph 共用同一结构）** | |
| `{component}.aggregation[]` | 聚合规则列表，按数组顺序执行 |
| `{component}.aggregation[].type` | 聚合维度类型：`folder` \| `field` \| `date` |
| `{component}.aggregation[].field` | 字段名（`field`/`date` 用，`folder` 可省略） |
| `{component}.aggregation[].depth` | 文件夹截取深度（仅 `folder` 有效） |
| `{component}.aggregation[].granularity` | 日期粒度：`year` \| `month` \| `quarter`（仅 `date` 有效） |
| **图谱专属字段** | | |
| `graph.coreNodeFilter` | `CoreNodeFilterRule[]` | **全局图谱**核心节点筛选规则（OR 关系）。<br/>**核心节点判定逻辑**：<br/>① 若配置了 `coreNodeFilter`，则按规则匹配（OR 关系，匹配任一规则即为核心节点）；<br/>② 若未配置 `coreNodeFilter`，则回退为连接数阈值：**连接数 > 2** 的节点为核心节点。<br/>**只有核心节点才会被 `regionRules` 归入大区**。例如 tasks 文件夹下的节点通常只连 1 个 person + 1 个 project（连接数 = 2），不满足 > 2，因此不会成为核心节点，也不会产生 `region:tasks` |
| `graph.coreNodeLimit` | number | **全局图谱**核心节点数量硬上限（默认 `100`） |
| `graph.regionRules` | `AggregationRule[]` | **全局图谱**大区聚合规则。配置后首屏先显示大区节点。注意：当前实现**只取列表中第一条规则**，其余规则会被忽略。**大区只对核心节点分组**，非核心节点所在文件夹不会产生对应大区 |
| `graph.expandCoresOnRegionOpen` | `boolean` | 大区展开后是否同时展开内部核心节点。`true`（默认）时核心节点的边缘节点一并展开；`false` 时核心节点保持收起，需逐个点击展开 |
| `graph.aggregation` | `AggregationRule[]` | 叶节点聚合规则，对核心节点的单归属边缘节点分组 |
| `graph.colorBy` | string | 普通节点按指定 frontmatter 字段分配分类颜色，例如 `type`。当前节点、标签与未配置该字段的节点仍使用默认颜色。 |

`backlinks.aggregation` 和 `graph.aggregation` 使用**完全相同的结构**（`AggregationConfig`），均为 `AggregationRule[]` 规则列表。数组顺序即执行顺序，每条规则独立配置，按顺序依次对未聚合的叶子节点进行分组。

### 常见注意事项

#### 1. 聚合 vs 大区（region）：核心节点与边缘节点的区别

图谱中有两类节点：

| 概念 | 定义 | 作用 |
|:---|:---|:---|
| **核心节点** | 由 `coreNodeFilter` 匹配（或连接数 >2 的节点） | 被 `regionRules` 归入大区 |
| **边缘节点** | 非核心节点，连接到核心节点 | 被 `aggregation` 规则聚合 |

**关键限制**：**一个节点不能同时是核心节点和边缘节点**。聚合规则只对边缘节点生效，大区规则只对核心节点生效。

**典型误配置**：把某个文件夹同时放入 `coreNodeFilter.values` 和期望它被 `aggregation` 聚合。例如：

```json
// ❌ 错误：tasks 既是核心节点又想被聚合
{
  "graph": {
    "coreNodeFilter": [{"type": "folder", "depth": 1, "values": ["person", "project", "tasks"]}],
    "regionRules": [{"type": "folder", "depth": 1}],
    "aggregation": [{"type": "field", "field": "责任部门"}]
  }
}
```

这样配置后 tasks 成为核心节点，不再是边缘节点，聚合规则不会对其生效。展开 `region:tasks` 后看到的将是散点 task 节点而非聚合分组。

**正确做法**：确定每个文件夹的角色。如果希望 tasks 被聚合，就不要把它放入 `coreNodeFilter`，让它保持为边缘节点（连接数 ≤2 时自动成为边缘节点）。

#### 2. `coreNodeFilter` 与连接数阈值的关系

- 配置了 `coreNodeFilter` → 严格按规则匹配，连接数阈值**不生效**
- 未配置 `coreNodeFilter` → 回退为连接数阈值：**连接数 > 2** 为核心节点

这意味着当 `coreNodeFilter` 只配置了部分文件夹（如 `["project"]`）时，其他文件夹（如 `person`）中连接数 > 2 的节点仍然可能通过阈值成为核心节点。这是**正常行为**，因为阈值逻辑始终作为兜底存在（仅在 `coreNodeFilter` 为空时生效）。

#### 3. 修改配置文件后必须全量构建

增量构建**会重新生成 `graphGlobal.json`**（emitter 始终全量执行），但修改 `quartz.layout.json` 不会触发已有 HTML 页面的重建。这会导致各页面中内嵌的图谱参数（如 `data-precompute-depth`）保持旧值，与新的 `graphGlobal.json` 不一致。

因此修改配置文件后，**必须带 `--reset` 参数触发全量构建**。

API 方式：`POST /api/domain/{domain}/build?user=admin&pwd=password123&reset=true`

#### 4. 聚合规则的执行逻辑

聚合规则按数组顺序**多级嵌套**执行：
1. 对每个核心节点的单归属边缘节点，按第 1 条规则分组 → 生成第 1 级聚合节点
2. 对第 1 级聚合节点的子节点，按第 2 条规则分组 → 生成第 2 级聚合节点
3. 依次类推，直到规则用完或所有剩余规则都无效

**规则无效的情况**：
- `folder` 规则：分组数 ≤1（只有一组，无需聚合）
- `field` / `date` 规则：所有子节点都没有该字段的有效值

当所有剩余规则都无效时，直接展示原始叶子节点。此时如果该聚合节点只有一个子节点，展开后子节点会直接显示（相当于"穿透"了该级聚合）。

### 为什么聚合用列表，排序不用列表？

聚合和排序的设计目标不同，因此配置方式也不同：

| | 聚合 | 排序 |
|:---|:---|:---|
| **作用** | 分组（树形结构） | 排列（线性顺序） |
| **执行方式** | 多级嵌套，逐级过滤 | 单一标准，一次决定 |
| **多规则结果** | 有意义的层级结构 | 会导致语义混乱 |

聚合天然可以多级（先按客户分，再按类型分），所以用规则列表。排序只需要一个标准，多键排序会让配置和实现都变得复杂且难以预期。如需局部调整排序，可在对应 `index.md` 或文件的 frontmatter 中设置排序相关属性（如 `order`、`date` 等）。

### 排序配置

| 字段 | 说明 |
|------|------|
| `{component}.sort.type` | 排序方式：`natural` \| `lexical` \| `date` \| `numeric` |
| `{component}.sort.order` | 排序方向：`asc` \| `desc` |
| `{component}.sort.field` | 排序字段名（frontmatter 属性名） |

**排序字段来源**：`field` 对应 Markdown 文件 frontmatter 中的属性名。例如 `"field": "priority"` 表示按 `priority` 字段排序；`"field": "date"` 表示按 `date` 字段排序。该字段在页面渲染时**不会显示**，仅用于排序计算。

**排序值相同时的处理（Tie-Breaker）**：当两个文件的主排序字段值相同时，系统会**隐式使用 `title` 的自然排序（natural asc）作为二次排序**。`title` 通常与文件名一致，因此可理解为"按文件名的自然升序"作为兜底规则。

**不同文件夹使用不同排序逻辑**：`quartz.layout.json` 中的排序配置是全局的，但不同文件夹可以通过在各自文件的 frontmatter 中设置**同一排序字段的不同值**来实现差异化排序效果。例如全局配置 `"field": "priority"`，项目文件夹下的文件设置 `priority: 1, 2, 3...`，任务文件夹下的文件也设置各自的 `priority` 值，各自文件夹内即按该字段独立排序。

## 创建新业务域

### 方式一：通过 API（推荐）

```bash
POST /api/domain/{domain}
{
  "domain_name": "myproject",
  "display_name": "我的项目"
}
```

### 方式二：手动复制

1. 复制本目录中的示例文件到 `settings/{domain}/`
2. 修改 `quartz.config.json` 和 `quartz.layout.json`
3. 调用 `POST /api/domain/{domain}/build` 触发构建
