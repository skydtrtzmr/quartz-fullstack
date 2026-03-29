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
GET /api/domain?user=admin&pwd=password123
```

**方式2：Cookie**
首次使用 URL 参数认证成功后，服务端会设置 `quartz_auth` Cookie，后续请求可自动通过。

---

## 业务域管理 API

业务域（Domain）是 Quartz 的多租户隔离单位，如 `xm`、`xm1`、`xm2` 等。每个业务域有独立的：
- 输入目录：`input/{domain}/`
- 输出目录：`output/{domain}/`
- 配置目录：`settings/{domain}/`

### 1. 列出所有业务域

```
GET /api/domain
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domain?user=admin&pwd=password123"
```

**响应**：
```json
{
  "domains": ["xm", "xm1", "xm2"],
  "count": 3
}
```

---

### 2. 创建业务域

```
POST /api/domain/create
```

**请求体**：
```json
{
  "domain_name": "xm1",
  "display_name": "业务域1",
  "description": "这是第一个测试业务域"
}
```

**请求示例**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/create?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"domain_name": "xm1", "display_name": "业务域1", "description": "测试业务域"}'
```

**响应**：
```json
{
  "status": "Created",
  "domain": "xm1",
  "message": "Domain created successfully"
}
```

**说明**：
- 自动创建 `input/xm1/` 和 `settings/xm1/` 目录
- 自动生成默认的 `domain_config.json` 和 `index.md`

---

### 3. 获取业务域配置

```
GET /api/domain/{domain}/config
```

**请求示例**：
```bash
curl "http://127.0.0.1:8766/api/domain/xm/config?user=admin&pwd=password123"
```

**响应**：
```json
{
  "domain_name": "xm",
  "display_name": "xm",
  "description": "",
  "root_folders": [],
  "aggregation_fields": {
    "graph_fields": [
      {
        "field_name": "tags",
        "display_name": "标签",
        "color": "#4a9eff",
        "enabled": true
      }
    ],
    "explorer_fields": [
      {
        "field_name": "folder",
        "display_name": "文件夹",
        "group_by": true,
        "sort_order": 1
      }
    ]
  },
  "build_overrides": {
    "base_url": "127.0.0.1:8767/xm"
  }
}
```

---

### 4. 更新业务域配置

```
PUT /api/domain/{domain}/config
POST /api/domain/{domain}/config
```

**请求体**：
```json
{
  "domain_name": "xm",
  "display_name": "主业务域",
  "description": "核心业务知识库",
  "root_folders": [
    {
      "name": "项目文档",
      "display_name": "项目文档",
      "description": "项目相关文档",
      "icon": "📁",
      "order": 1,
      "visible": true
    }
  ],
  "aggregation_fields": {
    "graph_fields": [
      {
        "field_name": "tags",
        "display_name": "标签",
        "color": "#4a9eff",
        "enabled": true
      },
      {
        "field_name": "category",
        "display_name": "分类",
        "color": "#ff6b6b",
        "enabled": true
      }
    ],
    "explorer_fields": [
      {
        "field_name": "folder",
        "display_name": "文件夹",
        "group_by": true,
        "sort_order": 1
      }
    ]
  },
  "build_overrides": {
    "base_url": "127.0.0.1:8767/xm",
    "enable_graph": true,
    "enable_explorer": true,
    "enable_search": true
  }
}
```

**请求示例**：
```bash
curl -X PUT "http://127.0.0.1:8766/api/domain/xm/config?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"domain_name": "xm", "display_name": "主业务域", ...}'
```

**响应**：
```json
{
  "status": "Saved",
  "domain": "xm"
}
```

---

### 5. 删除业务域配置

```
DELETE /api/domain/{domain}/config
```

**请求示例**：
```bash
curl -X DELETE "http://127.0.0.1:8766/api/domain/xm/config?user=admin&pwd=password123"
```

**响应**：
```json
{
  "status": "Deleted",
  "domain": "xm"
}
```

**注意**：此操作仅删除配置文件，不会删除输入目录和输出目录。

---

## 构建 API

### 1. 触发指定业务域构建（推荐）

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
  "message": "Build triggered for domain: xm"
}
```

**构建流程**：
1. 加载业务域配置 `settings/{domain}/domain_config.json`
2. 应用配置生成 Quartz 配置文件 `settings/{domain}/config.json`
3. 执行构建命令：
   ```
   node ./quartz/bootstrap-cli.mjs build --sqlite --settings={settingsDir}/{domain} -d {inputDir}/{domain} -o {outputDir}/{domain}
   ```
4. 构建日志保存到 `logs/tasks/task-{timestamp}.log`

---

### 2. 传统构建端点（兼容）

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

### 构建任务状态

构建任务异步执行，同一时间只能有一个任务在运行。

**忙碌响应**：
```json
{
  "status": "Busy",
  "message": "A task is running",
  "description": "已有任务正在执行，请稍后再试"
}
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

### Nginx 配置参考

```nginx
server {
    listen 8767;
    server_name localhost;
    root "E:/ProgramProjects/VScode_projects/quartz-fullstack/output";
    index index.html;

    # 业务域 xm
    location /xm/ {
        try_files $uri $uri/ $uri.html =404;
    }
    
    # 业务域 xm1
    location /xm1/ {
        try_files $uri $uri/ $uri.html =404;
    }

    error_page 404 /404.html;
}
```

### 缓存控制

- **HTML/JSON 文件**：`Cache-Control: no-store`（不缓存）
- **静态资源**：`Cache-Control: public, max-age=31536000`（长期缓存）

### 路径重定向规则

后端会自动处理以下重定向：

| 访问路径 | 响应 | 目标路径 |
|---------|------|---------|
| `/xm` | 301 Moved Permanently | `/xm/` |
| `/xm/page` | 200 OK | `output/xm/page.html` |
| `/static/...` | 404 Not Found | - |

> **注意**：直接访问 `/static/contentIndex.json` 会返回 404，必须通过业务域路径访问，如 `/xm/static/contentIndex.json`。

---

## 配置数据结构

### DomainConfig（业务域配置）

```typescript
interface DomainConfig {
  domain_name: string;        // 业务域标识（如 xm, xm1）
  display_name: string;       // 显示名称
  description: string;        // 描述
  root_folders: RootFolderConfig[];    // 一级目录配置
  aggregation_fields: AggregationConfig; // 聚合字段配置
  build_overrides: BuildConfig;          // 构建设置覆盖
}

interface RootFolderConfig {
  name: string;           // 目录名
  display_name: string;   // 显示名
  description: string;    // 描述
  icon: string;           // 图标
  order: number;          // 排序
  visible: boolean;       // 是否可见
}

interface AggregationConfig {
  graph_fields: GraphFieldMapping[];       // 图谱聚合字段
  explorer_fields: ExplorerFieldMapping[]; // 目录聚合字段
}

interface GraphFieldMapping {
  field_name: string;     // 字段名（如 tags, category）
  display_name: string;   // 显示名
  color: string;          // 颜色（十六进制）
  enabled: boolean;       // 是否启用
}

interface ExplorerFieldMapping {
  field_name: string;     // 字段名
  display_name: string;   // 显示名
  group_by: boolean;      // 是否按此分组
  sort_order: number;     // 排序优先级
}

interface BuildConfig {
  base_url?: string;      // 覆盖 baseUrl
  theme?: string;         // 主题
  enable_graph?: boolean;     // 启用图谱
  enable_explorer?: boolean;  // 启用目录
  enable_search?: boolean;    // 启用搜索
}
```

---

## 目录结构

```
quartz-fullstack/
├── input/                    # Markdown 输入目录
│   ├── xm/                   # xm 业务域输入
│   ├── xm1/                  # xm1 业务域输入
│   └── xm2/
├── output/                   # 构建输出目录
│   ├── xm/                   # xm 业务域输出（对应 /xm/ URL）
│   ├── xm1/                  # xm1 业务域输出（对应 /xm1/ URL）
│   └── xm2/
├── settings/                 # 配置目录
│   ├── xm/                   # xm 业务域配置
│   │   ├── domain_config.json   # 业务域配置（后端管理）
│   │   ├── config.json          # Quartz 配置（自动生成）
│   │   └── layout.json          # Quartz 布局配置
│   ├── xm1/
│   └── xm2/
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
curl -X POST "http://127.0.0.1:8766/api/domain/create?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_name": "xm1",
    "display_name": "业务域1",
    "description": "第一个业务域"
  }'
```

### 2. 添加 Markdown 文件

在 `input/xm1/` 目录下创建 Markdown 文件。

### 3. 更新业务域配置（可选）

```bash
curl -X PUT "http://127.0.0.1:8766/api/domain/xm1/config?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_name": "xm1",
    "display_name": "业务域1",
    "build_overrides": {
      "base_url": "127.0.0.1:8767/xm1",
      "enable_graph": true
    }
  }'
```

### 4. 触发构建

```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm1/build?user=admin&pwd=password123"
```

### 5. 访问网站

浏览器访问：`http://127.0.0.1:8767/xm1/`

---

**文档版本**: v1.0  
**更新日期**: 2026-03-29
