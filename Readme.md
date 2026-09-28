# Quartz 全栈项目

包含**前端引擎**与**后端服务**。

核心设计理念是**“前端引擎层”与“业务数据层”的解耦**：通过统一的后端调度，配合前端支持动态参数，实现一套 Quartz 代码支持无限个独立业务域的站点构建。

---

构建命令（v5，引擎在 `quartz5/`）：

```
cd E:\ProgramProjects\VScode_projects\quartz-fullstack\quartz5

npx quartz build -d ../input/demo-region -o ../output/demo-region-sqlite --settings ../settings/demo-region-sqlite --sqlite --cacheDir ../cache/demo-region-sqlite
```

## 项目文件夹结构

| 名称 | 作用 | 主要文件 / 子目录 |
|:---|:---|:---|
| `quartz5/` | Quartz v5 前端引擎，负责 Markdown 解析与静态站点生成 | `quartz/`（核心引擎代码）、`quartz.config.yaml`（引擎自身配置） |
| `server/` | Go 后端服务，负责接口路由、域配置读写与构建任务调度 | `config.json`、`v5config.go`、`domain_config.go` 等 |
| `input/` | 业务 Markdown 源文件根目录，按业务域分子目录 | 各域 Markdown 文件 |
| `settings/` | 各业务域的配置，**每个域一份 `quartz.config.yaml`** | `quartz.config.yaml`（`_v4-backup/` 为 v4 留档） |
| `output/` | 构建产物根目录，按业务域分子目录 | `index.html`、`static/` 等（直接落在域目录下） |
| `plugins-local/` | 本地插件源码（graph-pro / explorer-pro / aggregation-pro / aggregation-page-pro 等） | `<插件>/src`、`<插件>/dist` |
| `scripts/` | 辅助脚本（如项目打包） | Python / Shell 脚本等 |
| `bruno-api-test/` | API 测试集合 | `*.bru` 测试用例 |
| `document/` | 项目文档说明 | `*.md`、`*.json` 示例与说明 |
| `server/logs/` | 服务与构建任务日志 | `service.log`、`tasks/` |

### 目录与参数映射关系

| 逻辑概念 | 服务端配置 (`config.json`) | 默认值 / 推导 | 作用概述 |
|:---|:---|:---|:---|
| **输入源** | `input_dir` | `./input` | 存放所有 Markdown 原始文件，按业务域分子目录 |
| **输出池** | `output_dir` | `./output` | 存放最终编译生成的静态站点，按业务域分子目录 |
| **动态配置** | `settings_dir` | `./settings` | 每个业务域一份 `quartz.config.yaml` |
| **建域模板** | `template_file` | 指向某个 v5 域配置 | 建域时整棵配置继承它，只改写 `pageTitle` / `baseUrl` |
| **构建缓存** | `cache_dir` | 项目根 `cache/{domain}/` | 每个域一份独立缓存（多域并发构建互不干扰），db = `cache/{domain}/.quartz-cache.db`；想换成 `settings/{domain}/` 只改 `cache_dir` 一项 |

### 构建调度流程

当 `POST /api/domain/{domain}/build` 被触发时：

1. **获取基础路径**：后端从 `config.json` 读取 `input_dir`、`output_dir`、`settings_dir`、`cache_dir`。
2. **拼接业务域路径**：按 `domain` 拼出输入/输出/配置/缓存目录。
3. **注入 CLI 执行**：在 `quartz5` 目录下执行（实际命令，`reset=true` 时追加 `--reset`）：
   ```bash
   node ./quartz/bootstrap-cli.mjs build --sqlite \
     --settings {settings_dir}/{domain} \
     -d {input_dir}/{domain} \
     -o {output_dir}/{domain} \
     --cacheDir {cache_dir}/{domain}
   ```
   > `--cacheDir` 必须显式传入：服务端支持多域并发构建，共用一份缓存会互相踩。
4. **引擎处理**：`bootstrap-cli` 读取 `quartz.config.yaml`，编译后输出到指定目录。

> **重要**：增量构建只检测 `input/` 下 Markdown 的变更。改了 `quartz.config.yaml`（或域内的聚合/图谱配置）不会被识别为需要重建页面的原因，**必须带 `reset=true` 触发全量构建**，否则页面中内嵌的配置（如图谱参数）不会更新。

### 静态资源路由

当用户访问 `http://ip:port/{domain}/index.html` 时：

1. Go HTTP 服务层拦截路径前缀 `/{domain}/`。
2. 提取 `domain`，将剩余 URL 映射回本地文件系统。
3. 返回 `{output_dir}/{domain}/index.html`。

---

## 前端引擎

进入 `quartz5` 文件夹，执行 `npm install` 安装依赖包；本地插件改完记得在 `plugins-local/<插件>` 下 `npm run build`，再对站点做一次全量（`reset=true`）构建。

## 服务端

进入 `server` 文件夹，执行构建：

```bash
go build -ldflags="-s -w" -o quartz-service.exe .
```

单元测试：

```bash
go test ./...
```

### 域配置读写（v5）

`settings/{domain}/quartz.config.yaml` 由 `server/v5config.go` 以**节点级**方式读写：
写接口只替换白名单字段对应的节点，注释、锚点别名、键序、插件清单与 `layout:` 段全部保留。
白名单之外的键不报错，但会在响应 `warnings` 里逐条列出。

详见 `document/API文档.md`（接口契约）与 `document/Settings目录说明.md`（配置模型）。

### 打包

```
python .\scripts\pack-project.py
```

首次访问：
http://127.0.0.1:8766/demo-core?user=admin&pwd=password123
http://127.0.0.1:8766/demo-region?user=admin&pwd=password123
http://127.0.0.1:9766/demo-bench1?user=admin&pwd=password123

### 注意事项

1. 域配置是**手工维护的 YAML**（注释很有价值），优先通过 API 改；API 只按白名单动字段，不会重写整份文件。
2. 改了配置后记得用 `reset=true` 全量重建。
3. 注意确保业务域根目录有 `index.md` 文件。
