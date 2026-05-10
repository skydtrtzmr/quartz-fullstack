# Settings 目录说明

本目录存放各业务域的配置文件，每个子目录代表一个独立的业务域（domain）。

## 目录结构

```
server/examples/settings/
├── README.md              # 本说明文件
├── quartz.config.json     # Quartz 运行时配置（示例）
├── quartz.layout.json     # 布局配置（示例）
```

## 配置文件说明

### 1. quartz.config.json

**作用**：供 Quartz Client 读取的运行时配置，对应 `quartz.config.ts` 的 configuration 字段。

**管理方式**：通过 Server API 管理
- `PUT /api/domain/{domain}` - 更新配置（传入 config 字段）
- `GET /api/domain/{domain}` - 获取配置

**注意**：请勿手动修改，会被 API 调用覆盖。

### 2. quartz.layout.json

**作用**：覆盖 Quartz 布局行为（排序、聚合等）。

**支持字段**：

| 字段 | 说明 |
|------|------|
| `explorer.sort` | 文件浏览器排序配置 |
| `folderPage.sort` | 文件夹页面排序配置 |
| `backlinks.hideWhenEmpty` | 无反向链接时是否隐藏 |
| `backlinks.sort` | 反向链接排序配置 |
| **聚合配置（backlinks / graph 共用同一结构）** | |
| `{component}.aggregation.folder` | 文件夹聚合配置（depth） |
| `{component}.aggregation.fields` | 字段聚合配置（field / granularity / order） |

`backlinks.aggregation` 和 `graph.aggregation` 使用**完全相同的结构**（`AggregationConfig`），都包含 `folder` 和 `fields`，且文件夹优先于字段聚合。

## 创建新业务域

### 方式一：通过 API（推荐）

```bash
POST /api/domain/{domain}
{
  "domain_name": "myproject",
  "display_name": "我的项目"
}
```

### 方式二：手动复制

1. 复制本目录中的示例文件到 `settings/{domain}/`
2. 修改 `quartz.config.json` 和 `quartz.layout.json`
3. 调用 `POST /api/domain/{domain}/build` 触发构建
