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
        "graph": { "tags": { "color": "#4a9eff", "displayName": "标签" } }
      },
      "layout": {
        "backlinks": { "hideWhenEmpty": false, "aggregation": { "folder": { "depth": 1, "flatten": true }, "fields": [] } }
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
    "graph": { "tags": { "color": "#4a9eff", "displayName": "标签" } }
  },
  "layout": {
    "backlinks": { "hideWhenEmpty": false, "aggregation": { "folder": { "depth": 1, "flatten": true }, "fields": [] } }
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
    "tags": {
      "color": "#4a9eff",
      "displayName": "标签"
    }
  }
}
```

### quartz.layout.json

```json
{
  "backlinks": {
    "hideWhenEmpty": false,
    "aggregation": {
      "folder": {
        "depth": 1,
        "flatten": true
      },
      "fields": [
        { "field": "date", "granularity": "year", "order": 1 }
      ]
    }
  }
}
```

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
  "listen_addr": "0.0.0.0:8766",
  "base_url": "http://127.0.0.1:8766",
  "build_path": "/api/build",
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
    "work_dir": "E:/ProgramProjects/VScode_projects/quartz-fullstack/client",
    "interpreter": "node",
    "interpreter_args": "--no-deprecation",
    "script": "./quartz/bootstrap-cli.mjs",
    "args": "build --sqlite",
    "optional_flag": "--reset"
  },
  "input_dir": "E:/ProgramProjects/VScode_projects/quartz-fullstack/input",
  "output_dir": "E:/ProgramProjects/VScode_projects/quartz-fullstack/output",
  "settings_dir": "E:/ProgramProjects/VScode_projects/quartz-fullstack/settings",
  "compression": {
    "enabled": true,
    "level": 6,
    "min_size_kb": 1
  },
  "chunked_transfer": {
    "enabled": true,
    "threshold_kb": 1024,
    "buffer_size_kb": 32
  }
}
```

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
