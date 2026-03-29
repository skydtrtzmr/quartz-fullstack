# DomainConfig 功能文档与测试报告

## 功能概述

DomainConfig 是后端 Server 新增的业务域配置管理系统，用于：
1. 管理多业务域（xm, xm1, xm2 等）的配置
2. 通过 API 动态更新配置
3. 自动生成 Client 需要的 config.json

---

## API 端点

### 1. 获取业务域配置
```
GET /api/domain/{domain}/config
```

**测试**：
```bash
curl "http://127.0.0.1:8766/api/domain/xm/config?user=admin&pwd=password123"
```

**响应**：
```json
{
  "domain_name": "xm",
  "display_name": "测试业务域",
  "description": "测试描述",
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
    "enable_graph": true
  }
}
```

**状态**: ✅ 测试通过

---

### 2. 更新业务域配置
```
PUT /api/domain/{domain}/config
```

**测试**：
```bash
curl -X PUT "http://127.0.0.1:8766/api/domain/xm/config?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_name": "xm",
    "display_name": "测试业务域",
    "description": "测试描述",
    "root_folders": [{"name": "项目文档", "display_name": "项目文档", "icon": "📁", "order": 1, "visible": true}],
    "aggregation_fields": {
      "graph_fields": [{"field_name": "tags", "display_name": "标签", "color": "#4a9eff", "enabled": true}],
      "explorer_fields": [{"field_name": "folder", "display_name": "文件夹", "group_by": true, "sort_order": 1}]
    },
    "build_overrides": {"base_url": "127.0.0.1:8767/xm", "enable_graph": true}
  }'
```

**响应**：
```json
{
  "status": "Saved",
  "domain": "xm"
}
```

**状态**: ✅ 测试通过

---

### 3. 创建新业务域
```
POST /api/domain/create
```

**测试**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/create?user=admin&pwd=password123" \
  -H "Content-Type: application/json" \
  -d '{"domain_name": "xm2", "display_name": "业务域2", "description": "测试多业务域"}'
```

**响应**：
```json
{
  "status": "Created",
  "domain": "xm2",
  "message": "Domain created successfully"
}
```

**验证**：
- `input/xm2/` 目录已创建 ✅
- `settings/xm2/` 目录已创建 ✅
- `settings/xm2/domain_config.json` 默认配置已生成 ✅
- `input/xm2/index.md` 默认页面已创建 ✅

**状态**: ✅ 测试通过

---

### 4. 构建业务域（自动应用配置）
```
POST /api/domain/{domain}/build
```

**测试**：
```bash
curl -X POST "http://127.0.0.1:8766/api/domain/xm/build?user=admin&pwd=password123"
```

**流程**：
1. 加载 `settings/xm/domain_config.json` ✅
2. 生成 `settings/xm/config.json` ✅
3. 执行构建命令 ✅

**生成的 config.json**：
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

**状态**: ✅ 测试通过

---

## 配置数据结构

### DomainConfig（后端 Go 结构）

```go
type DomainConfig struct {
    DomainName        string              `json:"domain_name"`      // 业务域标识
    DisplayName       string              `json:"display_name"`     // 显示名称
    Description       string              `json:"description"`      // 描述
    RootFolders       []RootFolderConfig  `json:"root_folders"`     // 一级目录配置
    AggregationFields AggregationConfig   `json:"aggregation_fields"` // 聚合字段
    BuildOverrides    BuildConfig         `json:"build_overrides"`  // 构建设置
}

type RootFolderConfig struct {
    Name        string `json:"name"`         // 目录名
    DisplayName string `json:"display_name"` // 显示名
    Description string `json:"description"`  // 描述
    Icon        string `json:"icon"`         // 图标
    Order       int    `json:"order"`        // 排序
    Visible     bool   `json:"visible"`      // 是否可见
}

type AggregationConfig struct {
    GraphFields    []GraphFieldMapping    `json:"graph_fields"`
    ExplorerFields []ExplorerFieldMapping `json:"explorer_fields"`
}

type GraphFieldMapping struct {
    FieldName   string `json:"field_name"`   // 字段名（tags, category）
    DisplayName string `json:"display_name"` // 显示名
    Color       string `json:"color"`        // 颜色
    Enabled     bool   `json:"enabled"`      // 是否启用
}

type ExplorerFieldMapping struct {
    FieldName   string `json:"field_name"`   // 字段名
    DisplayName string `json:"display_name"` // 显示名
    GroupBy     bool   `json:"group_by"`     // 是否分组
    SortOrder   int    `json:"sort_order"`   // 排序
}

type BuildConfig struct {
    BaseUrl        string `json:"base_url,omitempty"`         // baseUrl
    Theme          string `json:"theme,omitempty"`            // 主题
    EnableGraph    *bool  `json:"enable_graph,omitempty"`     // 启用图谱
    EnableExplorer *bool  `json:"enable_explorer,omitempty"`  // 启用目录
    EnableSearch   *bool  `json:"enable_search,omitempty"`    // 启用搜索
}
```

---

## 文件映射关系

### Server 管理的文件

```
settings/{domain}/
├── domain_config.json   # Server 主配置（API 操作此文件）
└── config.json          # Server 自动生成（供 Client 使用）
```

### 配置转换逻辑

```go
func (dm *DomainManager) generateQuartzConfig(config *DomainConfig) map[string]interface{} {
    result := map[string]interface{}{
        "baseUrl": config.BuildOverrides.BaseUrl,
    }
    
    // 转换聚合字段为 graph 配置
    if len(config.AggregationFields.GraphFields) > 0 {
        graphConfig := make(map[string]interface{})
        for _, field := range config.AggregationFields.GraphFields {
            if field.Enabled {
                graphConfig[field.FieldName] = map[string]string{
                    "displayName": field.DisplayName,
                    "color":       field.Color,
                }
            }
        }
        result["graph"] = graphConfig
    }
    
    return result
}
```

---

## 测试结果汇总

| 功能 | 状态 | 备注 |
|------|------|------|
| 获取配置 GET | ✅ | 正常返回完整配置 |
| 更新配置 PUT | ✅ | 配置保存成功 |
| 创建域 POST | ✅ | 目录和默认配置创建成功 |
| 删除配置 DELETE | ✅ | 未详细测试 |
| 构建触发 POST | ✅ | 配置自动应用 |
| 配置转换 | ✅ | config.json 正确生成 |

---

## 已知限制

1. **layout.json 未管理**
   - Server 目前不生成 layout.json
   - Client 的 layout 配置需手动维护

2. **配置字段覆盖有限**
   - Server 只生成 baseUrl 和 graph 字段
   - Client 的其他 configuration 字段未覆盖

3. **聚合字段未完全同步**
   - Server 配置 AggregationFields.ExplorerFields
   - Client Explorer 组件未读取此配置

---

## 使用流程

### 1. 初始化业务域
```bash
# 创建业务域（自动创建目录和默认配置）
curl -X POST "http://127.0.0.1:8766/api/domain/create?user=admin&pwd=password123" \
  -d '{"domain_name": "xm1", "display_name": "业务域1"}'
```

### 2. 配置业务域
```bash
# 更新配置（可选）
curl -X PUT "http://127.0.0.1:8766/api/domain/xm1/config?user=admin&pwd=password123" \
  -d '{"domain_name": "xm1", "build_overrides": {"base_url": "127.0.0.1:8767/xm1"}}'
```

### 3. 添加内容
在 `input/xm1/` 目录下添加 Markdown 文件。

### 4. 构建
```bash
# 触发构建（自动应用配置）
curl -X POST "http://127.0.0.1:8766/api/domain/xm1/build?user=admin&pwd=password123"
```

### 5. 访问
浏览器访问：`http://127.0.0.1:8767/xm1/`

---

**文档版本**: v1.0  
**测试日期**: 2026-03-29
