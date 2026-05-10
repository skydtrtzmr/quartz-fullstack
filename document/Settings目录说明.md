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
