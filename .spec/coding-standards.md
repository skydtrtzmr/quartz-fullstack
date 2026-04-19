# Quartz 项目代码规范

## 1. 配置文件管理规范

### 1.1 目录结构
```
settings/{domain}/          # 业务域配置目录
├── quartz.config.json      # Quartz 运行时配置（Server 管理）
│   ├── pageTitle          # 显示名
│   ├── baseUrl            # 由服务器自动生成
│   └── graph              # 图谱聚合配置
│
└── quartz.layout.json      # 布局覆盖配置（Server 管理）
    ├── backlinks          # 反向链接配置
    └── aggregation         # 聚合分组配置
```

### 1.2 配置层级（优先级从低到高）
1. `quartz.config.ts` / `quartz.layout.ts` - 代码默认配置
2. `quartz.config.json` / `quartz.layout.json` - Server 管理的域配置
3. 运行时 URL 参数 - 临时覆盖

### 1.3 baseUrl 生成规则
- **不可用户自定义**：用户在 API 请求中传入的 `baseUrl` 会被忽略
- **生成方式**：`{server config.json base_url}/{domain}`
- 例如：服务器 base_url = `http://127.0.0.1:8766`，domain = `xm`，则 baseUrl = `http://127.0.0.1:8766/xm`

### 1.4 示例文件存放
- 位置：`server/examples/settings/`
- 包含：`quartz.config.json`、`quartz.layout.json` 示例
- 用途：用户复制创建新 domain

## 2. API 设计规范

### 2.1 参数验证
- **必须验证参数白名单**：所有请求参数必须在配置文件定义的允许列表内
- **白名单来源**：`cfg.Auth.UserParam`、`cfg.Auth.PwdParam`、`cfg.OptionalParam`
- **非法参数响应**：返回 400 Bad Request，明确告知非法参数和允许参数列表

```go
// 正确的参数验证流程
func handler(w http.ResponseWriter, r *http.Request) {
    // 1. 先验证参数白名单
    if _, ok := validateParams(w, r); !ok {
        return
    }
    // 2. 再验证身份
    if !validateAuth(w, r) {
        return
    }
    // 3. 执行业务逻辑
}
```

### 2.2 响应格式
```json
{
  "status": "Accepted|Bad Request|Unauthorized|Busy",
  "message": "人类可读的简短描述",
  "command": "完整执行的命令（调试用）",
  "description": "中文描述（给前端展示）"
}
```

### 2.3 构建命令回显
- API 响应必须包含完整构建命令
- 任务日志必须清晰展示：
  - 任务ID、业务域、重置标志
  - Input/Output/Settings 路径
  - 完整执行的命令

## 3. 图谱渲染规范

### 3.1 虚拟节点处理
- **定义**：被引用但不存在的页面（非 tag）
- **动态计算**：像 tags 一样从现有文件 links 中提取，不依赖 virtualNodeIndex.json
- **链接方向**：实体节点 → 虚拟节点（虚拟节点永远是被指向的目标）

```typescript
// 正确的虚拟节点计算逻辑
const virtualNodes = new Set<SimpleSlug>()
const allExistingSlugs = new Set(data.keys())
const allTags = new Set(/* ... */)

for (const link of outgoing) {
  if (!allExistingSlugs.has(link) && !allTags.has(link) && !link.startsWith("tags/")) {
    virtualNodes.add(link)  // 作为被指向的目标
  }
}
```

### 3.2 边去重
- 必须使用 `"source->target"` 作为 key 去重
- 避免 BFS 遍历导致的重复链接

### 3.3 箭头渲染
- 可配置：`showArrows?: boolean`（默认 true）
- 箭头位置：在 target 节点边缘，避免重叠
- 短线段处理：长度不足时不显示箭头

## 4. 构建系统规范

### 4.1 Reset 参数传递
- API 必须正确读取并传递 `reset` 参数到构建任务
- 禁止在 handler 中硬编码 `false`

```go
// 错误：硬编码 false
go runBuildAsyncTask(false, domain)

// 正确：读取请求参数
enableReset := r.URL.Query().Get(cfg.OptionalParam) == "true"
go runBuildAsyncTask(enableReset, domain)
```

### 4.2 任务日志格式
```
╔══════════════════════════════════════════════════════════════╗
║                    构建任务启动                              ║
╠══════════════════════════════════════════════════════════════╣
║ 任务ID:     {taskID}
║ 业务域:     {domain}
║ 重置标志:   {resetFlag}
║ Settings:   {settingsPath}
║ Input:      {inputPath}
║ Output:     {outputPath}
╠══════════════════════════════════════════════════════════════╣
║ 完整命令:                                                   ║
║ {fullCommand}
╚══════════════════════════════════════════════════════════════╝
```

## 5. 代码组织规范

### 5.1 示例文件命名
- `{name}.example.{ext}` 或 `{name}_example.{ext}`
- 示例文件必须可直接复制使用

### 5.2 注释规范
- 关键逻辑必须注释原因（Why），不只是描述（What）
- 配置项必须说明：用途、默认值、谁来维护

### 5.3 错误处理
- 所有错误必须记录日志
- 对外响应不要暴露敏感内部信息
- 使用统一的状态码和错误格式

## 6. 文档同步规范

修改代码后必须同步更新：
- `.spec/` 下的任务清单（TODO.md、*-tasks.md）
- 示例配置文件（server/examples/）
- 本规范文档（如影响）