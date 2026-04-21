# Quartz 后端研发任务清单

## ✅ 已完成

### 业务域核心功能
- [x] **业务域区分**：基于 `settings/{domain}/` 目录作为 domain 权威来源，分别进行图谱/目录构建
  - 实现位置：`server/domain_config.go`（DomainManager 结构体）
  - 目录结构：`settings/{domain}/quartz.config.json` + `quartz.layout.json`

- [x] **业务域配置 API**：
  - `GET /api/domain` - 列出所有 domain
  - `POST /api/domain/create` - 创建 domain（同时创建目录和默认 index.md）
  - `PUT /api/domain/{domain}` - 更新 domain 配置（config + layout）
  - `GET /api/domain/{domain}` - 获取 domain 信息
  - `DELETE /api/domain/{domain}` - 删除业务域（配置目录 + 可选输入/输出目录）
  - `POST /api/domain/{domain}/build` - 触发指定 domain 的构建
  - 实现位置：`server/domain_config.go`（HTTP Handlers）+ `server/api.go`

- [x] **构建状态与日志 API**：
  - `GET /api/domain/{domain}/status` - 获取指定 domain 的构建状态
  - `GET /api/domain/{domain}/logs` - 获取指定 domain 的构建日志
  - `GET /api/tasks` - 获取所有正在运行的任务
  - 实现位置：`server/domain_config.go`

- [x] **baseUrl 自动生成**：
  - 根据 `server/config.json` 的 `base_url` + domain 自动拼接
  - 用户在 API 请求中传入的 `baseUrl` 会被忽略
  - 实现位置：`server/domain_config.go`（generateBaseUrl 函数）

### 业务域配置结构
```go
type QuartzConfig struct {
    BaseUrl   string         // 由服务器自动生成
    PageTitle string         // 显示名称（用户可设置）
    Graph     GraphConfig    // 图谱配置
}

type QuartzLayout struct {
    Backlinks    BacklinksConfig    // 反向链接配置
}

type GraphConfig struct {
    Tags      TagConfig
    Category  TagConfig
}

type TagConfig struct {
    Color       string
    DisplayName string
}

type BacklinksConfig struct {
    HideWhenEmpty bool
    Aggregation   AggregationConfig
}

type AggregationConfig struct {
    Folder  FolderConfig
    Fields  []FieldConfig
}

type FieldConfig struct {
    Field      string
    Granularity string  // "year", "month", "quarter", 或 ""
    Order      int
}
```

### 构建设置
- [x] **异步构建执行**：构建任务在后台 goroutine 执行
- [x] **按 domain 并行构建**：不同 domain 可以同时构建，同一 domain 串行执行
  - 使用 `DomainTaskManager` 管理任务状态
  - 位于：`server/main.go`
- [x] **构建日志记录**：每个构建任务生成独立日志文件（`server/logs/tasks/task-{domain}-{timestamp}.log`）
- [x] **命令行参数白名单验证**：防止非法参数注入
- [x] **认证授权**：基于用户名/密码的简单认证机制

### 服务版本与启动信息
- [x] **版本号管理**：通过 `config.json` 的 `version` 字段配置
- [x] **启动信息框**：服务启动时打印版本、监听地址、输入/输出目录
- [x] **默认值支持**：若未配置 version，使用默认值 "1.0.0"

### 任务状态管理
```go
type TaskState struct {
    Domain     string        // 业务域
    TaskID     string        // 任务ID
    StartTime  time.Time     // 开始时间
    Reset      bool          // 是否使用重置标志
    Command    string        // 执行命令
    LogPath    string        // 日志文件路径
}

type DomainTaskManager struct {
    mu    sync.Mutex
    tasks map[string]*TaskState  // domain -> task state
}
```

---

## 📋 API 接口文档

> 完整的 API 文档请参考 `API文档.md`。

### 业务域管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/domain` | 列出所有业务域 |
| POST | `/api/domain/{domain}` | 创建业务域 |
| GET | `/api/domain/{domain}` | 获取业务域信息 |
| PUT | `/api/domain/{domain}` | 更新业务域配置（config + layout） |
| DELETE | `/api/domain/{domain}` | 删除业务域 |
| POST | `/api/domain/{domain}/build` | 触发构建 |
| GET | `/api/domain/{domain}/status` | 获取构建状态 |
| GET | `/api/domain/{domain}/logs` | 获取构建日志 |
| GET | `/api/domain/tasks` | 获取所有运行中的任务 |

### 配置说明

**注意**：`baseUrl` 由服务器自动生成，公式为 `{server config.json base_url}/{domain}`，用户传入的值会被忽略。

**API 请求格式**（更新业务域配置）：
```json
{
  "config": {
    "pageTitle": "新标题",
    "graph": { "tags": { "color": "#ff0000", "displayName": "标签" } }
  },
  "layout": {
    "backlinks": {
      "aggregation": {
        "folder": { "depth": 2, "flatten": true },
        "fields": [{ "field": "date", "granularity": "year", "order": 1 }]
      }
    }
  }
}
```

---

## 📋 待开发功能

### 配置验证
- [ ] **配置验证 API**：创建/更新配置时的合法性检查
  - 验证域名格式（字母数字下划线）
  - 验证配置文件 JSON 结构
  - 验证路径不存在冲突

### 高级功能
- [ ] **Webhook 回调**：构建完成时回调外部 URL
  - 配置项：`webhook_url`
  - 支持重试机制

- [ ] **构建缓存管理**：
  - `POST /api/domain/{domain}/cache/clear` - 清理构建缓存
  - `GET /api/domain/{domain}/cache/status` - 获取缓存状态

- [ ] **构建历史 API**：`GET /api/domain/{domain}/history`
  - 返回最近 N 次构建记录
  - 每条记录包含：时间、状态、耗时、日志路径

- [ ] **批量操作 API**：
  - `POST /api/domain/batch-build` - 同时触发多个 domain 构建
  - `GET /api/domain/stats` - 返回整体统计信息

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `server/main.go` | 服务入口，路由注册，DomainTaskManager |
| `server/api.go` | 通用构建 API（`/api/build`） |
| `server/domain_config.go` | 业务域管理（DomainManager + Handlers） |
| `server/config.go` | 服务配置加载 |
| `server/config.json` | 服务配置文件 |
| `server/static.go` | 静态文件服务 |

---

## 🔧 配置示例

`server/config.json`:
```json
{
  "port": 8766,
  "base_url": "http://127.0.0.1:8766",
  "input_dir": "e:/ProgramProjects/VScode_projects/quartz-fullstack/input",
  "output_dir": "e:/ProgramProjects/VScode_projects/quartz-fullstack/output",
  "settings_dir": "e:/ProgramProjects/VScode_projects/quartz-fullstack/settings",
  "auth": {
    "user": "admin",
    "pwd": "admin",
    "user_param": "u",
    "pwd_param": "p"
  },
  "command": {
    "interpreter": "npx",
    "interpreter_args": "",
    "script": "quartz",
    "args": "build --sqlite",
    "optional_flag": "--reset",
    "work_dir": "e:/ProgramProjects/VScode_projects/quartz-fullstack/client"
  }
}
```

`settings/{domain}/quartz.config.json`:
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

`settings/{domain}/quartz.layout.json`:
```json
{
  "backlinks": {
    "hideWhenEmpty": false,
    "aggregation": {
      "folder": {
        "depth": 1,
        "flatten": true
      },
      "fields": []
    }
  }
}
```

---

## 📝 开发注意事项

1. **编码**：所有源文件必须使用 UTF-8 编码
2. **并发安全**：使用 sync.Mutex 保护共享状态（DomainTaskManager）
3. **日志规范**：使用 `log.Printf` 输出到标准日志
4. **错误处理**：返回结构化 JSON 错误信息，便于前端解析
5. **构建并行**：不同 domain 可并行构建，同一 domain 必须串行
6. **baseUrl 规则**：`baseUrl` 由服务器自动生成，用户不可自定义