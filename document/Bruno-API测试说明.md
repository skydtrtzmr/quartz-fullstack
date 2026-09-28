# Bruno API 测试说明

## 什么是 Bruno

Bruno 是一款开源的 API 测试客户端（类似 Postman/Insomnia），使用纯文本格式（`.bru`）存储接口请求，可直接通过 Git 管理。

## 导入方式

1. 下载并安装 [Bruno](https://www.usebruno.com/)
2. 打开 Bruno → 点击 **Open Collection**
3. 选择项目根目录下的 `bruno-api-test/` 文件夹
4. 所有接口请求会自动加载

## 集合结构

| 文件 | 接口 | 说明 |
|------|------|------|
| `列出所有业务域.bru` | `GET /api/domains` | 列出所有业务域（v5 元信息，含 `config_format` / `warnings`） |
| `创建业务域.bru` | `POST /api/domain/{domain}` | 用 `template_file` 模板建域，body 白名单 `page_title` |
| `修改业务域配置.bru` | `PUT /api/domain/{domain}` | 白名单补丁：`page_title` / `aggregation.{folder_depth,default,folders}` |
| `文件夹配置-读取.bru` | `GET /api/domain/{domain}/_folder/{path...}` | 读目录在两个链段（聚合/属性显示）的配置 + 继承提示 |
| `文件夹配置-设置.bru` | `PUT /api/domain/{domain}/_folder/{path...}` | 整体下发双区块；区块缺省=不动，`fields: []` = 恢复继承 |
| `文件夹配置-恢复继承.bru` | `DELETE /api/domain/{domain}/_folder/{path...}` | 两个链段里该目录条目都删 |
| `删除业务域.bru` | `DELETE /api/domain/{domain}` | 删除业务域（body 可选 `delete_input` / `delete_output`，默认 false） |
| `触发指定业务域构建.bru` | `POST /api/domain/{domain}/build` | 触发构建（`reset=true` 为全量） |
| `获取业务域构建状态.bru` | `GET /api/domain/{domain}/status` | 查询构建任务状态 |
| `获取业务域日志.bru` | `GET /api/domain/{domain}/logs` | 获取构建日志 |
| `获取正在进行的任务.bru` | `GET /api/tasks` | 获取运行中的任务列表 |
| `清理output垃圾-预览.bru` | `GET /api/output/cleanup` | 预览会被清理的孤立目录 |
| `清理output垃圾-确认删除.bru` | `POST /api/output/cleanup?confirm=true` | 确认删除 |
| `访问业务域.bru` / `前端界面.bru` | `GET /{domain}/` | 静态站点访问（带认证参数） |

## 环境变量

当前集合中的请求默认使用以下值：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| Base URL | `http://127.0.0.1:8766` | 后端服务地址 |
| `user` | `admin` | 认证用户名 |
| `pwd` | `password123` | 认证密码 |

如需修改，请在 Bruno 中创建环境变量并替换请求中的硬编码值（`environments/` 下已有 `本地8766.bru`、`公司测试.bru`）。

## v5 请求体约定

v5 的域配置只有一份 `settings/{domain}/quartz.config.yaml`，服务端**只按白名单碰该碰的字段**，其余内容（注释、锚点别名、插件清单、layout 段）原样保留。

| 接口 | 白名单字段 |
|------|-----------|
| `POST /api/domain/{domain}` | `page_title` |
| `PUT /api/domain/{domain}` | `page_title`、`aggregation.folder_depth`、`aggregation.default`、`aggregation.folders` |

- 白名单外的键**不报错**，会被忽略并在响应的 `warnings` 里逐条列出 —— 写错字段时不会静默丢配置。
- `baseUrl` 由服务端按 `{base_url}/{domain}` 注入，请求里传了也不作数。
- `aggregation.folders` 里值为 `[]` 表示**删除该目录的覆盖**（恢复逐层继承）；目录级只有「配了字段」与「未配置」两态。

## 推荐测试顺序（改配置 → 重建 → 看效果）

1. **看全貌**：`列出所有业务域.bru` —— 确认每个域都解析正常（`page_title` / `aggregation` / `warnings`）。
2. **看单域**：`GET /api/domain/{domain}`（Bruno 里没有单独文件，改「列出」的 URL 或新增一个）——
   核对 `aggregation.folders` 与你手改的 YAML 是否一致。
3. **手改配置（可选）**：直接编辑 `settings/{domain}/quartz.config.yaml` 并保存。
   服务端**每次请求都重新读盘**，改配置不需要重启服务。
4. **走 API 改配置**：`修改业务域配置.bru` —— body 只写要改的键；响应的 `domain_info` 就是改后结果，
   `warnings` 会列出被忽略的非白名单键。改完回到第 2 步核对。
5. **重建**：`触发指定业务域构建.bru`，URL 加 `&reset=true`（配置变更不会被增量识别，必须全量）。
   响应里的 `command` 就是实际执行的命令。
6. **看进度**：`获取业务域构建状态.bru` 轮询到 `"status": "idle"`；
   失败就用 `获取业务域日志.bru` 看完整输出（含错误栈）。
7. **看效果**：浏览器 `http://127.0.0.1:9766/{domain}/?user=admin&pwd=password123`，
   配置类改动记得**硬刷新**（页面里内嵌的是构建期参数）。
8. **收尾**：`删除业务域.bru`（body 传 `{"delete_input":true,"delete_output":true}` 连输入/输出一起删）、
   `清理output垃圾-预览.bru` / `清理output垃圾-确认删除.bru`。

> 改了 `server/config.json`（端口、`template_file`、`cache_dir`、构建命令）**必须重启服务**；
> 改 `settings/` 下的域配置则**不需要**重启（每次请求实时读盘）。

## 注意

- 集合里的测试域（`demo-new`、`test1` 等）会真实改动本地 `settings/`，跑完请顺手清理。
- 改了配置后必须带 `reset=true` 全量构建，否则页面内嵌的图谱参数不会更新。
- 服务端必须**在 `server/` 目录下启动**：`config.json` 与 `logs/` 都是相对工作目录解析的。
