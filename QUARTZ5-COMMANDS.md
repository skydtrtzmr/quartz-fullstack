# Quartz v5 常用命令手册

> 环境：Windows PowerShell，项目根目录 `e:\ProgramProjects\VScode_projects\quartz-fullstack`
> 前提：Node >= 22（quartz5 要求）

## 目录速查

```
quartz-fullstack/
├── quartz5/                  # v5 基座（配置、构建入口）
├── plugins-local/            # 本地插件源码（submodule，fork 自社区仓库）
│   └── reader-mode-pro/
├── input/                    # 内容源（demo-bench = 2 万文件压测集）
├── output/                   # 构建输出
├── client/                   # 旧 v4（冻结，只修致命 bug）
└── server/                   # Go server
```

---

## 一、本地插件开发（plugins-local/xxx）

### 1. 首次获取/新增插件

> **★ 铁律（2026-09-19 用户确立）**：所有本地插件一律 GitHub fork + submodule，
> 没有例外——不因"改动小"而复制骨架成普通目录。
> **改任何插件前，先等用户建好 GitHub 仓库**，AI 不得擅自启动插件改造。
> 增量改动一律提交并推送到 **dev 分支**（main 保持镜像上游干净状态）。

```powershell
# 已有 submodule 的插件：主仓库拉取后初始化（换电脑必跑）
git submodule update --init --recursive

# 新增一个 fork 插件（用户已在 GitHub fork 好仓库后）
cd e:\ProgramProjects\VScode_projects\quartz-fullstack
git submodule add -b dev https://github.com/<你的账号>/<fork仓库> plugins-local/<插件名>

# 给 fork 配置上游（一次性，之后可 merge 社区更新）
cd plugins-local/<插件名>
git remote add upstream https://github.com/quartz-community/<原仓库>.git

# 插件改动流程：dev 分支提交 → push origin dev → npm run build → 重建站点
```

### 2. 安装插件依赖（改了 package.json 后跑）

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\plugins-local\reader-mode-pro
npm install
```

### 3. 构建插件（每次改 src/ 后跑）

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\plugins-local\reader-mode-pro
npm run build        # tsup 构建，产物在 dist/
npm run typecheck    # 可选：类型检查
npm run dev          # 可选：watch 模式，保存即重建
```

> **注意**：`npx quartz plugin add` 内部的构建步骤在 Windows symlink 路径下不可靠，
> 一律用上面的手动 `npm install + npm run build`，构建产物 dist/ 会被 quartz 直接使用。

### 4. 把插件注册进 quartz5（每个插件一次性）

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\quartz5
npx quartz plugin add ../plugins-local/reader-mode-pro
```

- 创建 `.quartz/plugins/reader-mode-pro` → symlink 指向源码目录，**改源码立即生效**（改完记得手动 `npm run build`）
- 同时更新 `quartz.lock.json` 和 `quartz.config.yaml`
- 卸载：`npx quartz plugin remove reader-mode-pro`
- 查看已装：`npx quartz plugin list`

### 5. 同步社区上游更新（需要时）

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\plugins-local\reader-mode-pro
git fetch upstream
git merge upstream/main      # 在 dev 分支上合并，解决冲突后
npm install && npm run build # 依赖有变时重装重建
git push                      # 推回自己的 fork
```

---

## 二、构建 quartz5

### 基本构建（指定 input/output）

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\quartz5

# 小输入快速验证（官方文档集，~111 文件，15 秒）
npx quartz build -d docs -o ../output/rm-test

# 压测集（2 万文件，约 3 分钟）
npx quartz build -d ../input/demo-bench -o ../output/demo-bench5

# 完整参数
npx quartz build `
  -d ../input/demo-bench `
  -o ../output/demo-bench5 `
  --concurrency 4 `           # 解析线程数（默认按 CPU 核数）
  -v                          # verbose，打印每个插件/文件的处理日志
```

### 开发热重建（watch + 本地服务器）

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\quartz5
npx quartz build -d docs -o ../output/rm-test --serve --port 8080
# 修改 docs/ 内容自动重建；改插件 src 后需手动 npm run build 再触发页面刷新
```

### 构建产物结构

```
output/<name>/
├── index.html                # 首页（folder 页）
├── <目录>/<页面>.html        # 内容页
├── component-*.css           # 各组件样式（含插件注入的）
├── static/                   # 静态资源
├── tags/                     # 标签页
└── 404.html
```

---

## 三、查看构建后的网站

### 方式 A：Go server（默认，生产链路）★ 后续统一用这个

```powershell
# server 常驻运行中（监听 0.0.0.0:9766），产物放对位置即可直接访问
# v5 产物构建到 output/{domain}/（与 Go server 路由物理对位）：
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\quartz5
npx quartz build -d ../input/demo-bench -o ../output/demo-bench

# 浏览器打开（带认证参数，首次访问会设置 cookie）：
# http://127.0.0.1:9766/demo-bench/?user=admin&pwd=password123
```

- Go server 自带静态站点适配：domain 前缀剥离、无扩展名 `.html` 回退、目录 index.html、尾斜杠 301
- **产物兼容性已验证（2026-09-19）**：v5 产物（含全部核心补丁）在 Go server 上全链路正常
- 注意：Go server 的 `config.json` 构建命令目前仍指向 v4 client——通过 API 触发的构建还是 v4；手动构建 v5 产物放对目录即可被 serve

### 方式 B：quartz 内置 serve（插件开发快速迭代用）

小输入 + 热重建（改 quartz5 源码/配置自动重建）：

```powershell
cd e:\ProgramProjects\VScode_projects\quartz-fullstack\quartz5
npx quartz build -d docs -o ../output/rm-test --serve --port 8080
# 浏览器打开 http://localhost:8080
```

带 baseUrl 子路径时（模拟生产 URL 结构）：

```powershell
npx quartz build -d docs -o ../output/rm-test --serve --port 8080 --baseDir demo-bench
# 浏览器打开 http://localhost:8080/demo-bench/   ← 必须带前缀（含尾斜杠）
```

三条纪律：
1. `--baseDir` 必须与 baseUrl 里的子路径一致
2. 入口必须是带前缀的 URL（站内链接是相对路径，从根 `/` 进入会解析错位）
3. 根路径 `/` 返回 404 属预期（guard 拦截）
依赖 v5 核心补丁 #3（renderPage.tsx），详见 V5-BUGS.md BUG-V5-005。

> ~~python -m http.server~~ **不采用**：缺无扩展名 `.html` 回退（Go server/nginx try_files/GitHub Pages 都有），站内链接会 404。预览一律走 Go server 或 quartz serve。

---

## 四、配置文件

| 文件 | 作用 |
|------|------|
| `quartz5/quartz.config.yaml` | 主配置：主题色(oceanColors)、locale(zh-CN)、插件清单、layout 位置 |
| `quartz5/quartz.lock.json` | 插件版本锁定（勿手改，由 plugin 命令维护） |
| `quartz5/.quartz/plugins/` | 已安装插件（社区=实体目录，本地=symlink） |

改 YAML 后直接重新 build 即可生效，无需其他步骤。

---

## 五、常见问题

| 症状 | 原因与解决 |
|------|-----------|
| `Found 0 input files` | glob 受仓库 `.gitignore` 的 `/input` 影响已修（glob.ts `gitignore: false`）；若复现，检查该补丁是否被 v5 升级覆盖 |
| `plugin add` 报 build failed | Windows symlink 下安装器内 npm 不可靠；手动到 `plugins-local/<插件>` 跑 `npm install && npm run build` 即可 |
| 插件改了没生效 | 忘了 `npm run build`（symlink 只同步源码目录，dist 需手动构建） |
| `normalizeHastElement` 导入错误 | 根目录 `@quartz-community/utils` 版本漂移；`npm install @quartz-community/utils@^1.0.0` |
| 输出页面按钮重复 | YAML 里新旧两个同类插件同时 enabled；把社区版改 `enabled: false` |
| **插件组件不在同一行（掉出工具组）** | `plugin add` 自动追加的 YAML 条目缺 `group: toolbar`；手动补上该字段 |
| **插件 CSS 规则被主样式覆盖** | base.scss 竞争规则带 ID 选择器（如 `.page>#quartz-body .sidebar` 特异性 (1,2,0)），插件侧栏规则必须写成 `:root[reader-mode=on] #quartz-body .sidebar.left` (1,4,0) 才能赢；写插件 CSS 前先查 base.scss 对应选择器的层级 |
| 搜索结果链接/预览 404，或图谱/explorer 运行时请求 404 | YAML 的 `baseUrl` 子路径必须与 Go server 的 domain 目录名一致（`body[data-basepath]` 来源于它）；不同 domain 需各自一份 YAML（per-domain YAML 方案见 V5-BUGS.md BUG-V5-006）。临时办法：构建前把 `baseUrl` 改成目标 domain 再 build |
| 构建报 `[safe-delete] trash 操作失败` | 输出目录被占用（http.server / 编辑器 / 资源管理器）；关掉占用进程后重试，或直接手动删输出目录 |
| 构建报 `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]` | 一次性删除文件数超阈值被拦（如整个 output/demo-bench 是 2 万文件）；绕过法：先 `mv output/demo-bench output/demo-bench-prev-<日期>` 再构建 |
| **`--serve` 后再构建异常/页面空白/文件变少** | 旧的 serve 进程没退干净（Ctrl+C 不彻底或终端被直接关闭），它占着端口且其 watcher 会与新构建赛跑互删文件。处理：`netstat -ano \| findstr :8080` 找 PID → `Stop-Process -Id <PID> -Force` → 重新构建。**退出 serve 必须在终端 Ctrl+C 并等提示符返回** |
| **图谱整块空白 / 页面卡在加载** | 历史上 d3、pixi 从 `cdn.jsdelivr.net` 加载，外网被代理挡住时 `Promise.all(loadScript(...))` 永不 resolve → `initGraph()` 不执行。**已本地化**（graph-pro 打包 d3/pixi），若复现先确认 `static/scripts/script-*.js` 里含 `globalThis.d3=`/`globalThis.PIXI=`，并看 DevTools Network 是否还有外部域名请求 |
| git push 报 `Failed to connect to 127.0.0.1 port 7890` | 本机 git 配了 SOCKS5 代理（`socks5://127.0.0.1:7890`）但代理没启动；启动代理后重试 push 即可（不要改 git config） |
| **页面看不到 frontmatter / 属性块空白** | `note-properties` 默认 `includeAll: false`，只显示 `includedProperties` 里列的 `description/tags/aliases`；生成数据的字段是 `type/status/priority/组织` 等 → 全部被过滤。改 `includeAll: true`（并可用 `excludedProperties` 排除不想要的键，如 `priority`）。组件位置为 `beforeBody` priority 15（标题下方） |

---

## 六、当前插件状态备忘

| 插件 | 来源 | 状态 |
|------|------|------|
| reader-mode-pro | submodule → github.com/skydtrtzmr/quartz-community_reader-mode，分支 `dev`，upstream 已配 | ✅ 可用（`::root` 修正 + 全宽阅读 + 与全局图谱浮层冲突修正 BUG-COM-003） |
| footer-pro | submodule → github.com/skydtrtzmr/quartz-community_footer，分支 `dev`，upstream 已配 | ✅ 可用（源悦科技版权页脚 + 阅读模式横排修复） |
| search-pro | submodule → github.com/skydtrtzmr/quartz-community_search，分支 `dev`，upstream 已配 | ✅ 可用（社区版搜索 + 结果统计条 + 加载更多分页，默认 10/10） |
| content-index-pro | submodule → github.com/skydtrtzmr/quartz-community_content-index，分支 `dev`，upstream 已配 | ✅ 可用（contentIndex.json 保留每页 frontmatter；2 万文件集 8.88MB → 13.16MB） |
| explorer-pro | submodule → github.com/skydtrtzmr/quartz-community_explorer，分支 `dev`，upstream 已配 | ✅ 可用（v4 Explorer2 扁平化+虚拟滚动引擎整体移植；排序含 frontmatter 字段；`hideFiles` 只显示文件夹；与上游已无实质关联，仅保留仓库血统） |
| graph-pro | submodule → github.com/skydtrtzmr/quartz-community_graph，分支 `dev`，upstream 已配 | ✅ 可用（**v4 交互层已接入**：全局 region 大区模式 + 局部目录聚合 + 数字徽标；`category: [component, emitter]` + `Graph` 组件 right/priority 10；d3@7/pixi.js@8/@tweenjs/tween.js 全部本地打包，**零 CDN**；emitter 产出 `graph/local/**` + `graph/global/graphGlobal.json`） |
| content-meta-pro | submodule → github.com/skydtrtzmr/quartz-community_content-meta，分支 `dev`，upstream 已配 | ⬜ 占位（零改动，未注册进 YAML，避免与社区版组件重复渲染） |
| 社区 reader-mode / footer / content-index / search / explorer | quartz-community | 已禁用（被对应的 pro 插件替代） |
| 社区 graph | quartz-community | 已禁用（被 graph-pro 替代；`enabled: false`，避免同名 `Graph` 组件重复注册） |

> **graph-pro 输出协议（第二步交互层与 per-domain 注入都要对齐，勿改）**：
> - 局部图谱：`graph/local/{djb2(slug)[0:2]}/{djb2(slug)[2:4]}/{slug}.json`（每页一个，`djb2Hash` 与运行时读取端逐字符一致，单测 `test/graphLocal.test.ts` 覆盖）
> - 全局图谱：`graph/global/graphGlobal.json`（单文件，含首屏 + 展开所需全部数据）
> - **emitter 顺序必须 > content-index-pro（50）**：graph-pro 用 `order: 55`
> - YAML `options` 三段：`graph.{precomputeLocal,localDepth}`、`localGraph`、`globalGraph`（键名对齐 v4 `settings/<domain>/quartz.{config,layout}.json` 的 `graph` 段）

> **本地插件命名**：npm `name` 与 `quartz.name` 均改为 `xxx-pro`、`defaultEnabled: false`（由 YAML 显式启用）；
> `plugin add` 追加的条目 `enabled` 会跟着 `defaultEnabled`，且可能缺 `layout`/`group`——每次 `plugin add` 后手工核对 YAML 条目（见 V5-BUGS.md BUG-V5-004）。

---

## 七、核心补丁清单（升级上游 v5 时逐一核对，勿被覆盖）

| # | 文件 | 补丁内容 | 原因 |
|---|------|---------|------|
| 1 | `quartz5/quartz/util/glob.ts` | globby `gitignore: false` | 否则受仓库根 `.gitignore` 的 `/input` 影响，报 `Found 0 input files` |
| 2 | `quartz5/quartz/styles/variables.scss` | `$topSpacing: 6rem → 2rem` | 页面顶部留白过大 |
| 3 | `quartz5/quartz/components/renderPage.tsx` | serve 模式仅在 `(serve && !baseDir) \|\| !baseUrl` 时清空 basePath | 否则 `--baseDir` 子路径下资源 404 |
| 4 | `quartz5/quartz/util/ctx.ts` | `Argv` 补 `baseDir?: string` | serve/构建参数类型补全 |
| 5 | `quartz5/quartz/components/Head.tsx` | **删除 `<link rel="preconnect" href="https://cdnjs.cloudflare.com">`**（原第 60 行） | 站点零外链（2026-09-20 加入） |
| 6 | `quartz5/quartz/plugins/loader/config-loader.ts` + `quartz5/quartz/cli/args.js` | 新增 `--settings`：可指定**任意路径**的配置文件（传目录则取其中 `quartz.config.yaml`，传文件则直接用），**整份取代**默认主配置（configuration / plugins / layout 都从它读）；路径非法或缺省则告警并回退默认（不中断构建）。另在 `readPluginsJson()` 加解析容错：**仅当配置来自 `--settings` 且解析失败**时告警并回退默认主配置，**主配置自身损坏仍抛错**（不静默） | 让"每个业务域一份 `quartz.config.yaml`"可落地；Go server 构建时已在传 `--settings=<settings/<domain>>`（2026-09-21 加入） |

> **`--settings` 用法**
> ```powershell
> npx quartz build -d ../input/demo-region -o ../output/demo-region --settings ../settings/demo-region
> npx quartz build -d ../input/demo-region -o ../output/demo-region --settings ../settings/demo-region/quartz.config.yaml
> ```
> 配置在**导入期**加载（`quartz5/quartz.ts:3`），早于 yargs 解析，因此参数由 `resolveConfigPath()` 直接读 `process.argv`（与 v4 的 `quartz.layout.ts:41-59` 同款做法）；`--settings=<path>` 与 `--settings <path>` 都支持。
> ⚠️ 本次只打通"指定任意配置文件"；域 YAML 里的 `aggregation` 段（文件夹粒度聚合规则）**尚未消费**（graph-pro 解析留待后续）。
>
> **"换另一套 YAML 是否真的生效"已实测（2026-09-21，一次性验证，临时脚本未保留）**
> 做法：把主 YAML 复刻到临时目录、只改两处标记字段，用同一份 3 篇 md 的临时内容跑 5 次真实构建对拍。
>
> | 构建 | 命令形态 | 产物 | 日志 |
> |------|---------|------|------|
> | A | `--settings <目录>` | 5/5 页含标记、0 页含原值 | `[settings] 使用配置：<alt yaml>` |
> | B | 不传参（对照） | 5/5 页含原值、0 页含标记 | 无 `[settings]` 行 |
> | C | `--settings=<文件>` | 同 A | 同 A |
> | D | 坏路径 | 回退 → 全为原值 | `[settings] --settings 指向的路径不存在：…，回退默认配置` |
> | E | 坏 YAML | 回退 → 全为原值 | `使用配置：<path>` + `解析失败（Flow sequence … line 3）` |
>
> A/B 的 `index.html` 行数相同、**逐行仅 1 行不同**（即同时含 `<title>` 与 `og:site_name` 的那行）；5 次构建退出码全为 0。
>
> **想"一眼看出用的哪份配置"**：`configuration.pageTitleSuffix` 会拼进每页 `<title>`（`quartz5/quartz/components/Head.tsx:15-17`）；`configuration.pageTitle` **不进 `<title>`**，只进每页 `<meta name="og:site_name">`（`Head.tsx:63`）→ 同时打这两个字段最直观。

## 八、外链审计现状（2026-09-20 核对）

| 依赖 | 之前 | 现在 |
|------|------|------|
| d3@7 / pixi.js@8（图谱） | `cdn.jsdelivr.net`，运行时 `loadScript` + `Promise.all` | ✅ 由 graph-pro 打包进组件脚本（挂 `globalThis.d3/PIXI`），首屏 0 外部请求 |
| mermaid | `cdnjs.cloudflare.com` 懒加载 `import()` | ✅ YAML 关闭（`obsidian-flavored-markdown.options.mermaid: false`；当前内容无 mermaid 图）。将来要用需 fork 该插件，按 v4 `client/quartz/static/mermaid/`（ESM 入口 + chunks 分片）本地化 |
| katex（latex 插件） | `cdn.jsdelivr.net` | 插件 `enabled: false` → 无请求；将来启用前按 v4 写法改本地 `/static/katex/*` |
| Google Fonts | — | 已是本地（`fontOrigin: local` + `cdnCaching: false`） |

> 验收口径：`node .codebuddy/audit-output.mjs output/<站点>` —— "CDN 类外链"应为 0；
> 唯一可能残留的 `cdn.jsdelivr.net` 字符串来自 **pixi 自带的 basis/ktx 转码器默认 URL**（不用压缩纹理不会请求），已知无害。

## 九、图谱（graph-pro）：交互口径与配置

### 打开方式（沿用 v4）
| 操作 | 行为 |
|------|------|
| 右侧栏「关系图谱」 | 局部图谱（当前页邻域） |
| 点「关系图谱」右上角图标 | **放大局部图谱**（弹窗里仍是局部图，字号放大 25%） |
| `Ctrl+G`（macOS `⌘+G`） | **全局图谱浮层**（大区模式） |
| 视口右上角图谱图标（**与阅读模式按钮并列**） | 同上（开/关全局图谱浮层，2026-09-20 新增） |
| 单击节点 | 展开/收起（大区 → 内部核心节点或子聚合；核心节点 → 邻接叶子；聚合节点 → 具体文档） |
| 双击节点 | 跳转到该文档 |

> 按钮实现：`.graph-toggle` 由 graph-pro 的组件脚本注入到 `.page-header > header`，视觉位置走 `position: fixed; top: 0.75rem; right: 3.25rem`（阅读模式是 `right: 1rem`，两者错开一格）。
>
> **右上角按钮排**（自右向左，全部 32×32、`top: 0.75rem`、间距 4px）：
> | 按钮 | 位置 | 来源 |
> |------|------|------|
> | 阅读模式（书本） | `right: 1rem` | reader-mode-pro 自带（`.readermode`，fixed） |
> | 全局图谱（描边地球） | `right: 3.25rem` | graph-pro 脚本注入 `.graph-toggle` |
> | 夜间模式（日/月） | `right: 5.5rem` | 社区 darkmode 按钮；YAML 里已从左侧工具栏移到 `position: header`，再由 `quartz5/quartz/styles/custom.scss` 的 `:root .darkmode` 覆盖为 fixed |
>
> `custom.scss` 是 v5 设计好的用户覆盖层：`componentResources.ts:347` 把它拼在 `@layer quartz-base` **之外**（无层样式优先于有层样式），因此不需要改插件就能覆盖已装插件的样式；必要时再用 `:root` 提升特异性。
>
> **为什么夜间模式写 `custom.scss` 而不是写插件**：darkmode 是**社区插件**（`@quartz-community/darkmode`，`github:quartz-community/darkmode`，`quartz.category: component`，`components.Darkmode.defaultPosition/priority = left/30`），源码落在 `quartz5/.quartz/plugins/darkmode/`——该目录被 `.gitignore:12`（`.quartz/`）忽略，是 git loader（`PLUGINS_CACHE_DIR = .quartz/plugins`）的**同步缓存**（本地插件是软链，社区插件是下载的实体目录），**改它不持久、也不进版本库**。而阅读模式/全局图谱的样式在各自**本地 fork 插件**里（`.readermode` → reader-mode-pro，`.graph-toggle` → graph-pro），因为那两个按钮是本仓库自己的组件。
> ⚠️ `custom.scss` **不属于 §七 核心补丁清单**（那份清单是给 `glob.ts`/`renderPage.tsx` 这类上游逻辑文件打补丁用的）；它是上游预留的用户样式文件，升级时只需确认本段追加内容仍在。当前相对上游为纯新增 39 行、无删改。
> **两个图谱图标刻意不同**：侧栏的实心"节点网络"图标 = **放大局部图谱**（`title="放大局部图谱"`）；右上角**描边地球图标** = **全局图谱**（`title="全局图谱（Ctrl/⌘+G）"`）。
> **不能**把按钮做成 graph-pro 的第二个组件：`config-loader.ts` 只按**插件名**或插件名 PascalCase 查组件，`loadComponentsFromPackage` 仅在「插件恰好一个组件」时才注册插件名别名 → 双组件插件的组件会被布局阶段整体丢弃。

### 关键配置（`quartz.config.yaml` 的 graph-pro 条目）
| 键 | 作用 | 当前值 |
|----|------|--------|
| `graph.localDepth` | 局部图谱预计算深度；运行时判定 `usePrecomputed = depth>0 && depth<=precomputeDepth` | 1 |
| `localGraph.aggregation` | 局部图谱边缘叶子聚合（带数字徽标，点击展开） | `folder depth 1` |
| `globalGraph.regionRules` | 全局大区聚合规则（配置后首屏只显示大区节点） | **`field: type`（按项目类型分大区）** |
| `globalGraph.expandCoresOnRegionOpen` | 展开大区时是否连带展开内部核心节点 | `false` |
| `globalGraph.aggregation` | 核心节点下的边缘叶子聚合（展开后按 目录/type/年份 分组） | folder1 + field type + date year |
| `globalGraph.coreNodeFilter` | **决定哪些节点算核心节点**；folder 规则必须带 `values` | 仅 `项目` |
| `globalGraph.coreNodeLimit` | 核心节点数量硬上限 | 50 |

> ⚠️ **大区的成员来自核心节点**（大区 = 核心节点按 `regionRules[0]` 分组）：当前 `coreNodeFilter.values = [项目]`
> 表示"核心节点只从项目类文档里选"，所以大区是**项目按类型分出的 6 个**：产品研发 / 运营支撑 / 市场推广 /
> 基础设施建设 / 技术预研 / (未分组)（缺 `type` 的归入未分组，生成器 `MISSING_RATE.type = 0.10`）。
> 想让人员/任务等目录也加入大区，就往 `coreNodeFilter.values` 补目录名，并按需放宽 `coreNodeLimit`。

### 力度/间距调参（对齐 v4 Graph.tsx 的 `[TUNING]`，2026-09-20）
| 参数 | 局部图谱 | 全局图谱 | 说明 |
|------|---------|---------|------|
| `linkDistance` | 30 → **70** | 30 → **150** | 原来"边太短"就是因为沿用了 v5 社区版默认 30 |
| `repelForce` | 0.5 → **0.6** | 0.5 → **1.5** | 节点更分散，长标题不重叠 |
| `centerForce` | 0.3 | 0.2 → **0.4** | 全局图谱收紧中心 |
| `fontSize` | 0.6 → **0.75** | 0.6 → **0.72** | 侧栏小图更易读 |

### 抖动优化（2026-09-20，`src/components/scripts/graph.inline.ts`）
| 位置 | 原值 | 现值 | 原因 |
|------|------|------|------|
| 拖拽开始时（局部图谱） | `alphaTarget(1)` | **`alphaTarget(0.3)`** | 拖一个节点整图持续剧烈运动 |
| 展开/收起节点时 | `simulation.alpha(0.3)` | **`alpha(0.15)`** | 全图被反复"加热"，收敛慢 |
| 全局图谱 | `velocityDecay(0.6)` | **`velocityDecay(0.75)`** | 降低惯性，抑制拖拽/展开后的余震 |

### 数据来源（构建期预计算，运行时不再现算）
- 局部图谱：`graph/local/{djb2(slug)[0:2]}/{djb2(slug)[2:4]}/{slug}.json`
- 全局图谱：`graph/global/graphGlobal.json`（含 `firstScreen` / `aggNodes` / `regionNodes` / `adjacency`）
- 取不到时按 v4 逻辑回退到 `fetchData` + 运行时计算（站点不会因此不可用）
- 构建日志核对点：`[Step 7] Agg nodes: N`、`[Step 8] Region nodes: N`、`[GraphGlobal] Output: ...KB, X first-screen, Y agg, Z region`
