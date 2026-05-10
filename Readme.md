# Quartz 全栈项目

包含**客户端**与**服务端**。

核心设计理念是**“前端引擎层”与“业务数据层”的解耦**：通过统一的后端调度，配合前端支持动态参数，实现一套 Quartz 代码支持无限个独立业务域的站点构建。

---

## 项目文件夹结构

| 名称 | 作用 | 主要文件 / 子目录 |
|:---|:---|:---|
| `client/` | Quartz 前端引擎，负责 Markdown 解析与静态站点生成 | `quartz/`（核心引擎代码） |
| `server/` | Go 后端服务，负责接口路由与构建任务调度 | `config.json`、Go 源码等 |
| `input/` | 业务 Markdown 源文件根目录，按业务域分子目录 | 各域 Markdown 文件 |
| `settings/` | 各业务域的覆写配置 | `quartz.config.json`、`quartz.layout.json` |
| `output/` | 构建产物根目录，按业务域分子目录 | `public/`（静态 HTML） |
| `scripts/` | 辅助脚本（如项目打包） | Python / Shell 脚本等 |
| `bruno-api-test/` | API 测试集合 | `*.bru` 测试用例 |
| `document/` | 项目文档说明 | `*.md`、`*.json` 示例与说明 |
| `logs/` | 运行日志目录 | `tasks/` |

### 目录与参数映射关系

| 逻辑概念 | 服务端配置 (`config.json`) | 默认路径 | 作用概述 |
|:---|:---|:---|:---|
| **输入源** | `input_dir` | `./input` | 存放所有 Markdown 原始文件，按业务域分子目录 |
| **输出池** | `output_dir` | `./output` | 存放最终编译生成的 HTML 静态网站，按业务域分子目录 |
| **动态配置** | `settings_dir` | `./settings` | 存放各业务域特定的 `quartz.config.json` 和 `quartz.layout.json` 覆写文件 |
| **图谱缓存** | （自动推导） | `<settings_dir>/<domain>/.quartz-cache.db` | 存放 SQLite 解析结果增量缓存，确保各域的增量构建互不干扰 |

### 构建调度流程

当后端 API `/api/build?domain=xm` 被触发时：

1. **获取基础路径**：后端从 `config.json` 读取 `input_dir`、`output_dir`、`settings_dir`。
2. **拼接业务域路径**：根据 `domain=xm` 拼接出对应的子目录路径。
3. **注入 CLI 执行**：在 `client` 目录下执行构建命令：
   ```bash
   node ./quartz/bootstrap-cli.mjs build \
     -d {input_dir}/xm \
     -o {output_dir}/xm/public \
     --settings {settings_dir}/xm \
     --cacheDir {output_dir}/xm/.cache \
     --sqlite
   ```
   > **注意**：`--cacheDir` 参数必须显式传入，否则 SQLite 缓存文件会默认生成在 `--settings` 指定的目录下。
4. **引擎处理**：`build.ts` 恢复增量 SQLite 缓存，`quartz.config.ts` 与 `quartz.layout.ts` 动态合并配置，编译后输出到指定目录。

### 静态资源路由

当用户访问 `http://ip:port/xm/index.html` 时：

1. Go HTTP 服务层拦截路径前缀 `/xm/`。
2. 提取 `domain=xm`，将剩余 URL 映射回本地文件系统。
3. 返回位于 `{output_dir}/xm/public/index.html` 的文件。

---

## 客户端

进入 `client` 文件夹，执行 `npm install` 安装依赖包。

## 服务端

进入 `server` 文件夹，执行构建：

```bash
go build -ldflags="-s -w" -o quartz-service.exe .
```

首次访问：
- http://127.0.0.1:8766/xm?user=admin&pwd=password123
- http://127.0.0.1:8766/testwork0?user=admin&pwd=password123