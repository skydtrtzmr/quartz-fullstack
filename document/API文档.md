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

业务域（Domain）是 Quartz 的多租户隔离单位，如 `xm`、`xm1`、`testwork0` 等。每个业务域有独立的：
- 输入目录：`input/{domain}/`
- 输出目录：`output/{domain}/`
- 配置目录：`settings/{domain}/`

### 1. 列出所有业务域

```
GET /api/domains
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domains?user=admin&pwd=password123"
```

**响应**：
```json
{
  "count": 2,
  "domains": [
    {
      "domain_name": "xm",
      "display_name": "源悦知识库",
      "config": {
        "pageTitle": "源悦知识库",
        "baseUrl": "http://127.0.0.1:8766/xm",
        "graph": { "precomputeLocal": false, "localDepth": 1, "fallbackToBfs": false }
      },
      "layout": {
        "backlinks": { "hideWhenEmpty": false, "aggregation": [{ "type": "folder", "depth": 1 }] }
      }
    },
    {
      "domain_name": "testwork0",
      "display_name": "testwork0",
      "config": { "pageTitle": "testwork0", "baseUrl": "http://127.0.0.1:8766/testwork0", "graph": { ... } },
      "layout": { ... }
    }
  ]
}
```

---

### 2. 创建业务域

```
POST /api/domain/{domain}
```

**请求体**（`config` 和 `layout` 都是可选的，未传则使用默认值）：
```json
{
  "config": {
    "pageTitle": "业务域1"
  }
}
```

**请求示例**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm1?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"config": {"pageTitle": "业务域1"}}'
```

**响应**（成功）：
```json
{
  "status": "Created",
  "domain": "xm1",
  "message": "Domain created successfully"
}
```

**响应**（域名已存在）：
```json
{
  "error": "Domain 'xm1' already exists"
}
```

**说明**：
- 域名从 URL 路径中获取，不再从 body 中传 `domain_name`
- 自动创建 `input/xm1/` 和 `settings/xm1/` 目录
- 自动生成默认的 `quartz.config.json`、`quartz.layout.json` 和 `index.md`
- 可在 body 中传入 `config` 和/或 `layout` 覆盖默认值

---

### 3. 获取业务域信息

```
GET /api/domain/{domain}
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123"
```

**响应**：
```json
{
  "domain_name": "xm",
  "display_name": "源悦知识库",
  "config": {
    "pageTitle": "源悦知识库",
    "baseUrl": "http://127.0.0.1:8766/xm",
    "graph": { "precomputeLocal": false, "localDepth": 1, "fallbackToBfs": false }
  },
    "layout": {
      "backlinks": { "hideWhenEmpty": false, "aggregation": [{ "type": "folder", "depth": 1 }] },
      "graph": { "aggregation": [{ "type": "folder", "depth": 1 }, { "type": "field", "field": "type" }] }
    }
}
```

---

### 4. 更新业务域配置

```
PUT /api/domain/{domain}
POST /api/domain/{domain}
```

**请求体**（`config` 和 `layout` 都是可选的，`baseUrl` 由服务器自动生成，用户传入的值会被忽略）：
```json
{
  "config": {
    "pageTitle": "新标题",
    "graph": {
      "tags": {
        "color": "#ff0000",
        "displayName": "标签"
      }
    }
  },
  "layout": {
    "backlinks": {
      "hideWhenEmpty": false,
      "aggregation": {
        "folder": {
          "depth": 2,
          "flatten": true
        },
        "fields": [
          { "field": "date", "granularity": "year", "order": 1 }
        ]
      }
    },
    "graph": {
      "aggregation": {
        "folder": { "depth": 1, "flatten": true },
        "fields": [
          { "field": "type", "order": 1 }
        ]
      }
    }
  }
}
```

**请求示例**：
```bash
# 只更新 pageTitle
curl -X PUT "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"config": {"pageTitle": "新标题"}}'

# 只更新 layout
curl -X PUT "http://127.0.0.1:8766/api/domain/xm?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"layout": {"backlinks": {"hideWhenEmpty": true}}}'
```

**响应**：
```json
{
  "status": "Saved",
  "domain": "xm"
}
```

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
  "command": "node build --settings=settings/xm -d input/xm -o output/xm"
}
```

**构建流程**：
1. 检查业务域目录是否存在
2. 执行构建命令：`node ./quartz/bootstrap-cli.mjs build --sqlite --settings={settingsDir}/{domain} -d {inputDir}/{domain} -o {outputDir}/{domain}`
3. 构建日志保存到 `logs/tasks/task-{timestamp}.log`

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

**响应**（空闲）：
```json
{
  "status": "idle",
  "domain": "xm"
}
```

---

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

### 4. 传统构建端点（兼容）

```
POST /api/build
```

**查询参数**：

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `domain` | string | 业务域名称 | `xm` |
| `reset` | boolean | 是否重置后构建 | `true` |

**请求示例**：
```bash
# 构建 xm 业务域（增量构建）
curl -X POST "http://127.0.0.1:8766/api/build?user=admin&pwd=password123&domain=xm"

# 重置后构建
curl -X POST "http://127.0.0.1:8766/api/build?user=admin&pwd=password123&domain=xm&reset=true"
```

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

### quartz.config.json

**注意**：`baseUrl` 由服务器根据 `config.json` 的 `base_url` + domain 自动生成，API 请求中传入的值会被忽略。

```json
{
  "pageTitle": "源悦知识库",
  "graph": {
    "precomputeLocal": false,
    "localDepth": 1,
    "fallbackToBfs": false
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `pageTitle` | string | 页面标题/业务域显示名称 |
| `graph.precomputeLocal` | boolean | 是否预计算局部图谱（默认 `false`） |
| `graph.localDepth` | number | 局部图谱深度（默认 `1`） |
| `graph.fallbackToBfs` | boolean | 是否回退到 BFS 算法（默认 `false`） |

### quartz.layout.json

**所有字段均为可选**，不传则使用前端默认值。反向链接和图谱**共用同一 `AggregationConfig` 结构**，均为 `AggregationRule[]` 规则列表，按数组顺序执行。

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
      { "type": "folder", "depth": 1 },
      { "type": "date", "field": "date", "granularity": "year" },
      { "type": "field", "field": "type" }
    ]
  },
  "graph": {
    "aggregation": [
      { "type": "folder", "depth": 1 },
      { "type": "field", "field": "type" }
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

**不同文件夹使用不同排序逻辑**：`quartz.layout.json` 中的排序配置是全局的，但不同文件夹可以通过在各自文件的 frontmatter 中设置**同一排序字段的不同值**来实现差异化排序效果。例如全局配置 `"field": "priority"`，项目文件夹下的文件设置 `priority: 1, 2, 3...`，任务文件夹下的文件也设置各自的 `priority` 值，各自文件夹内即按该字段独立排序。

> **注意**：`backlinks.aggregation` 与 `graph.aggregation` 共用完全相同的结构（`AggregationConfig`），均为规则列表。数组顺序即执行顺序，每条规则独立配置，按顺序依次对未聚合的叶子节点进行分组。不再使用 `order` 字段，也不再区分 `folder` 和 `fields` 两个独立配置块。

### DomainInfo（API 响应结构）

```typescript
interface DomainInfo {
  domain_name: string;     // 业务域标识（目录名）
  display_name: string;    // 显示名称（从 pageTitle 获取）
  config: QuartzConfig;   // quartz.config.json 内容
  layout: QuartzLayout;  // quartz.layout.json 内容
}
```

---

## 目录结构

```
quartz-fullstack/
├── input/                    # Markdown 输入目录
│   ├── xm/                   # xm 业务域输入
│   └── xm1/                  # xm1 业务域输入
├── output/                   # 构建输出目录
│   ├── xm/                   # xm 业务域输出（对应 /xm/ URL）
│   └── xm1/                  # xm1 业务域输出（对应 /xm1/ URL）
├── settings/                 # 配置目录
│   ├── xm/                   # xm 业务域配置
│   │   ├── quartz.config.json   # Quartz 配置
│   │   └── quartz.layout.json    # Quartz 布局配置
│   └── xm1/
├── server/                   # 后端服务代码
│   ├── main.go
│   ├── api.go
│   ├── static.go
│   ├── domain_config.go      # 业务域管理
│   └── config.json           # 后端服务配置
└── client/                   # Quartz 前端代码
```

---

## 后端服务配置

`server/config.json`：

```json
{
  "version": "1.0.1",
  "listen_addr": "0.0.0.0:8766",
  "base_url": "http://127.0.0.1:8766",
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
    "work_dir": "/path/to/quartz-fullstack/client",
    "interpreter": "node",
    "interpreter_args": "--no-deprecation",
    "script": "./quartz/bootstrap-cli.mjs",
    "args": "build --sqlite",
    "optional_flag": "--reset"
  },
  "input_dir": "/path/to/quartz-fullstack/input",
  "output_dir": "/path/to/quartz-fullstack/output",
  "settings_dir": "/path/to/quartz-fullstack/settings",
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

**文档版本**: v3.0
**更新日期**: 2026-04-19
