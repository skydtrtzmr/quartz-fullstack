# Quartz 全栈项目 - AI 代理指南

本文档面向 AI 编码代理，提供项目的完整技术概览、架构说明和开发指南。

## 项目概述

Quartz 全栈项目是一个**多业务域静态站点生成系统**，由以下两部分组成：

1. **Client（前端引擎）**: 基于 Quartz v4 的静态站点生成器（Node.js/TypeScript）
2. **Server（后端服务）**: Go 编写的 HTTP 服务，负责构建调度和静态文件服务

### 核心设计理念

- **引擎与数据解耦**: 前端引擎代码零污染，配置策略全剥离
- **多业务域隔离**: 支持无限个独立业务域（如 `xm`, `xm1`, `xm2`），各域完全隔离
- **部署灵活**: 输入/输出/配置目录可任意移动，只需修改后端配置

## 技术栈

| 层级 | 技术 | 版本/说明 |
|------|------|----------|
| 前端引擎 | Node.js | >= 22 |
| 前端引擎 | TypeScript | 5.9+ |
| 前端引擎 | React/Preact | 预渲染组件 |
| 前端引擎 | ESBuild | 打包工具 |
| 后端服务 | Go | 1.24.4+ |
| 后端服务 | lumberjack | 日志轮转 |
| 数据存储 | SQLite | 图谱缓存（.quartz-cache.db）|

## 项目结构

```
quartz-fullstack/
├── client/                   # Quartz 前端引擎（纯渲染引擎）
│   ├── quartz/              # 核心源代码
│   │   ├── components/      # React 组件（页面布局、搜索、图谱等）
│   │   ├── plugins/         # 插件系统（transformers, emitters, filters）
│   │   ├── util/            # 工具函数（路径处理、图谱数据库等）
│   │   ├── static/          # 静态资源（字体、图标、Katex等）
│   │   ├── styles/          # SCSS 样式文件
│   │   ├── themes/          # 主题配置（颜色方案）
│   │   ├── i18n/            # 国际化（支持 30+ 语言）
│   │   ├── build.ts         # 构建入口
│   │   └── bootstrap-cli.mjs # CLI 启动器
│   ├── quartz.config.ts     # Quartz 主配置（支持运行时 JSON 覆盖）
│   ├── quartz.layout.ts     # 页面布局配置（支持运行时 JSON 覆盖）
│   ├── package.json         # Node.js 依赖
│   └── node_modules/        # 依赖目录
│
├── server/                   # Go 后端服务
│   ├── main.go              # 服务入口，HTTP 路由注册
│   ├── api.go               # 构建 API 处理器
│   ├── static.go            # 静态文件服务（含认证）
│   ├── domain_config.go     # 业务域管理（CRUD + 配置转换）
│   ├── compression.go       # GZIP 压缩中间件
│   ├── config.go            # 配置加载与默认值
│   └── config.json          # 服务运行时配置（**重要**：包含路径配置）
│
├── input/                    # Markdown 输入根目录
│   ├── xm/                  # 业务域 xm 的源文件
│   │   ├── index.md         # 首页
│   │   └── ...              # 其他 Markdown 文件
│   ├── xm1/                 # 业务域 xm1
│   └── xm2/                 # 业务域 xm2
│
├── output/                   # 构建输出根目录
│   ├── xm/                  # xm 业务域输出（对应 /xm/ URL）
│   │   ├── index.html       # 首页
│   │   └── static/          # 静态资源
│   ├── xm1/
│   └── xm2/
│
├── settings/                 # 配置根目录
│   ├── xm/                  # xm 业务域配置
│   │   ├── domain_config.json  # 业务域配置（后端管理）
│   │   ├── config.json         # Quartz 配置（后端自动生成）
│   │   └── layout.json         # Quartz 布局配置（可选）
│   ├── xm1/
│   └── xm2/
│
└── AGENTS.md                # 本文档
```

## 核心配置说明

### 1. 后端服务配置 (`server/config.json`)

```json
{
  "listen_addr": "0.0.0.0:8766",
  "build_path": "/api/build",
  "optional_param": "reset",
  "auth": {
    "user_param": "user",
    "pwd_param": "pwd",
    "user": "admin",
    "pwd": "password123",
    "cookie_max_age": 0
  },
  "command": {
    "work_dir": "E:/.../client",
    "interpreter": "node",
    "interpreter_args": "--no-deprecation",
    "script": "./quartz/bootstrap-cli.mjs",
    "args": "build --sqlite",
    "optional_flag": "--reset"
  },
  "input_dir": "E:/.../input",
  "output_dir": "E:/.../output",
  "settings_dir": "E:/.../settings",
  "compression": {
    "enabled": true,
    "level": 6,
    "min_size_kb": 1,
    "types": ["text/html", "text/css", ...]
  },
  "chunked_transfer": {
    "enabled": true,
    "threshold_kb": 1024,
    "buffer_size_kb": 32
  }
}
```

**关键字段说明**:
- `command.work_dir`: Quartz CLI 执行目录，必须是 `client` 目录
- `input_dir/output_dir/settings_dir`: 三大根目录的绝对路径
- `compression`: GZIP 压缩配置
- `chunked_transfer`: 大文件分片传输配置

### 2. 业务域配置 (`settings/{domain}/domain_config.json`)

```json
{
  "domain_name": "xm",
  "display_name": "业务域显示名",
  "description": "业务域描述",
  "root_folders": [
    {
      "name": "项目文档",
      "display_name": "项目文档",
      "description": "",
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

### 3. Quartz 运行时配置 (`settings/{domain}/config.json`)

由后端根据 `domain_config.json` 自动生成，Quartz 构建时通过 `--settings` 参数加载。

```json
{
  "baseUrl": "127.0.0.1:8767/xm",
  "graph": {
    "tags": {
      "displayName": "标签",
      "color": "#4a9eff"
    }
  }
}
```

### 4. Quartz 布局配置 (`settings/{domain}/layout.json`)

可选文件，用于覆盖页面布局排序等行为。

```json
{
  "explorer": {
    "sortBy": {
      "key": "name",
      "order": "asc"
    }
  },
  "backlinks": {
    "hideWhenEmpty": false
  },
  "folderPage": {
    "sortBy": {
      "key": "name",
      "order": "asc"
    }
  }
}
```

## 构建与运行

### 启动后端服务

```bash
cd server

# 首次运行：下载依赖
go mod tidy

# 构建可执行文件（优化体积）
go build -ldflags="-s -w" -o quartz-service.exe .

# 运行服务
./quartz-service.exe
```

服务启动后监听 `0.0.0.0:8766`。

### 首次访问

浏览器访问: `http://127.0.0.1:8766?user=admin&pwd=password123`

认证成功后，Cookie 会保存登录状态。

### API 构建触发

```bash
# 构建指定业务域（推荐方式）
curl -X POST "http://127.0.0.1:8766/api/domain/xm/build?user=admin&pwd=password123"

# 重置后构建（清除 SQLite 缓存）
curl -X POST "http://127.0.0.1:8766/api/domain/xm/build?user=admin&pwd=password123&reset=true"

# 传统构建端点（兼容）
curl -X POST "http://127.0.0.1:8766/api/build?user=admin&pwd=password123&domain=xm"
```

### 本地开发构建（直接调用 Quartz CLI）

```bash
cd client

# 安装依赖
npm install

# 构建单个业务域（开发调试）
npx quartz build -d ../input/xm -o ../output/xm --settings ../settings/xm --sqlite

# 开发模式（带热重载）
npx quartz build --serve -d ../input/xm -o ../output/xm --settings ../settings/xm
```

## API 端点参考

### 业务域管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/domain` | 列出所有业务域 |
| POST | `/api/domain/create` | 创建新业务域 |
| GET | `/api/domain/{domain}/config` | 获取业务域配置 |
| PUT/POST | `/api/domain/{domain}/config` | 更新业务域配置 |
| DELETE | `/api/domain/{domain}/config` | 删除业务域配置 |
| POST | `/api/domain/{domain}/build` | 触发指定域构建 |

### 构建 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/build` | 传统构建端点（带 `domain` 参数）|

### 静态文件服务

| URL 模式 | 说明 |
|----------|------|
| `/{domain}/` | 访问业务域首页 |
| `/{domain}/{path}` | 访问业务域内页面 |

所有静态文件请求都需要认证（Cookie 或 URL 参数）。

## 数据流转与架构

### 构建调度流程

```
1. 触发构建 (POST /api/domain/xm/build)
   ↓
2. 后端加载 domain_config.json
   ↓
3. 后端生成 config.json (供 Quartz 使用)
   ↓
4. 后端执行 CLI 命令:
   node ./quartz/bootstrap-cli.mjs build --sqlite \
     --settings=settings/xm \
     -d input/xm \
     -o output/xm
   ↓
5. Quartz 引擎处理:
   - 读取 Markdown 源文件
   - 解析 Frontmatter
   - 应用插件转换
   - 生成静态 HTML
   - 更新 SQLite 缓存 (.quartz-cache.db)
   ↓
6. 输出到 output/xm/
```

### 静态文件服务流程

```
浏览器请求 /xm/index.html
   ↓
后端提取 domain=xm
   ↓
映射到文件系统: output/xm/index.html
   ↓
返回文件内容（带压缩和缓存头）
```

### contentIndex.json 数据流

`contentIndex.json` 是图谱渲染的核心数据源，存储每个页面的链接关系：

```
1. 解析阶段 (CrawlLinks Plugin)
   Markdown/HTML AST
   ↓
   ├─ 正文链接收集: [[目标]] → sourcedLinks.push({target, source: {type:'content'}})
   └─ Frontmatter链接收集: project: "[[目标]]" → sourcedLinks.push({target, source: {type:'frontmatter', field}})
   ↓
   file.data.sourcedLinks = [...]  // 注入到 vfile 数据

2. 生成阶段 (ContentIndex Emitter)
   emit() / partialEmit() 函数
   ↓
   遍历所有 processed files
   ↓
   构建 ContentDetails 对象:
   {
     slug, title, links, tags,
     sourcedLinks: file.data.sourcedLinks ?? []  // 关键字段
   }
   ↓
   输出到 static/contentIndex.json

3. 消费阶段 (Graph Component)
   浏览器加载图谱
   ↓
   fetchData = fetch('/static/contentIndex.json')
   ↓
   构建 LinkData:
   {
     source: NodeData,
     target: NodeData,
     sourceField?: string  // 'content' | frontmatter字段名
   }
```

**关键类型定义**:
```typescript
// sourcedLinks 类型 (links.ts)
interface SourcedLink {
  target: SimpleSlug
  source: { type: 'content' } | { type: 'frontmatter'; field: string }
}

// contentIndex.json 单条记录类型 (contentIndex.tsx)
interface ContentDetails {
  slug: FullSlug
  links: SimpleSlug[]
  sourcedLinks?: SourcedLink[]  // 图谱边标签来源
  // ...其他字段
}
```

**注意事项**:
- `sourcedLinks` 字段在 `emit()` 和 `partialEmit()` 中都需要正确传递
- 图谱渲染时通过 `sourceField` 区分链接来源（正文 vs YAML frontmatter）

## 代码规范与开发指南

### 前端（Client）规范

1. **组件命名**: PascalCase，如 `Explorer2.tsx`, `Search2.tsx`
2. **工具函数**: camelCase，如 `fileTrie.ts`, `graphdb.ts`
3. **样式文件**: 组件同名 `.scss`，如 `explorer2.scss`
4. **类型定义**: 使用 TypeScript 严格类型，定义在 `types.ts` 或 `cfg.ts`

### 后端（Server）规范

1. **Go 版本**: 1.24.4+
2. **代码组织**: 按功能分文件（`api.go`, `static.go`, `domain_config.go` 等）
3. **错误处理**: 使用 `log.Printf` 记录，返回 JSON 错误响应
4. **并发安全**: 使用 `sync.Mutex` 保护共享状态（如 `taskRunning`）

### 配置文件修改注意事项

**修改 `server/config.json` 时**:
- 路径必须使用绝对路径或使用双反斜杠（Windows）
- 修改后需要重启服务生效
- `work_dir` 必须指向 `client` 目录

**修改业务域配置时**:
- 通过 API 修改会立即生效
- 手动修改 `domain_config.json` 后需重新触发构建
- `config.json` 由后端自动生成，**不要手动编辑**

## 常见问题与排查

### 构建失败排查

1. 检查 `logs/service.log` 查看服务日志
2. 检查 `logs/tasks/task-{timestamp}.log` 查看具体构建日志
3. 确认 Node.js 版本 >= 22
4. 确认 `client/node_modules` 已安装

### 静态文件 404

1. 确认业务域已构建（`output/{domain}/` 目录存在）
2. 确认 URL 带斜杠（`/xm/` 而非 `/xm`）
3. 检查后端日志中的文件路径映射

### 认证问题

1. 确认 URL 参数 `user` 和 `pwd` 正确
2. 检查 `config.json` 中的 `auth` 配置
3. 清除浏览器 Cookie 后重试

## 安全注意事项

1. **生产环境必须修改默认密码**: `config.json` 中的 `auth.pwd`
2. **Cookie 安全**: 当前 `HttpOnly=false`，生产环境建议使用 HTTPS
3. **路径遍历防护**: 静态文件服务使用 `filepath.Clean` 清理路径
4. **参数白名单**: API 端点校验只允许特定参数名

## 扩展开发

### 添加新的后端 API 端点

在 `main.go` 的 `main()` 函数中注册处理器：

```go
http.Handle("/api/new-endpoint", compressionMiddleware(http.HandlerFunc(newHandler)))
```

### 添加新的 Quartz 插件

1. 在 `client/quartz/plugins/transformers/` 或 `emitters/` 创建插件文件
2. 在 `client/quartz/plugins/index.ts` 导出
3. 在 `quartz.config.ts` 的 `plugins` 数组中启用

### 添加新的业务域字段

1. 修改 `server/domain_config.go` 中的 `DomainConfig` 结构体
2. 修改 `generateQuartzConfig()` 方法转换新字段
3. 重新构建后端服务

## 参考文档

- [Quartz 官方文档](https://quartz.jzhao.xyz)
- [API文档.md](./API文档.md) - 完整 API 文档
- [架构联动说明.md](./架构联动说明.md) - 架构详细说明
- [DomainConfig功能文档.md](./DomainConfig功能文档.md) - 业务域配置文档
