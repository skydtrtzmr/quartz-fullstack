# U3、Go Server JSON 与 YAML 配置映射表

核对日期：2026-10-21。依据当前工作区代码及 `quartz5/quartz.config.yaml`。本文记录已讨论的业务配置，不把主题、字体、插件执行顺序、页脚链接、搜索优先级等固定技术参数扩大为 U3 配置。

## 使用约定

- U3 只与 Go Server 交换 JSON，不负责定位、解析、修改 YAML。U3 字段编码仅为给 U3 开发人员看的建表建议，不进入我方代码、不与 JSON 绑定；按不区分大小写、无下划线和连字符的规则书写。JSON 保留既有命名（含下划线），由双方接口约定。
- 域级基础参数、最小成组数、目录树四项、图谱六项已接入 Go 的 POST/PUT/GET。四视图单独配置接口也已实现；域说明仍是 U3 自有内容字段。
- `configuration` 是单个业务域的全局存储位置；folder 规则仍由目录配置入口维护，不在 U3 业务域主表重复维护字段链。
- **代码默认值**是参数省略时的缺省值；**模板值**是新域继承当前模板得到的值。已有域保留自身配置，不能用模板值覆盖回显结果。
- Go 的业务配置只读写 YAML 的 `configuration`。图谱业务参数现位于 `configuration.graph`，Quartz5 加载器负责注入插件；Go 不再定位具体插件。
- `{folder}` 是相对于内容根的目录路径，例如 `project/2026`，不是磁盘路径，也不包含业务域 ID。

## 1. 业务域基础信息

接口：`POST /api/domain/{domain}` 创建；`PUT /api/domain/{domain}` 更新；`GET /api/domain/{domain}` 查询。

| U3 建议字段编码 | U3 显示名称 | YAML 位置 | JSON 字段或来源 | 类型 | 配置说明 | 示例值 | 可选项 / 校验 | 默认值 | 接口状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| domainid | 域 ID | 无；用于 input/settings/output/cache 下同名目录 | URL `{domain}`；查询响应 `domain_name` | 字符串 | 业务域唯一标识，建议创建后不改 | `test1` | 必填、唯一，最长 64；不能含路径分隔符或非法目录字符，不能以点开头或有首尾空白 | 无，必填 | 已实现；不是请求体 `domain_name` |
| domainname | 域名称 | `configuration.pageTitle` | `page_title` | 字符串 | 站点标题；与域 ID 区分 | `项目管理知识库` | U3 建议必填；现有 API 未强制非空 | 创建时省略则使用域 ID；模板标题为“源悦知识库” | 已实现 |
| domaindescription | 域说明 | 无 | 当前无对应配置 JSON 字段 | 编辑器正文 | 保存在 U3；若要显示为首页正文，需要另行实现内容同步 | `项目管理相关知识与资料` | 可为空 | 空 | U3 自有；Go 配置接口未实现 |
| accessurl | 访问地址 | `configuration.baseUrl` | 查询响应 `base_url`，只读 | 字符串 | Go 根据服务地址和域 ID 生成；不是 U3 可编辑配置 | `localhost/test1` | 不接受客户端覆盖 | 服务主机缺省 `localhost`，再拼域 ID | 已实现，只读 |

查询还会返回 `display_name`，当前由页面标题等元信息得到，不应在 U3 再建一个独立可编辑名称。

## 2. 域级聚合与目录树参数

域 POST/PUT 可保存下表参数，GET 返回对应值。省略字段时更新保持原值，新建则继承模板。

| U3 建议字段编码 | U3 显示名称 | YAML 位置 | JSON 字段 | 类型 | 配置说明 | 示例值 | 可选项 / 校验 | 代码默认值 | 当前模板值 | 接口状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aggregationmingroupsize | 最小成组数量 | `configuration.aggregation.minGroupSize` | `aggregation.min_group_size` | 整数 | 触发当前层分组的成员数阈值；不是删除小类别或过滤文件的条件 | `2` | ≥1；1 可让单成员取值参与成组 | `2` | `2` | 已实现 |
| aggregationfolderdepth | 聚合目录上下文层数 | `configuration.aggregation.folderDepth` | `aggregation.folder_depth` | 整数 | 聚合规则采用的目录上下文层数；不是聚合字段链长度或目录树分类层数 | `1` | ≥1 | `1` | `1` | 已实现；是否显示在 U3 可另定，通常保持 1 |
| explorerhidefiles | 目录树隐藏文件 | `configuration.explorer.hideFiles` | `explorer.hide_files` | 布尔 | 隐藏左侧树内文件项，保留文件夹和已启用的动态分类；不隐藏页面列表、搜索或图谱内文件 | `true` | `true` / `false`；无分类规则时只剩普通文件夹 | `false` | `false` | 已实现 |
| explorerdimensionfolders | 目录树显示动态分类 | `configuration.explorer.dimensionFolders` | `explorer.dimension_folders` | 布尔 | 在目录下按 folder 聚合规则显示分类；这里不重新选择分类字段 | `true` | `true` / `false`；依赖有效聚合规则与维度产物 | `false` | `true` | 已实现 |
| explorerdimensionmaxlevels | 目录树分类最大层数 | `configuration.explorer.dimensionMaxLevels` | `explorer.dimension_max_levels` | 整数 | 最多应用几项分类字段；可使用字段不足时不会凭空增加层级 | `3` | ≥1 | `2` | `3` | 已实现 |
| explorerdimensionmaxvalues | 每层分类最多显示取值数 | `configuration.explorer.dimensionMaxValues` | `explorer.dimension_max_values` | 整数 | 例如负责人有 200 人，设 20 则最多显示 20 个负责人分类；不是每个分类里的文件数 | `20` | ≥1；目前没有取值“加载更多”；隐藏文件模式下也不生成超限分类入口 | `20` | `20` | 已实现 |

`hideFiles: true` 时分类取值通常作为维度页跳转入口。`hideFiles: false` 时，超出分类取值上限而未参与分类的文件仍留在父层。

## 3. 域级图谱基本参数（全局 YAML 与 JSON 均已实现）

图谱配置统一使用四视图独立规则，不设配置版本或旧版兼容分支。业务参数的优先级为：内置视图默认值 → configuration.graph.defaults → configuration.graph 下对应视图（local/folder/dimension/global）的覆盖。图谱渲染、构建和业务参数全部集中到 configuration.graph，插件条目不再保存 options。Go 接口仅修改开放且明确提交的字段，其他全局参数保持原值，不因集中存放而增加 U3 字段。三个模板和 17 个业务域已迁移，并逐视图核对实际参数不变。

下表 JSON 已实现，用于公共默认及全局图谱业务设置。U3 不需要知道 YAML 路径或插件名称。

| U3 建议字段编码 | U3 显示名称 | 当前 YAML 位置 | JSON 字段 | 类型 | 配置说明 | 示例值 | 可选项 / 校验 | 代码默认值 | 当前模板值 | 接口状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| graphglobalfolders | 全局图谱主体目录 | `configuration.graph.global.folders` | `graph.global.folders` | 字符串数组 | 全局主体目录白名单；不代表左侧目录树隐藏规则 | `["project", "person"]` | 目录多选、去重、不要求顺序；`[]` 表示不加目录白名单限制，不是关闭图谱 | `[]` | `[]` | 已实现 |
| graphinitialnodelimit | 图谱首屏节点数量 | `configuration.graph.defaults.maxVisibleNodes` | `graph.defaults.initial_node_limit` | 整数 | 四图谱公共首屏预算，包含内容、聚合、大区节点；后续主动加载可超过它；视图显式覆盖时使用视图值 | `500` | ≥1 | `500` | `500` | 已实现 |
| graphexpandbatchsize | 聚合节点每批展开数量 | `configuration.graph.defaults.expandBatchSize` | `graph.defaults.expand_batch_size` | 整数 | 聚合节点首次展开及继续加载的子节点批次；视图可覆盖 | `20` | ≥1 | `20` | `20` | 已实现 |
| graphloadbatchsize | 普通节点每批加载数量 | `configuration.graph.defaults.loadBatchSize` | `graph.defaults.load_batch_size` | 整数 | 非聚合加载队列的批次；与聚合成员批次是两个参数；视图可覆盖 | `100` | ≥1 | `100` | `100` | 已实现 |
| graphcoreminlinks | 主体节点最少真实关联数 | `configuration.graph.defaults.coreMinLinks` | `graph.defaults.core_min_links` | 整数 | 主体筛选的真实文件关联数门槛，主要供全局、文件夹、维度图谱使用；低于门槛的文件仍可能作为合格主体的直接邻居出现，不过滤列表 | `0` | ≥0；0 允许孤立内容节点参与；局部图谱仍以当前文件为中心，不把此项理解为局部中心筛选 | `0` | `0` | 已实现 |
| graphcoreaggregationmaxlevels | 全局主体聚合层数 | `configuration.graph.global.coreAggregationMaxLevels` | `graph.global.core_aggregation_max_levels` | 整数 | 全局主体聚合最多使用 folder 字段链的前几项，不计目录层；字段内容及顺序仍在 folder 级维护 | `2` | ≥1 | `2` | `2` | 已实现 |

### 3.1 四视图独立配置（POST/PUT/GET 均已实现）

以下为当前已实现的 JSON 合同。四类视图均可独立读写；YAML 缺少的字段才继承公共默认，JSON 请求省略字段则保持原配置不动。0 是 core_min_links 的有效值，不表示继承。

| YAML 视图前缀 | JSON 视图前缀 | U3 显示分组 |
| --- | --- | --- |
| `configuration.graph.local` | `graph.local` | 局部图谱 |
| `configuration.graph.folder` | `graph.folder` | 文件夹图谱 |
| `configuration.graph.dimension` | `graph.dimension` | 维度值图谱 |
| `configuration.graph.global` | `graph.global` | 全局图谱 |

| YAML 字段后缀 | JSON 字段后缀 | U3 显示名称 | 示例值 | 可选项 / 默认值 |
| --- | --- | --- | --- | --- |
| `.maxVisibleNodes` | `.initial_node_limit` | 当前视图首屏节点数量 | `300` | 正整数；省略则继承公共默认，最终内置默认 500 |
| `.expandBatchSize` | `.expand_batch_size` | 当前视图聚合展开批次 | `10` | 正整数；省略则继承公共默认，最终内置默认 20 |
| `.loadBatchSize` | `.load_batch_size` | 当前视图普通加载批次 | `50` | 正整数；省略则继承公共默认，最终内置默认 100 |
| `.coreMinLinks` | `.core_min_links` | 当前视图主体最少关联数 | `2` | 非负整数；省略则继承公共默认，最终内置默认 0；局部中心语义不因此改变 |

例如 `configuration.graph.folder.maxVisibleNodes` 对应 JSON `graph.folder.initial_node_limit`。四类视图均支持查询和修改；省略字段保持原值，查询缺省项按 defaults、内置值顺序补齐。

### 3.2 不提供给 U3 的旧限制

`configuration.graph.global.coreNodeLimit` 仍有模板值 50、内置默认 100，但有目录分区规则时旧数量截断逻辑不会执行。**不建立对应 U3 字段，不将它命名为图谱最大节点数。** 当前可用的数量控制是首屏预算与两类加载批次。

## 4. Folder 级配置（已实现，独立目录入口）

接口：`GET / PUT / DELETE /api/domain/{domain}/_folder/{folder}`。下列三类规则不放入业务域主表。

| U3 建议字段编码 | U3 显示名称 | YAML 位置 | JSON 字段 | 类型 | 配置说明 | 示例值 | 可选项 / 校验 | 默认值 / 继承 | 接口状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| folderaggregationfields | 聚合字段 | `configuration.aggregation.branches.folders.{folder}` | `aggregation.fields` | 有序字符串数组 | 顺序即分组顺序；字段来自该业务数据的 frontmatter | `["阶段", "type", "status"]` | 非空字段名；`[]` 清除本目录覆盖，不表示禁止聚合 | 无本目录覆盖 → 最近已配置祖先 → aggregation 默认链；模板默认链为 `[]` | 已实现 |
| folderpropertyfields | 正文属性显示字段 | `configuration.properties.branches.folders.{folder}` | `properties.fields` | 有序字符串数组 | 顺序即属性面板行序；不影响链外字段作为聚合维度 | `["负责人", "status"]` | 非空字段名；`[]` 清除覆盖；includeAll 与字段链互斥由 Quartz5 构建时校验，Go 不读取插件选项 | 无本目录覆盖 → 最近已配置祖先 → properties 默认链；模板默认链为 `[]` | 已实现 |
| foldersortfield | 排序字段 | `configuration.listingSort.folders.{folder}` 或其 `.field` | `sort.field` | 字符串 | 每个目录一个排序字段；升序可用 YAML 字符串简写 | `priority` | 非空字段名，`title` 为常用值；不是写死的枚举 | 无本目录覆盖 → 最近已配置祖先 → listingSort 默认；模板默认 `title` | 已实现 |
| foldersortorder | 排序方向 | `configuration.listingSort.folders.{folder}.order`；字符串简写隐含 asc | `sort.order` | 枚举 | 与排序字段一起组成一条排序规则 | `desc` | `asc` 升序 / `desc` 降序 | 新提交 sort 对象省略 order 时用 `asc`，不是继承旧方向 | 已实现 |

补充规则：

- PUT 未出现的整个区块不修改。`aggregation`、`properties` 区块一旦提交必须包含 fields；不要传 null 代替 fields 数组。
- `sort: null` 清除本目录排序覆盖；`sort: {"field": "title"}` 明确设置 title 升序。
- DELETE 清除该目录聚合、属性、排序三类覆盖，恢复继承。
- GET 的 `configured / fields` 表示本目录配置；`inherit_from / inherit_fields` 表示删除本目录覆盖后的回退来源，不是可写字段。sort 另有 effective / effective_order / from 表示当前生效规则。
- 属性链只认 `configuration.properties`；目录树策略只认 `configuration.explorer`。现有域已完成迁移，不读取旧插件位置，也不提供自动迁移。
- 字段候选值应来自 U3 的业务字段元数据或受控目录选择器，不应让用户填写磁盘路径。

## 5. 请求示例

### 5.1 域更新的最小示例

`PUT /api/domain/test1`

```json
{
  "page_title": "项目管理知识库",
  "aggregation": { "folder_depth": 1 }
}
```

现有域 PUT 还接受 `aggregation.default` 和 `aggregation.folders`，但这是既有接口能力，不新增为 U3 业务域默认字段链配置入口。目录覆盖统一走 folder 接口。

### 5.2 现在已支持的目录更新

`PUT /api/domain/test1/_folder/project`

```json
{
  "aggregation": { "fields": ["阶段", "type"] },
  "properties": { "fields": ["负责人", "status"] },
  "sort": { "field": "priority", "order": "desc" }
}
```

### 5.3 已实现的完整域业务配置请求

`PUT /api/domain/test1` 更新，`POST /api/domain/test1` 新建；均支持以下请求体，GET 返回相同配置分组供 U3 回显。

```json
{
  "page_title": "项目管理知识库",
  "aggregation": {
    "folder_depth": 1,
    "min_group_size": 2
  },
  "explorer": {
    "hide_files": false,
    "dimension_folders": true,
    "dimension_max_levels": 3,
    "dimension_max_values": 20
  },
  "graph": {
    "defaults": {
      "initial_node_limit": 500,
      "expand_batch_size": 20,
      "load_batch_size": 100,
      "core_min_links": 0
    },
    "global": {
      "folders": [
        "project",
        "person"
      ],
      "core_aggregation_max_levels": 2
    }
  }
}
```

已实现接口语义：省略字段保持原值；显式 false 必须写入；列表 `[]` 表示清空列表；0 只对允许非负整数的 core_min_links 有效。explorer/graph 区块、其中已知字段、aggregation.min_group_size 不接受 null，返回 400。四视图区块及其中字段不接受 null；本批不增加清除覆盖语义。需要回到继承时可在 YAML 删除对应键，接口查询会回显继承值。

## 6. 后端交接与生效

1. Go 已校验并回显 explorer 与 graph 参数；aggregation 视图新增 min_group_size。不再返回 graph.view_overrides；改为在 graph.local/folder/dimension/global 直接返回各类当前生效的业务值；公共默认不能覆盖视图显式值。
2. 新域 POST 继承模板后应用同一套域业务配置白名单，写盘前校验；非法配置不创建域目录。
3. 保存响应要检查 warnings；未知字段目前可能 HTTP 200 但被忽略，不能把它当成保存成功。
4. YAML 同步与站点构建是两个步骤。修改后需要全量构建 reset，现有静态站点不会自动更新。本文只记录配置，不触发构建、发布或修改服务级认证。
5. 同步状态、同步时间、错误信息属于 U3 管理字段，没有 YAML 映射；主表结构仍可使用简单字段和一个目录多选，不因数组值而要求明细表或排序号。

## 7. 核对源码

- Go JSON 请求解析：`server/config_request.go` 的 decodeDomainPatch / decodeFolderPatch；明确字段类型与 YAML 映射：`server/domain_business_config.go`。
- Go YAML 读写与默认：`server/quartz_config.go` 中 AggregationView、ListingSort、PropertiesChain、SetPropertiesFolder。
- 目录树全局注入与校验：`quartz5/quartz/plugins/loader/shared-explorer.ts`、`config-loader.ts`。
- 目录树缺省值及显示逻辑：`plugins-local/explorer-pro/src/components/Explorer.tsx`、`components/scripts/explorer-pro.inline.ts`。
- 聚合默认与目录继承：`plugins-local/aggregation-pro/src/compiler.ts`。
- 全局图谱参数注入：`quartz5/quartz/plugins/loader/shared-graph.ts`。四图谱配置解析与默认：`plugins-local/graph-pro/src/options.ts` 中 resolveGraphViewConfig。
- 首屏与批次校验：`plugins-local/graph-pro/src/components/scripts/expansionPages.ts`。
- 模板：`quartz5/quartz.config.yaml`。图谱正在继续调整时，应再次核对当前源码，不依据旧说明中的插件参数路径实施接口。


2026-10-27 接口路径同步：公共字段在 graph.defaults 下，各类字段在 graph.local/folder/dimension/global 下；global.folders 为全局目录白名单。旧平铺 JSON 不提供别名，按未知字段提示。三份模板均实际声明四类业务参数；接口返回完整的各类生效业务值，修改某一类不会改其他类。Bruno 的“图谱配置”目录提供读取和修改请求。
