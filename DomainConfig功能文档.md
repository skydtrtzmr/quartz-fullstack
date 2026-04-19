# DomainConfig 功能文档

## 设计原则

1. **简化配置**：只保留两个 JSON 文件，不使用 `domain_config.json`
2. **Client 驱动**：配置在 Client 构建时被读取，Server 只负责 CRUD
3. **目录即 Domain**：settings 下的子目录名即为 domain id

---

## 目录结构

```
settings/{domain}/
├── quartz.config.json   # 配置覆盖（baseUrl, pageTitle, graph）
└── quartz.layout.json   # 布局配置（backlinks, explorer, aggregation）
```

### quartz.config.json

```json
{
  "baseUrl": "127.0.0.1:8767/testwork0",
  "pageTitle": "testwork0",
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

---

## 配置映射关系

| 概念 | 来源 | 说明 |
|------|------|------|
| Domain ID | settings 子目录名 | 自动获取 |
| Display Name | `quartz.config.json` 的 `pageTitle` | 用户可设置 |
| Base URL | 服务器自动生成 | 由 `server/config.json` 的 `base_url` + domain 拼接，**不允许用户自定义** |
| Graph 配置 | `quartz.config.json` 的 `graph` | 用户可设置 |
| Layout 配置 | `quartz.layout.json` | 用户可设置 |

---

## Client 构建流程

```bash
npx quartz build --settings=settings/testwork0 -d input/testwork0 -o output/testwork0
```

1. 读取 `settings/testwork0/quartz.config.json`
2. deepMerge 到 `quartz.config.ts` 的 `configuration` 字段
3. 读取 `settings/testwork0/quartz.layout.json`（如果有）
4. 覆盖对应 layout 配置

---

## Server API

### 1. 列出所有业务域
```
GET /api/domain
```

**响应**：
```json
{
  "count": 2,
  "domains": [
    {
      "domain_name": "xm",
      "display_name": "源悦知识库",
      "config": { "baseUrl": "...", "pageTitle": "源悦知识库", "graph": {...} },
      "layout": { "backlinks": {...} }
    },
    {
      "domain_name": "testwork0",
      "display_name": "testwork0",
      "config": { "baseUrl": "...", "pageTitle": "testwork0", "graph": {...} },
      "layout": { "backlinks": {...} }
    }
  ]
}
```

---

### 2. 获取业务域信息
```
GET /api/domain/{domain}
```

**响应**：
```json
{
  "domain_name": "testwork0",
  "display_name": "testwork0",
  "config": { "baseUrl": "...", "pageTitle": "testwork0", "graph": {...} },
  "layout": { "backlinks": {...} }
}
```

---

### 3. 创建业务域
```
POST /api/domain/create
```

**请求**：
```json
{
  "domain_name": "xm1",
  "display_name": "业务域1"
}
```

**响应**：
```json
{
  "status": "Created",
  "domain": "xm1",
  "message": "Domain created successfully"
}
```

**自动创建**：
- `input/xm1/` 目录
- `settings/xm1/quartz.config.json`
- `settings/xm1/quartz.layout.json`
- `input/xm1/index.md`

---

### 4. 更新业务域配置
```
PUT /api/domain/{domain}
```

**请求**（`config` 和 `layout` 都是可选的，`baseUrl` 由服务器自动生成，**忽略用户传入的值**）：
```json
{
  "config": {
    "pageTitle": "新标题",
    "graph": { "tags": { "color": "#ff0000", "displayName": "标签" } }
  },
  "layout": {
    "backlinks": {
      "hideWhenEmpty": false,
      "aggregation": { "folder": { "depth": 2, "flatten": true }, "fields": [] }
    }
  }
}
```

**响应**：
```json
{
  "status": "Saved",
  "domain": "testwork0"
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

**响应**：
```json
{
  "status": "Deleted",
  "domain": "testwork0",
  "message": "Domain deleted successfully",
  "deletedInput": true,
  "deletedOutput": true
}
```

---

### 6. 触发构建
```
POST /api/domain/{domain}/build
```

**参数**：`?optional=true` 启用 reset 模式

**响应**：
```json
{
  "status": "Accepted",
  "message": "Build triggered for domain: testwork0",
  "command": "node build --settings=settings/testwork0 -d input/testwork0 -o output/testwork0"
}
```

---

### 7. 获取构建状态
```
GET /api/domain/{domain}/status
```

**响应**（运行中）：
```json
{
  "status": "running",
  "domain": "testwork0",
  "taskId": "testwork0-1745067600",
  "startTime": "2026-04-19T15:00:00Z"
}
```

**响应**（空闲）：
```json
{
  "status": "idle",
  "domain": "testwork0"
}
```

---

### 8. 获取构建日志
```
GET /api/domain/{domain}/logs
```

---

## Go 数据结构

```go
// QuartzConfig quartz.config.json 结构
type QuartzConfig struct {
    BaseUrl   string `json:"baseUrl"`
    PageTitle string `json:"pageTitle"`
    Graph     struct {
        Tags struct {
            Color       string `json:"color"`
            DisplayName string `json:"displayName"`
        } `json:"tags"`
    } `json:"graph"`
}

// QuartzLayout quartz.layout.json 结构
type QuartzLayout struct {
    Backlinks struct {
        HideWhenEmpty bool `json:"hideWhenEmpty"`
        Aggregation   struct {
            Folder struct {
                Depth   int  `json:"depth"`
                Flatten bool `json:"flatten"`
            } `json:"folder"`
            Fields []struct {
                Field       string `json:"field"`
                Granularity string `json:"granularity"`
                Order       int    `json:"order"`
            } `json:"fields"`
        } `json:"aggregation"`
    } `json:"backlinks"`
}

// DomainInfo 业务域信息
type DomainInfo struct {
    DomainName  string       `json:"domain_name"`
    DisplayName string       `json:"display_name"`
    Config      QuartzConfig `json:"config"`
    Layout      QuartzLayout `json:"layout"`
}
```

---

**文档版本**: v3.0
**更新日期**: 2026-04-19
