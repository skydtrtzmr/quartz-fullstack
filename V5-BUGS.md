# Quartz v5 已知问题与 Bug 处理清单

> 处理原则：影响当前任务开发的问题立即修；纯上游 bug 记录待办，避免与 v5 核心改动冲突过多。
> 上游社区 bug 修复后可考虑向社区提交 PR 反哺。

## 状态说明

- **待处理**：尚未动手
- **处理中**：正在修
- **已处理**：修复完成（注明改在哪）
- **不修**：评估后决定不处理（注明理由）

---

## 一、v5 核心问题

### BUG-V5-001【已处理】glob 尊重 .gitignore 导致扫描不到输入文件

- **现象**：`npx quartz build -d ../input/xxx` 报 `Found 0 input files`，但目录里明明有内容
- **根因**：`quartz/util/glob.ts` 使用 globby 时 `gitignore: true`，而仓库根 `.gitignore` 里有 `/input` 规则，把输入目录整个忽略了
- **处理**：改为 `gitignore: false`（v4 同款补丁，见 `quartz5/quartz/util/glob.ts` 注释 `[M]`）
- **注意**：升级 v5 核心时此补丁可能被覆盖，需检查

### BUG-V5-002【已处理】根目录 @quartz-community/utils 版本漂移

- **现象**：构建报 `does not provide an export named 'normalizeHastElement'`
- **根因**：`quartz5/node_modules` 里的 utils 被降级到 0.1.0，v5 核心需要的导出不存在
- **处理**：`npm install @quartz-community/utils@^1.0.0`（当前 1.0.1）
- **预防**：动过 quartz5 依赖后构建报"导出不存在"类错误，优先查该包版本

### BUG-V5-003【待处理】移动端滚动时顶部跟着下移

- **现象**：移动端（≤800px 断点）页面滚动时，顶部区域（header/toolbar）会跟着往下挪一段，不是固定在顶部
- **来源**：用户 2026-09-19 实测原版（社区插件全配置）发现
- **疑似方向**：`quartz/styles/base.scss` 中移动端布局 grid/`position: sticky` 的层叠问题，或 sidebar 移动端样式与 header 的相互作用
- **优先级**：低（移动端体验问题，不阻塞桌面端任务 6 开发）
- **处理计划**：后续集中处理移动端适配时一起看；先复现定位，若为 v5 上游 bug 修复后考虑提 PR

### BUG-V5-005【已处理】serve 模式无条件清空 basePath 与 --baseDir 矛盾

- **现象**：`npx quartz build --serve --baseDir demo-bench` 预览时，页面能从 `/demo-bench/` 打开，但社区插件（图谱/搜索）运行时 fetch 的 JSON 全部打到根路径 → 404；且从根路径 `/` 进入时站内相对链接全部丢失前缀
- **根因**：上游提交 ad685b8（fix: use correct baseurl in serve mode）让 renderPage.tsx 在 serve 模式**无条件**清空 basePath（`data-basepath=""`），但 v5 的 serve 又支持 `--baseDir` 子路径挂载——两者不联动。`@quartz-community/utils` 的 `getBasePath()` 读 `document.body.dataset.basepath`，为空时组件 fetch 丢失前缀
- **处理（v5 核心补丁 #3）**：`quartz/components/renderPage.tsx` 改为 `(serve && !baseDir) || !baseUrl` 才清空——带 baseDir 的 serve 保留 basePath（2026-09-19）
- **验证**：serve+baseDir 下 `data-basepath="/demo-bench"`；`/demo-bench/static/contentIndex.json` 返回 200；根路径 404 属预期（服务器 guard）
- **注意**：v5 核心补丁累计 3 个（glob gitignore / topSpacing / renderPage basepath），升级核心时逐一检查保留
- **附注**：v4 曾用组件级三段式 baseUrl 解析（client 仓库提交 6adcbf6）绕开此问题，v5 暂不引入该方案（最小改动原则），若未来自研插件需要更强的前缀健壮性可参考

### BUG-V5-004【已处理】`plugin add` 自动追加的 YAML 条目丢失 group 字段

- **现象**：本地插件安装后，组件掉出 Flex 工具组（如阅读按钮和夜间模式不在一行）
- **根因**：`npx quartz plugin add` 追加进 `quartz.config.yaml` 的条目不含 `group: toolbar`，需手动补
- **处理**：YAML 中手动补 `group: toolbar`；每次 `plugin add` 后检查新条目的 layout 字段完整性

### BUG-V5-006【待处理】单份 YAML 的 baseUrl 与 Go server 多域目录不匹配（data-basepath 错位）

- **现象（2026-09-19 搜索插件实测中发现）**：`quartz.config.yaml` 里 `baseUrl: localhost/doc-demo`，但产物输出到 `output/demo-bench` 并由 Go server 以 `/demo-bench/` 提供服务。页面资源（`./static/...` 相对路径）正常，但 `body[data-basepath]="/doc-demo"`——**所有走 `@quartz-community/utils` 的 `getBasePath()/resolveBasePath()` 的运行时 fetch 全部 404**
- **实测证据**：搜索面板能出结果与统计条（索引走 `./static/contentIndex.json` 相对路径），但
  - 结果卡片 href = `/doc-demo/问答/qa-00105` → 404
  - 预览面板 `preview-inner` 为空（fetch `/doc-demo/...` 404）
  - 手动 `document.body.dataset.basepath='/demo-bench'` 后同一操作预览立即正常（155 字/1560 字节），证明是前缀错位而非逻辑问题
- **影响面**：不只搜索——图谱、explorer 等所有依赖 `getBasePath()` 的社区插件在 Go server 下同样错位
- **关联决策**：这正是"路线 B"里规划过的 **per-domain YAML**（Go server 为每个 domain 生成一份 baseUrl 匹配的 YAML）要解决的问题
- **临时规避**：构建某个 domain 的产物时，先把 YAML 的 `baseUrl` 改成该 domain（如 `localhost/demo-bench`）再 build
- **优先级**：中（不阻塞插件开发，但影响 Go server 端到端验收的真实性）

---

## 二、社区插件问题

### BUG-COM-001【已处理】reader-mode 社区版 `::root` 选择器无效

- **现象**：点击阅读模式按钮无任何视觉变化（v4 同款代码同样中招，即 v4 的阅读模式也从未真正生效过）
- **根因**：`reader-mode` 社区插件 scss 写了 `::root[reader-mode="on"]`（双冒号），CSS 规范中伪元素语法用于 root 无效，整条规则被浏览器丢弃
- **处理**：本地 fork `reader-mode-pro` 修正为 `:root`，并用更高特异性选择器实现全宽
- **后续**：可向 quartz-community/reader-mode 提 PR 修复上游

### BUG-COM-002【记录】latex 插件 Windows 构建失败

- **现象**：tsup 构建报找不到 `http-proxy-agent`（jsdom 依赖）
- **处理**：配置中 latex 已 `enabled: false`，且 `.quartz/plugins/index.ts` 中已移除其导出，不影响使用
- **注意**：将来启用 latex 时需先解决

### BUG-COM-003【已处理】阅读模式与全局图谱浮层冲突（图谱消失/打不开）

- **现象**（用户 2026-09-20 实测）：先打开全局图谱、再切阅读模式 → 图谱消失且再也打不开，只能把阅读模式切回去才恢复
- **根因**：全局图谱浮层 `.global-graph-outer`（`position: fixed; z-index: 9999`）在 DOM 上**嵌在右栏内部**（graph-pro 的 `Graph.tsx:189` 把它渲染在 `.sidebar.right > .graph` 里），而阅读模式的全宽样式把右栏设为 `display: none`（`readermode.scss` 的 `:root[reader-mode="on"] { #quartz-body .sidebar.left, #quartz-body .sidebar.right { display: none } }`）→ **`display:none` 的祖先会把 fixed 后代一起移出渲染树**，fixed/z-index 都救不了。实测：阅读模式开启后浮层 `.active` 仍在、但 `getBoundingClientRect()` 变成 `0x0`
- **处理**（仅改 `plugins-local/reader-mode-pro/src/components/styles/readermode.scss`，未动 graph-pro）：
  ```scss
  :root[reader-mode="on"] #quartz-body:has(.global-graph-outer.active) .sidebar.right { display: flex; }
  ```
  浮层打开时保留右栏在渲染树中（浮层是全屏 fixed + 模糊遮罩，遮罩下的侧栏不外露），关闭后立即回到"无侧栏全宽阅读"。特异性 (1,6,0) > 阅读模式规则的 (1,4,0)，无需 `!important`；依赖 `:has()`（Chrome 105+/Safari 15.4+/Firefox 121+），不支持时退化为旧行为
- **验证**（无头浏览器实测两种顺序，全部通过）：① 开图谱(1266px) → 切阅读模式 → 浮层仍 1266×627、右栏 `flex`、左栏 `none`、canvas 正常 ② 先阅读模式 → 点开图谱 → 浮层 1266×627、canvas 1520×753 正常绘制 ③ 阅读模式内关闭浮层 → 右栏回到 `none`、正文恢复全宽 1266px ④ 退出阅读模式 → 左右栏均恢复 `flex`
- **备选方案（未采用）**：在 graph-pro 里把浮层 DOM 迁移到 `<body>`（架构上更正统，可一并修掉移动端右栏被隐藏时浮层同样不可见的问题），但要同时改 `graph.scss` 的 `.graph > .global-graph-outer` 选择器与 SPA 导航后的重挂载逻辑，改动面大；若将来图谱浮层还需要在移动端/更多场景复用，再考虑此方案

---

## 三、reader-mode-pro 遗留问题（自身开发中的）

### TODO-RM-001【已处理·迭代2】阅读模式按钮 fixed 视口右上角常驻

- **需求**：桌面版和移动端统一在视口右上角固定显示阅读模式按钮（不随滚动、不随侧栏隐藏消失）；点击态有视觉区分；压缩整体顶部留白
- **迭代记录**：
  - 迭代1（2026-09-19 上午）：移入 header 槽位 + margin-left:auto。**实测三个问题**：① header 槽位实际渲染在 `.center` 列内（DefaultFrame 结构），不是全宽顶栏 ② 按钮跟正文滚动 ③ 只对齐 .center 右缘非视口右缘
  - 迭代2（当前）：改 `position: fixed; top: .75rem; right: 1rem; z-index: 200` 直接锚定视口右上角；悬停底色 + 开启态图标高亮 `--secondary`（`:root[reader-mode=on] .readermode svg`）
- **附带（v5 核心补丁 #2）**：`quartz/styles/variables.scss` 的 `$topSpacing: 6rem → 2rem`——顶部留白 96px 压缩为一条窄带，同时收紧 .page-header margin 与 sidebar padding-top。**升级 v5 核心时注意保留**
- **待用户实测**：三个问题的实际视觉效果

### TODO-RM-002【待复测】阅读模式状态刷新行为

- **现象**：用户曾报告"一刷新就会整个卡住"（旧构建，按钮还在侧栏内时）
- **推断**：按钮移入 header 后应自然解决（刷新重置 off + 常驻按钮可退出）
- **待办**：用户实测新构建确认

---

## 四、环境/工具链问题

### ENV-001【记录】Windows symlink 插件安装的构建步骤不可靠

- `npx quartz plugin add <本地路径>` 内部跑 npm install/build 在 Windows symlink 路径下会失败
- **规避**：手动在 `plugins-local/<插件>` 下 `npm install && npm run build`；`plugin add` 只用来做注册（symlink + lockfile + YAML 条目）

### ENV-002【记录】serve 僵尸进程

- `--serve` 是常驻进程，终端 Ctrl+C 不彻底或直接关终端会留下僵尸进程占端口，且其 watcher 会与新构建互踩输出目录
- **处理**：`netstat -ano | findstr :8080` → `Stop-Process -Id <PID> -Force`
- **预防**：退出 serve 务必在原终端 Ctrl+C 等提示符返回

### ENV-003【记录】safe-delete trash 失败

- 构建清理输出目录时报 `[safe-delete] 操作失败` = 目录被浏览器/编辑器/资源管理器占用
- **处理**：关闭占用方或换输出目录
