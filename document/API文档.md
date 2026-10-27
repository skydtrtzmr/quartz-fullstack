> 当前业务配置合同以 [U3－Go Server－YAML 配置映射表](U3-GoServer-YAML配置映射表.md) 为准。Go 的业务参数只写 configuration，不定位插件；POST/PUT/GET 已支持目录树四项和图谱六项。

# Quartz 后端 API 文档

## 概述

本文档描述 Quartz 全栈项目的后端 API 接口，包括业务域管理、构建触发和静态文件服务。

**基础 URL**: `http://127.0.0.1:8766`
**认证方式**: URL 查询参数 或 Cookie

---

## 认证

所有 API 端点（除静态文件外）都需要认证。

### 认证参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `user` | 用户名 | `admin` |
| `pwd` | 密码 | `password123` |

### 认证方式

**方式1：URL 参数**
```
GET /api/domains?user=admin&pwd=password123
```

**方式2：Cookie**
首次使用 URL 参数认证成功后，服务端会设置 `quartz_auth` Cookie，后续请求可自动通过。

---

## 业务域管理 API

业务域（Domain）是 Quartz 的多租户隔离单位，如 `demo-core`、`demo-region-sqlite` 等。

**域名即目录名，四个根目录下严格同名**：

| 根目录 | 路径 | 产生方式 |
|--------|------|---------|
| 输入 | `input/{domain}/` | 建域时创建 |
| 配置 | `settings/{domain}/quartz.config.yaml` | 建域时从 `template_file` 继承 |
| 输出 | `output/{domain}/` | 构建时生成 |
| 缓存 | `cache/{domain}/.quartz-cache.db` | 构建时生成（`cache_dir` 可换根目录） |

**域名规则**：必须是安全的单级目录名 —— 不含路径分隔符 `/` `\`、不含 `:*?"<>|`、不以 `.` 开头、
无首尾空白、长度 ≤ 64、不能是 `.` 或 `..`。服务端在每个接口入口校验，并在拼路径时再次确认
结果**严格落在对应根目录内**（`filepath.Rel` + 单级检查），所以不存在越界读写的可能。

**删除范围**：`DELETE /api/domain/{domain}` 只删这四个根目录下的 `{domain}` 同名目录
（配置目录必删；输入/输出按 body 参数；缓存总是删），不碰任何其它路径。

### 域配置契约（先看这个）

每个域的配置只有一份 `settings/{domain}/quartz.config.yaml`，**这份完整配置文件就是唯一事实来源**。
服务端**不解析成结构体再重写**，而是节点级替换：

- 写接口只碰白名单里的字段，其余内容（注释、锚点别名、插件清单、`layout:` 段）原样保留；
- 白名单外的键**不报错**，会被忽略并在响应的 `warnings` 里逐条列出；
- `baseUrl` 由服务端按 `{base_url}/{domain}` 注入，请求里传什么都不作数。

| 接口 | 白名单字段 |
|------|-----------|
| `POST /api/domain/{domain}` | 与 PUT 相同；继承模板后应用业务配置 |
| `PUT /api/domain/{domain}` | `page_title`、`aggregation.{folder_depth,min_group_size,default,folders}`、`explorer` 四项、`graph` 六项；详见配置映射表 |

---

### 1. 列出所有业务域

```
GET /api/domains
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domains?user=admin&pwd=password123"
```

**响应**（`domains[]` 为 `DomainMeta`）：
```json
{
  "count": 10,
  "domains": [
    {
      "domain_name": "demo-core",
      "display_name": "demo-core",
      "page_title": "demo-core",
      "base_url": "localhost/demo-core",
      "plugin_count": 55,
      "aggregation": {
        "folder_depth": 2,
        "default": ["type", "status", "category"],
        "folders": { "项目": ["阶段", "type", "status", "负责人"], "任务": ["status", "阶段", "级别"] }
      },
      "warnings": []
    }
  ]
}
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| `domain_name` | 域名（`settings/` 下的目录名） |
| `display_name` | 显示名，取自 `configuration.pageTitle`，缺失时回落为域名 |
| `page_title` / `base_url` | `configuration.pageTitle` / `configuration.baseUrl` 原值 |
| `plugin_count` | `plugins` 段条目数，仅供只读统计；不返回插件清单 |
| `aggregation` | `configuration.aggregation` 视图：`folder_depth` / `min_group_size` / `default` / `folders`（域没配则为 `null`） |
| `explorer` / `graph` | 域级业务配置回显，JSON 使用现有下划线字段名；缺省项保留原接口默认值。只返回域级声明，不返回四视图覆盖解释 |
| `warnings` | 结构校验告警（缺 `pageTitle`/`baseUrl`、`plugins` 缺 `source` 等） |

---

### 2. 创建业务域

```
POST /api/domain/{domain}
```

配置**不是从零生成的**：整棵节点树继承 `server/config.json` 里的 `template_file`
（本项目现指向 `quartz5/quartz.config.yaml`，即本地插件源的主配置），只改写
`configuration.pageTitle` 与 `configuration.baseUrl`。因此模板里的注释、锚点别名、插件清单与
`layout:` 段会原样落到新域。

**请求体**（白名单，可选，省略则用域名）：
```json
{
  "page_title": "业务域1"
}
```

**请求示例**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm1?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"page_title": "业务域1"}'
```

**响应**（成功，201）：
```json
{
  "status": "Created",
  "domain": "xm1",
  "domain_info": {
    "domain_name": "xm1",
    "display_name": "业务域1",
    "page_title": "业务域1",
    "base_url": "localhost/xm1",
    "config_format": "yaml",
    "plugin_count": 55,
    "aggregation": { "folder_depth": 1, "default": ["type", "status", "category"], "folders": { "...": ["..."] } },
    "warnings": []
  },
  "warnings": []
}
```

**响应**（域名已存在，409）：
```json
{
  "error": "Domain 'xm1' already exists"
}
```

**说明**：
- 域名从 URL 路径获取；已存在直接 409（不会覆盖）
- 自动创建 `input/xm1/` 与默认 `index.md`（已存在则不覆盖）
- 只生成 `settings/xm1/quartz.config.yaml`
- 未配置 `template_file` 时返回 500 并明确提示
- 非白名单键（例如旧的 `{"config":{"pageTitle":...}}`）会被忽略并在 `warnings` 里列出

---

### 3. 获取业务域信息

```
GET /api/domain/{domain}
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123"
```

**响应**：单个 `DomainMeta`，字段与「1. 列出所有业务域」里的 `domains[]` 元素完全一致
（`domain_name` / `display_name` / `page_title` / `base_url` / `config_format` /
`plugin_count` / `aggregation` / `warnings`）。

**其它情况**：
- 域目录里既没有 `quartz.config.yaml` 也没有 v4 JSON → `404`

---

### 4. 更新业务域配置

```
PUT /api/domain/{domain}
```

**语义**：**只改请求体里出现的键**，没出现的键一律不动。

| 键 | 类型 | 语义 |
|----|------|------|
| `page_title` | string | 写 `configuration.pageTitle` |
| `aggregation.folder_depth` | int (>=1) | 写 `configuration.aggregation.folderDepth` |
| `aggregation.min_group_size` | int (>=1) | 写 `configuration.aggregation.minGroupSize` |
| `explorer` | object | hide_files / dimension_folders / dimension_max_levels / dimension_max_values；只写 configuration.explorer |
| `graph` | object | global_folders / initial_node_limit / expand_batch_size / load_batch_size / core_min_links / core_aggregation_max_levels；只写 configuration.graph |
| `aggregation.default` | string[] | 写 `branches.default`；传 `[]` 表示**删除该键**（= 整域不做字段聚合） |
| `aggregation.folders` | object | 逐目录写 `branches.folders.<目录>`；值为 `[]` 表示**删除该目录的覆盖**（恢复逐层继承） |

目录级只有「配了字段」与「未配置」两态 —— 空数组等价于未配置，不存在「显式中断聚合」。

**请求体示例**：
```json
{
  "page_title": "新标题",
  "aggregation": {
    "folder_depth": 2,
    "default": ["type", "status", "category"],
    "folders": {
      "项目": ["阶段", "type", "status", "负责人"],
      "问答": ["category", "status"],
      "组织": []
    }
  }
}
```

**请求示例**：
```bash
# 只改标题
curl -X PUT "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"page_title": "新标题"}'

# 只改聚合：新增「问答」、删除「组织」的覆盖、目录层级改 2
curl -X PUT "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"aggregation": {"folder_depth": 2, "folders": {"问答": ["category", "status"], "组织": []}}}'
```

**响应**：
```json
{
  "status": "Saved",
  "domain": "xm",
  "domain_info": { "...": "更新后的 DomainMeta" },
  "warnings": ["请求体里的 \"nope\" 不在白名单内，已忽略"]
}
```

**说明**：
- 写入是**节点级**的：只替换目标标量/序列节点，`quartz.config.yaml` 里的注释、锚点别名、键序、插件清单与 `layout:` 段全部保留。
- 首次写入会做一次 YAML 风格归一化（Go emitter 把 flow 集合内侧空格去掉：`{ a: 1 }` → `{a: 1}`），内容零损失且幂等。
- `baseUrl` 始终由服务端按 `{base_url}/{domain}` 注入。
- 域没有 `quartz.config.yaml` → `500` 并提示配置不存在。
- **改完必须带 `reset=true` 全量构建**，否则页面内嵌的图谱参数不会更新。

---

### 5. 删除业务域

```
DELETE /api/domain/{domain}
```

**请求体**（可选）：
```json
{
  "delete_input": true,
  "delete_output": true
}
```

**请求示例**：
```bash
# 只删除配置目录
curl -X DELETE "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123"

# 删除配置 + 输入 + 输出目录
curl -X DELETE "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"delete_input": true, "delete_output": true}'
```

**响应**：
```json
{
  "status": "Deleted",
  "domain": "xm",
  "message": "Domain deleted successfully",
  "deletedInput": true,
  "deletedOutput": false
}
```

---

## 文件夹级配置 API

在域级配置（`PUT /api/domain/{domain}`）之上，按**目录**维护该目录自己的覆盖值。覆盖的是两个同构的「链段」：

| 链段 | 配置位置 | 语义 |
|------|----------|------|
| `aggregation` | `configuration.aggregation.branches.folders` | 该目录的**聚合字段链** |
| `properties` | `configuration.properties.branches.folders` | 该目录**正文属性面板显示**的字段链 |

目录级只有「配了字段」/「未配置」两态：未配置 → 逐层向上继承（最终用该链段的 `default`）。
所以「恢复继承」= 删掉这一行 = 传 `fields: []`。

### 1. 读

```
GET /api/domain/{domain}/_folder/{path...}
```

`{path...}` 是内容根相对的目录路径，**嵌套目录直接拼**（如 `任务/年度` → `.../_folder/任务/年度`）。

响应：

```json
{
  "domain": "demo-core",
  "folder": "任务/年度",
  "aggregation": {
    "configured": false,
    "fields": null,
    "inherit_from": "任务",
    "inherit_fields": ["status", "阶段", "级别"]
  },
  "properties": {
    "configured": true,
    "fields": ["status"],
    "inherit_from": "任务",
    "inherit_fields": ["status", "阶段", "级别", "负责人", "tags"]
  },
  "warnings": []
}
```

- `configured` / `fields`：该目录**自己**配没配、配了什么（未配置为 `false` / `null`）。
- `inherit_from` / `inherit_fields`：**删掉这一行之后会落到哪** —— 最近的已配置祖先，找不到就是 `default`。

### 2. 写

```
PUT /api/domain/{domain}/_folder/{path...}
```

请求体（白名单支持 `aggregation` / `properties` / `sort`）：

```json
{
  "aggregation": { "fields": ["阶段", "type"] },
  "properties": { "fields": ["status", "阶段"] }
}
```

| 情况 | 行为 |
|------|------|
| 区块未出现 | 该区块**不动**（不会误清另一区块） |
| `fields` 非空 | 写/覆盖该目录条目；数组顺序即字段优先级 |
| `fields: []` | 删除该条目（= 恢复继承） |
| 区块内缺 `fields` | 400 |
| 域里没有 note-properties-pro 插件 | 仍可保存全局属性显示规则；是否渲染面板由插件启用状态决定 |
| 该插件 `includeAll: true`（与 properties 链互斥） | Quartz5 构建时校验；Go 不读取插件选项 |

响应 200：与「读」同形（写完后立刻回读）+ `warnings`（未知键、构建校验结果）。

### 3. 删

```
DELETE /api/domain/{domain}/_folder/{path...}
```

删除聚合、全局属性显示链与排序中该目录的覆盖（恢复继承）。属性链只读写 `configuration.properties`，不兼容旧插件位置；JSON 请求格式保持不变。

### curl 示例

```bash
curl -X PUT "http://127.0.0.1:9766/api/domain/demo-core/_folder/任务/年度?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"aggregation": {"fields": ["阶段", "type"]}, "properties": {"fields": ["status"]}}'

# 恢复继承
curl -X DELETE "http://127.0.0.1:9766/api/domain/demo-core/_folder/任务/年度?user=admin&pwd=password123"
```

> 改了配置后**必须带 `reset=true` 全量重建**，页面里内嵌的构建期参数才会更新。
> 面板「本目录聚合配置」的字段顺序可用本接口落盘（`fields` 数组顺序 = 链顺序），替代浏览器 localStorage。

## 构建 API

### 1. 触发指定业务域构建

```
POST /api/domain/{domain}/build
```

**请求示例**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm/build?user=admin&pwd=password123"
```

**响应**：
```json
{
  "status": "Accepted",
  "message": "Build triggered for domain: xm",
  "command": "node build --settings=settings/xm -d input/xm -o output/xm",
  "taskId": "xm-1745067600"
}
```

**构建流程**：
1. 检查业务域目录是否存在
2. 执行构建命令：`node ./quartz/bootstrap-cli.mjs build --sqlite --settings={settingsDir}/{domain} -d {inputDir}/{domain} -o {outputDir}/{domain}`
3. 构建日志保存到 `logs/tasks/{taskId}.log`；taskId 仍为 `{domain}-{Unix秒}`，例如 `xm-1745067600.log`。同秒内先后两次任务的重名边界已知，暂不改造

**带 reset 模式**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm/build?user=admin&pwd=password123&reset=true"
```

---

### 2. 获取构建状态

```
GET /api/domain/{domain}/status
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domain/xm/status?user=admin&pwd=password123"
```

**响应**（运行中）：
```json
{
  "status": "running",
  "domain": "xm",
  "taskId": "xm-1745067600",
  "startTime": "2026-04-19T15:00:00Z"
}
```

**响应**（没有活动任务且没有可查询日志）：
```json
{
  "status": "idle",
  "domain": "xm"
}
```

---

任务状态说明（最新实现）：

| status | 含义 |
| --- | --- |
| queued | 任务正在排队，含 queuePosition、enqueuedAt |
| running | 正在运行，含 enqueuedAt、startTime |
| succeeded | 最新任务日志有完整成功结果，exitCode 为 0 |
| failed | 最新任务日志有完整失败结果，含 error；进程已启动时有 exitCode，启动前失败时省略 |
| unknown | 有日志，但没有完整有效的结果行，不能确认结果；旧格式日志、异常中断或结果写入失败均可能出现 |
| idle | 没有活动任务，也没有可查询日志 |

没有活动任务时，服务扫描该域日志，按修改时间选择最新一份，仅解析末尾 64 KiB 中的固定结果行。最新日志不完整时返回 unknown，不回退到更早的成功任务。完成结果不另外存储，服务重启后仍可从日志查询。

完成响应示例：

```json
{
  "status": "failed",
  "domain": "xm",
  "taskId": "xm-1745067600",
  "enqueuedAt": "2026-10-26T12:00:00+08:00",
  "startTime": "2026-10-26T12:00:02+08:00",
  "endTime": "2026-10-26T12:00:05+08:00",
  "exitCode": 1,
  "error": "exit status 1"
}
```

日志以 `@@QUARTZ_TASK_RESULT@@ ` 开头的最终 JSON 行记录结果，仅此明确记录用于判断完成状态，不搜索命令输出中的“成功/失败”字样。提交时创建日志失败会返回 500，不接受任务；提交后日志 IO 故障可能导致结果未确认。

### 3. 获取构建日志

```
GET /api/domain/{domain}/logs
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domain/xm/logs?user=admin&pwd=password123"
```

**响应**：`text/plain` 格式的日志内容

---

### 4. 获取所有运行中的任务

```
GET /api/tasks
```

获取当前所有正在运行的构建任务列表。

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/tasks?user=admin&pwd=password123"
```

**响应**：
```json
{
  "count": 2,
  "tasks": [
    {
      "domain": "xm",
      "taskId": "xm-1778596140",
      "startTime": "2026-05-12T22:29:00+08:00",
      "reset": false,
      "command": "node ./quartz/bootstrap-cli.mjs build ...",
      "logPath": "logs/tasks/xm-1747060140.log"
    },
    {
      "domain": "xm1",
      "taskId": "xm1-1778596260",
      "startTime": "2026-05-12T22:31:00+08:00",
      "reset": true,
      "command": "...",
      "logPath": "..."
    }
  ]
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | int | 正在运行的任务数量 |
| `tasks[].domain` | string | 业务域名称 |
| `tasks[].taskId` | string | 任务唯一标识（格式：`{domain}-{timestamp}`） |
| `tasks[].startTime` | string | RFC3339 格式的开始时间 |
| `tasks[].reset` | bool | 是否为 reset（全量）构建 |
| `tasks[].command` | string | 执行的完整命令 |
| `tasks[].logPath` | string | 任务日志文件路径 |

---

### 5. Output 目录清理

```
GET  /api/output/cleanup     # 干运行模式：只列出垃圾文件，不删除
POST /api/output/cleanup     # 确认删除（需带 confirm=true 参数）
```

清理 `output/` 目录中的孤立子目录（不在 `settings/` 目录列表中的条目视为垃圾）。

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `confirm` | boolean | 设为 `true` 时执行实际删除，设为其他值或省略时为干运行 |

**请求示例**：
```bash
# 干运行：列出垃圾文件（不删除）
curl "http://127.0.0.1:8766/api/output/cleanup?user=admin&pwd=password123"

# 确认删除
curl -X POST "http://127.0.0.1:8766/api/output/cleanup?user=admin&pwd=password123&confirm=true"
```

**响应**（干运行）：
```json
{
  "status": "dryrun",
  "count": 2,
  "garbage": [
    "output/orphan_dir1",
    "output/orphan_dir2"
  ],
  "message": "Dry run: found 2 garbage items (no deletion performed)"
}
```

**响应**（确认删除）：
```json
{
  "status": "deleted",
  "count": 2,
  "deleted": [
    "output/orphan_dir1",
    "output/orphan_dir2"
  ],
  "message": "Deleted 2 garbage items"
}
```

**响应**（有任务运行中）：
```json
{
  "error": "Task(s) running, cleanup denied"
}
```

**说明**：
- 清理规则：只删除 `output/` 下的孤立子目录
- 孤立目录 = 不在 `settings/` 目录子目录列表中的条目
- 忽略规则（不会被删除）：`.gitkeep` 文件、以 `.` 开头的隐藏文件/目录
- 有任何构建任务运行时，拒绝执行清理操作

---

### 6. 传统构建端点（已删除）

v4 时代的 `POST /api/build`（从 query 取 `domain`）**代码里从未注册过，已随 v4 模型一并删除**。
构建请统一走 `POST /api/domain/{domain}/build`（见上文「构建 API」）。

---

## 静态文件服务

静态文件服务支持多业务域隔离，URL 路径格式为 `/{domain}/{path}`。

### URL 映射规则

| URL 路径 | 实际文件路径 | 说明 |
|----------|-------------|------|
| `/xm/` | `output/xm/index.html` | ✅ 标准格式（带斜杠） |
| `/xm` | → 重定向到 `/xm/` | 自动添加斜杠 |
| `/xm/page` | `output/xm/page.html` | 自动添加 `.html` 后缀 |
| `/xm/page/` | `output/xm/page.html` | 保留斜杠的别名 |
| `/xm/static/...` | `output/xm/static/...` | 静态资源文件 |
| `/xm1/` | `output/xm1/index.html` | 其他业务域 |

> **重要**：访问业务域时必须带斜杠（`/xm/`），否则后端会返回 301 重定向到 `/xm/`。这是为了确保前端相对路径（如 `./static/contentIndex.json`）能正确解析到 `/xm/static/contentIndex.json`。

### 缓存控制

- **HTML/JSON 文件**：`Cache-Control: no-store`（不缓存）
- **静态资源**：`Cache-Control: public, max-age=31536000`（长期缓存）

---

## 配置数据结构

### quartz.config.yaml（v5 域配置，唯一的一份）

**注意**：`configuration.baseUrl` 由服务端按 `{base_url}/{domain}` 注入，API 或手工传入的值都会被忽略/覆盖。

```yaml
configuration:
  pageTitle: 示例业务域          # 作为 display name
  baseUrl: localhost/demo-core   # 服务端注入
  locale: zh-CN
  aggregation:                   # 全站唯一的聚合规则（取代 v4 的 backlinks/graph.aggregation）
    minGroupSize: 1
    folderDepth: 1
    branches:
      default: [type, status, category]
      folders:
        项目: [阶段, type, status, 负责人]
plugins:                         # 插件清单：source / enabled / options / order / layout
  - source: ../plugins-local/graph-pro
    enabled: true
    options:
      globalGraph:
        folders: [项目, 组织]     # 全局图谱首屏大区白名单（取代 v4 的 coreNodeFilter/regionRules）
    order: 55
    layout: { position: right, priority: 10, component: Graph }
layout:                          # 页型级布局调整
  byPageType:
    folder: { exclude: [backlinks], positions: { right: [] } }
```

| 段 | 说明 |
|----|------|
| `configuration` | 站点配置。`pageTitle` / `baseUrl` / `locale` / `theme` / `ignorePatterns` / `aggregation` |
| `configuration.aggregation` | 聚合规则：`minGroupSize`、`folderDepth`、`branches.{default,folders}`；目录级只有「配了字段」与「未配置」两态 |
| `plugins[]` | 每个插件条目：`source` / `enabled` / `options` / `order` / `layout`（多组件插件需用 `layout.component` 指定导出名） |
| `layout` | 页型级布局：`groups`（工具栏分组）与 `byPageType`（按页型 exclude 组件 / 清空栏位） |

> 局部图谱参数写在 `plugins[graph-pro].options.graph` / `.localGraph`，
> 排序写在 `plugins[explorer-pro].options.sort`，聚合写在 `configuration.aggregation`。

### 图谱字段（plugins[graph-pro].options.globalGraph）

下列全局图谱的规则名都写在 `plugins[graph-pro].options.globalGraph` 下。

> **注意**：域配置的变更**不会被增量构建自动识别**。修改后必须带 `reset=true` 触发全量重新构建，否则页面中嵌入的配置不会更新。

```json
{
  "graph": {
    "coreNodeFilter": [
      {
        "type": "folder",
        "depth": 1,
        "values": [
          "组织"
        ]
      },
      {
        "type": "field",
        "field": "type",
        "values": [
          "项目",
          "组织"
        ]
      }
    ],
    "coreNodeLimit": 50,
    "regionRules": [
      {
        "type": "field",
        "field": "客户"
      },
      {
        "type": "folder",
        "depth": 2
      }
    ],
    "aggregation": [
      {
        "type": "folder",
        "depth": 1
      },
      {
        "type": "field",
        "field": "type"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `graph.coreNodeFilter` | `CoreNodeFilterRule[]` | **全局图谱**核心节点筛选规则，满足任一规则即为核心节点（OR 关系）。未配置时回退到连接数阈值 |
| `graph.coreNodeFilter[].type` | string | 规则类型：`folder`（按路径文件夹匹配）\| `field`（按 frontmatter 字段匹配） |
| `graph.coreNodeFilter[].field` | string | 字段名（仅 `field` 类型有效） |
| `graph.coreNodeFilter[].depth` | number | 文件夹截取深度（仅 `folder` 类型有效，默认 `1`） |
| `graph.coreNodeFilter[].values` | string[] | 精确匹配值列表，满足任一值即命中 |
| `graph.coreNodeLimit` | number | **全局图谱**核心节点数量硬上限。超过时按连接数降序截取前 N 个。默认 `100` |
| `graph.regionRules` | `AggregationRule[]` | **全局图谱**大区聚合规则。配置后首屏先显示大区节点，点击展开才显示内部核心节点。不配置则保持现有行为 |
| `graph.expandCoresOnRegionOpen` | `boolean` | 大区展开后是否同时展开内部核心节点。`true`（默认）时核心节点的边缘节点一并展开；`false` 时核心节点保持收起，需逐个点击展开 |
| `graph.aggregation` | `AggregationRule[]` | 叶节点聚合规则，对核心节点的单归属边缘节点按规则分组为聚合节点 |

**coreNodeFilter 匹配示例**：
- `{ "type": "folder", "depth": 1, "values": ["组织"] }`：slug 第一级文件夹为 `"组织"` 的节点标记为核心节点
- `{ "type": "field", "field": "type", "values": ["项目", "组织"] }`：frontmatter.type 为 `"项目"` 或 `"组织"` 的节点标记为核心节点

**regionRules 大区聚合示例**：
- `{ "type": "field", "field": "客户" }`：按 frontmatter.客户 的值把核心节点分组为 "A客户"、"B客户" 等大区
- `{ "type": "folder", "depth": 2 }`：按 slug 路径第2级文件夹分组

> **注意**：`regionRules` 虽然为列表格式，但**当前实现只读取第一条规则**，其余规则会被忽略。如需更换分组维度，直接修改列表中的第一个元素即可。保留列表格式是为将来可能的“大区 → 子区”多级分组预留扩展。

> 大区聚合仅作用于**全局图谱**。首屏只显示大区节点和跨区共享文件，点击大区节点展开后才显示内部核心节点及其叶节点聚合。不配置 `regionRules` 时保持现有行为（直接显示核心节点）。

---

### layout 段（v5 位于 `quartz.config.yaml` 的 `layout:`）

**所有字段均为可选**，不写则用前端默认值。v5 的 `layout:` 只做页型级调整（`groups` / `byPageType`：
按页型 exclude 组件或清空某栏位）；组件自己的排序、聚合、图谱参数都写在对应插件的 `options` 里。
下表是 `plugins[<插件>].options.*` 下的字段（各插件的 options 结构）。

```json
{
  "explorer": {
    "sort": {
      "type": "natural",
      "order": "asc",
      "field": ""
    }
  },
  "folderPage": {
    "sort": {
      "type": "natural",
      "order": "asc",
      "field": ""
    }
  },
  "backlinks": {
    "hideWhenEmpty": false,
    "sort": {
      "type": "date",
      "order": "desc",
      "field": "date"
    },
    "aggregation": [
      {
        "type": "folder",
        "depth": 1
      },
      {
        "type": "date",
        "field": "date",
        "granularity": "year"
      },
      {
        "type": "field",
        "field": "type"
      }
    ]
  },
  "graph": {
    "aggregation": [
      {
        "type": "folder",
        "depth": 1
      },
      {
        "type": "field",
        "field": "type"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `explorer.sort.type` | string | 文件浏览器排序方式：`natural` \| `lexical` \| `date` \| `numeric` |
| `explorer.sort.order` | string | 排序方向：`asc` \| `desc` |
| `explorer.sort.field` | string | 排序字段名（frontmatter 属性名） |
| `folderPage.sort.*` | - | 文件夹页面排序（字段同 explorer.sort） |
| `backlinks.hideWhenEmpty` | bool | 无反向链接时是否隐藏组件 |
| `backlinks.sort.*` | - | 反向链接排序（可选，字段同 explorer.sort） |
| **聚合配置（backlinks / graph 共用同一结构）** | | |
| `{component}.aggregation[]` | `AggregationRule[]` | 聚合规则列表，按数组顺序执行 |
| `{component}.aggregation[].type` | string | 聚合维度类型：`folder` \| `field` \| `date` |
| `{component}.aggregation[].field` | string | 字段名（`field`/`date` 用，`folder` 可省略） |
| `{component}.aggregation[].depth` | int | 文件夹截取深度（仅 `folder` 有效，默认 `1`） |
| `{component}.aggregation[].granularity` | string | 日期粒度：`year` \| `month` \| `quarter`（仅 `date` 有效） |

**排序字段来源**：`sort.field` 对应 Markdown 文件 frontmatter 中的属性名。例如 `"field": "priority"` 表示按 `priority` 字段排序；`"field": "date"` 表示按 `date` 字段排序。该字段在页面渲染时**不会显示**，仅用于排序计算。

**排序值相同时的处理（Tie-Breaker）**：当两个文件的主排序字段值相同时，系统会**隐式使用 `title` 的自然排序（natural asc）作为二次排序**。`title` 通常与文件名一致，因此可理解为"按文件名的自然升序"作为兜底规则。

**不同文件夹使用不同排序逻辑**：`plugins[explorer-pro].options.sort` 里的排序配置是全局的，但不同文件夹可以通过在各自文件的 frontmatter 中设置**同一排序字段的不同值**来实现差异化排序效果。例如全局配置 `"field": "priority"`，项目文件夹下的文件设置 `priority: 1, 2, 3...`，任务文件夹下的文件也设置各自的 `priority` 值，各自文件夹内即按该字段独立排序。

> **注意**：`backlinks.aggregation` 与 `graph.aggregation` 共用完全相同的结构（`AggregationConfig`），均为规则列表。数组顺序即执行顺序，每条规则独立配置，按顺序依次对未聚合的叶子节点进行分组。不再使用 `order` 字段，也不再区分 `folder` 和 `fields` 两个独立配置块。

### DomainMeta（API 响应结构）

```typescript
interface DomainMeta {
  domain_name: string;       // 业务域标识（目录名）
  display_name: string;      // 显示名，取自 configuration.pageTitle，缺失回落为域名
  page_title: string;        // configuration.pageTitle 原值
  base_url: string;          // configuration.baseUrl
  plugin_count: number;      // plugins 段条目数
  aggregation?: {            // configuration.aggregation 视图（域没配则为 null）
    folder_depth: number;
    default: string[];
    folders: Record<string, string[]>;
  };
  warnings: string[];        // 结构校验告警 + v4 迁移提示
}
```

---

## 目录结构

```
quartz-fullstack/
├── input/                    # Markdown 输入目录
│   └── xm/                   # xm 业务域输入
├── output/                   # 构建输出目录
│   └── xm/                   # xm 业务域输出（对应 /xm/ URL）
├── cache/                    # 构建缓存，每域一份：cache/xm/.quartz-cache.db（已 gitignore）
├── settings/                 # 域配置目录
│   └── xm/
│       ├── quartz.config.yaml   # v5 域配置（唯一的一份）
│       └── _v4-backup/          # v4 迁移留档（服务端不读）
├── quartz5/                  # Quartz v5 前端引擎
│   └── quartz/               # 引擎核心（bootstrap-cli.mjs 等）
├── plugins-local/            # 本地插件源码
├── server/                   # 后端服务代码
│   ├── main.go
│   ├── api.go
│   ├── quartz_config.go           # 域配置（YAML）节点级读写
│   ├── domain_config.go      # 业务域管理
│   └── config.json           # 后端服务配置
```

---

## 后端服务配置

`server/config.json`：

```json
{
  "version": "1.0.1",
  "listen_addr": "0.0.0.0:8766",
  "base_url": "localhost",
  "optional_param": "reset",
  "forbidden_page": "401.html",
  "auth": {
    "user_param": "user",
    "pwd_param": "pwd",
    "user": "admin",
    "pwd": "password123",
    "cookie_max_age": 0
  },
  "command": {
    "work_dir": "/path/to/quartz-fullstack/quartz5",
    "interpreter": "node",
    "interpreter_args": "--no-deprecation",
    "script": "./quartz/bootstrap-cli.mjs",
    "args": "build --sqlite",
    "optional_flag": "--reset"
  },
  "input_dir": "/path/to/quartz-fullstack/input",
  "output_dir": "/path/to/quartz-fullstack/output",
  "settings_dir": "/path/to/quartz-fullstack/settings",
  "template_file": "/path/to/quartz-fullstack/quartz5/quartz.config.yaml",
  "cache_dir": "/path/to/quartz-fullstack/cache",
  "compression": {
    "enabled": true,
    "level": 6,
    "min_size_kb": 1,
    "types": [
      "text/html",
      "text/css",
      "text/javascript",
      "application/javascript",
      "application/json",
      "text/xml",
      "application/xml"
    ]
  },
  "chunked_transfer": {
    "enabled": true,
    "threshold_kb": 1024,
    "buffer_size_kb": 32
  },
  "cleanup_ignore": [".*", "*.gitkeep"]
}
```

本轮新增/变化的两项（下表同步）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `template_file` | string | 建域用的 v5 配置模板（`quartz.config.yaml`）。新域整棵继承它，只改写 `configuration.pageTitle` / `configuration.baseUrl`；未配置时 `POST /api/domain/{domain}` 报 500 |
| `cache_dir` | string | 构建缓存根目录。服务端传给 `--cacheDir` 的是 `{cache_dir}/{domain}`，db 落在 `{cache_dir}/{domain}/.quartz-cache.db`。留空 = `{output_dir}/../cache`（即项目根 `cache/{domain}/`）；指到 settings 目录就是 `settings/{domain}/.quartz-cache.db`。**不能省**：quartz5 不接 `--cacheDir` 时会退回 `{CLI 工作目录}/data`（全域共用） |
| `command.work_dir` | string | **已切到 `quartz5/`**（v4 时代指向 `client/`） |

| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | string | 配置格式版本号 |
| `listen_addr` | string | 监听地址和端口 |
| `base_url` | string | 服务器基础 URL（用于生成业务域 baseUrl） |
| `optional_param` | string | 构建 API 的 reset 参数名 |
| `forbidden_page` | string | 401 页面文件名 |
| `auth.user_param` | string | 认证用户名参数名 |
| `auth.pwd_param` | string | 认证密码参数名 |
| `auth.user` | string | 用户名 |
| `auth.pwd` | string | 密码 |
| `auth.cookie_max_age` | int | Cookie 有效期（秒，0=会话级）|
| `command.work_dir` | string | 构建命令的工作目录 |
| `command.interpreter` | string | 构建命令解释器 |
| `command.interpreter_args` | string | 解释器参数 |
| `command.script` | string | 构建脚本路径 |
| `command.args` | string | 构建脚本参数 |
| `command.optional_flag` | string | 可选的 reset 构建参数 |
| `input_dir` | string | Markdown 输入根目录 |
| `output_dir` | string | 构建输出根目录 |
| `settings_dir` | string | 业务域配置根目录 |
| `compression.enabled` | bool | 是否启用 gzip 压缩 |
| `compression.level` | int | 压缩级别（1-9） |
| `compression.min_size_kb` | int | 最小压缩阈值（KB） |
| `compression.types[]` | string[] | 需要压缩的 MIME 类型列表 |
| `chunked_transfer.enabled` | bool | 是否启用分块传输 |
| `chunked_transfer.threshold_kb` | int | 分块传输阈值（KB） |
| `chunked_transfer.buffer_size_kb` | int | 分块缓冲区大小（KB） |
| `cleanup_ignore[]` | string[] | output 清理时忽略的 glob 模式 |

---

## 错误码

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（认证失败）|
| 404 | 资源不存在 |
| 405 | 方法不允许 |
| 409 | 冲突（如任务正在运行）|
| 500 | 服务器内部错误 |

---

## 完整使用流程示例

### 1. 创建新业务域 xm1

```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm1?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"config": {"pageTitle": "业务域1"}}'
```

### 2. 添加 Markdown 文件

在 `input/xm1/` 目录下创建 Markdown 文件。

### 3. 更新业务域配置（可选）

```bash
curl -X PUT "http://127.0.0.1:8766/api/domain/xm1?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {"pageTitle": "业务域1"},
    "layout": {"backlinks": {"hideWhenEmpty": false}}
  }'
```

### 4. 触发构建

```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm1/build?user=admin&pwd=password123"
```

### 5. 访问网站

浏览器访问：`http://127.0.0.1:8766/xm1/`

> 注意：`baseUrl` 由服务器自动生成，格式为 `{server config.json base_url}/{domain}`。

---

**文档版本**: v3.1
**更新日期**: 2026-05-12


### 配置接口读写约定（2026-10-26 调整）

- POST/PUT 使用明确的 Go 字段类型；省略字段不修改，`false`、允许的 `0`、`[]` 正常处理。未知字段按原约定返回 warnings，并真正忽略；字段名称按已定义的 JSON 拼写匹配，U3 字段编码不参与。
- 域配置与 folder 配置共用单域读改写锁；提交前校验配置并生成响应数据，临时文件完整写入后替换目标文件。此锁保护单个 Go 服务进程内的操作，不协调外部编辑器或多个服务进程。
- 配置请求体上限 1 MiB，只接受一个 JSON 对象；重复字段、类型/范围错误返回 400，缺失配置的更新返回 404，建域冲突返回 409，文件读写错误返回 500。配置保存错误使用合法的 JSON `error` 响应。
- folder 的 `fields: []` 删除本目录字段覆盖，`sort: null` 清除排序覆盖；未提交的区块不变。
- 域 GET/保存响应移除非必需的 `graph.view_overrides`；已有 YAML 中四视图覆盖原样保留，不改变 Quartz 的合并规则。
- 域列表遇到坏配置仍返回该域标识，并在 warnings 里说明读取错误；详情读取仍报告错误。
- 保存 YAML 与重新构建站点仍是两个步骤，本次未重启服务或触发真实构建。


域接口使用固定、明确的字段范围，不动态公开 YAML 的全部内容。`enabled_plugins` 不在响应结构中，也不是可写字段；域列表、详情及创建/保存返回的域信息均不返回此项。请求提交此键时按未知字段忽略并提示 warnings，不修改 YAML 中的插件配置。不增加隐藏字段的服务开关；`plugin_count` 仍保留为只读统计。


构建状态与日志接口补充：`GET /api/domain/{domain}/logs` 的 `X-Task-Id` 与状态接口 taskId 对应，`X-Task-Status` 使用 queued/running/succeeded/failed/unknown，不再笼统返回 completed；有正文时仍返回 text/plain，无日志仍返回 JSON no_logs。排队提示保留。已有旧命名日志仍可查看，但没有固定结果行的旧日志返回 unknown。`GET /api/tasks` 继续只列排队/运行任务，不包含历史结果。未增加结果文件、数据库、超时或取消接口。


### 四类图谱的独立配置（2026-10-27）

域列表、详情、POST/PUT 的 domain_info 都返回 graph.defaults、graph.local、graph.folder、graph.dimension、graph.global。
JSON 与 YAML 分节一致，公共字段拼写仍为 initial_node_limit、expand_batch_size、load_batch_size、core_min_links；global 另有 folders、core_aggregation_max_levels。
原平铺的 graph.initial_node_limit 等公共字段改为 graph.defaults.initial_node_limit 等，graph.global_folders 改为 graph.global.folders；不设置重复字段或兼容别名。旧平铺字段会作为未知键忽略并提示 warnings，调用端应同步改用分节结构。

```json
{
  "graph": {
    "defaults": {"initial_node_limit":500,"expand_batch_size":20,"load_batch_size":100,"core_min_links":0},
    "local": {"initial_node_limit":500,"expand_batch_size":20,"load_batch_size":100,"core_min_links":0},
    "folder": {"initial_node_limit":500,"expand_batch_size":20,"load_batch_size":100,"core_min_links":0},
    "dimension": {"initial_node_limit":500,"expand_batch_size":20,"load_batch_size":100,"core_min_links":0},
    "global": {"initial_node_limit":500,"expand_batch_size":20,"load_batch_size":100,"core_min_links":0,"folders":[],"core_aggregation_max_levels":2}
  }
}
```

修改接口允许只传某一类中的某一字段，其余配置保持原样。整数门槛：core_min_links >=0，其他数量 >=1；null、浮点数和类型错误返回 400 且不保存。
查询返回每类的生效业务参数：视图自身声明优先，其次公共 defaults，最后内置默认。不会回填或重写 YAML 中未声明的值，不包括插件力导向、布局等技术参数。
三份默认模板现已显式填写四类配置；因此只改 defaults 不会覆盖四类已声明的同名参数，需修改对应视图。
