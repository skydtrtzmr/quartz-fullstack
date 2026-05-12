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
| `graph.coreNodeFilter` | `CoreNodeFilterRule[]` | **全局图谱**核心节点筛选规则（OR 关系） |
| `graph.coreNodeLimit` | number | **全局图谱**核心节点数量硬上限（默认 `100`） |
| `graph.regionRules` | `AggregationRule[]` | **全局图谱**大区聚合规则。配置后首屏先显示大区节点。注意：当前实现**只取列表中第一条规则**，其余规则会被忽略 |
| `graph.expandCoresOnRegionOpen` | `boolean` | 大区展开后是否同时展开内部核心节点。`true`（默认）时核心节点的边缘节点一并展开；`false` 时核心节点保持收起，需逐个点击展开 |
| `graph.aggregation` | `AggregationRule[]` | 叶节点聚合规则，对核心节点的单归属边缘节点分组 |

`backlinks.aggregation` 和 `graph.aggregation` 使用**完全相同的结构**（`AggregationConfig`），均为 `AggregationRule[]` 规则列表。数组顺序即执行顺序，每条规则独立配置，按顺序依次对未聚合的叶子节点进行分组。

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
