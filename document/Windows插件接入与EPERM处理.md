# Windows 插件接入与软链接 EPERM 处理

> 适用：在 **Windows** 上运行 quartz5 构建 / `npx quartz plugin add` 时，插件安装或加载报软链接相关错误。
> 关联文档：`QUARTZ5-COMMANDS.md`（§一 插件开发、§六 当前插件状态、§七 核心补丁清单）。
> 记录时间：2026-09-23，机器 `jrlaptop\skydt`，仓库路径 `d:\CodeProjects\quartz-fullstack`。

---

## 一、症状

构建或安装插件时出现类似：

```
✗ article-title: post-install build failed: EPERM: operation not permitted, symlink '..\..\..\..\node_modules\preact' -> 'D:\...\quartz5\.quartz\plugins\article-title\node_modules\preact'
✗ Failed to install plugin: github:quartz-community/article-title
✗ Failed to build plugin backlinks: EPERM: operation not permitted, symlink ...
```

典型表现还有：构建"看起来成功"，但**插件静默不生效**（页面/产物不生成）。

---

## 二、根因

Windows 上创建**目录软链接**（`fs.symlinkSync(target, path, "dir")`）需要下列任一特权，否则抛 `EPERM`：

1. 以**管理员**身份运行；或
2. 开启**开发者模式**（Developer Mode）；或
3. 账户被授予 **`SeCreateSymbolicLinkPrivilege`**（组策略：本地策略 → 用户权限分配 → 创建符号链接）。

quartz5 的 loader（`quartz5/quartz/plugins/loader/gitLoader.ts`）会在这几处建目录软链：

| 位置 | 用途 |
|---|---|
| `installPlugin()` 本地插件分支 | `.quartz/plugins/<名>` → `plugins-local/<名>` |
| `linkPeerDependencies()` / `trySymlink()` | 给每个插件在 `node_modules/<peer>` 下补 peer 链（`preact`、`@quartz-community/*` 等） |

> 另有本地插件的手动接入（见 §四方案 B）也依赖同样的链接能力。

**为什么"另一台 Windows 没问题"**：那台满足了上面条件之一（多为开了开发者模式或以管理员运行）。还有一种假象——首次安装时具备权限、链接已建好，之后构建都走"已安装直接复用"，就再也不触发建链了。

---

## 三、诊断（3 条命令）

```powershell
# 1) 开发者模式是否开启（空 = 未开启）
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense

# 2) 当前进程是否管理员 + 是否有符号链接特权
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
whoami /priv | Select-String 'SeCreateSymbolicLinkPrivilege'

# 3) 直接实测："dir" 与 "junction" 哪个能建（结论一目了然）
node -e "const fs=require('fs'),p=require('path');const d=p.resolve('.tmp-link-test');fs.rmSync(d,{recursive:true,force:true});fs.mkdirSync(p.join(d,'t'),{recursive:true});try{fs.symlinkSync('t',p.join(d,'l'),'dir');console.log('dir-symlink : OK')}catch(e){console.log('dir-symlink : FAIL '+e.code)}try{fs.symlinkSync(p.join(d,'t'),p.join(d,'j'),'junction');console.log('junction    : OK')}catch(e){console.log('junction    : FAIL '+e.code)}fs.rmSync(d,{recursive:true,force:true});"
```

本机 2026-09-23 的实测结果（未开开发者模式、非管理员）：
```
AllowDevelopmentWithoutDevLicense = (空)
IsAdmin = False
SeCreateSymbolicLinkPrivilege = 无
dir-symlink : FAIL EPERM
junction    : OK
```
→ 结论：**`"dir"` 需特权、`"junction"` 免特权**。

---

## 四、解决方式

### 方案 A（推荐）：开启开发者模式 —— 不改源码、与"另一台正常"的机器对齐

手动路径：`设置 → 隐私和安全性 → 开发者选项 → 开发人员模式 = 开`。

或命令行 UAC 提权写入（会弹管理员确认框）：
```powershell
Start-Process -FilePath 'reg.exe' -Verb RunAs -Wait -PassThru -ArgumentList @(
  'add','HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock',
  '/t','REG_DWORD','/f','/v','AllowDevelopmentWithoutDevLicense','/d','1'
)
```
验证：`(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock').AllowDevelopmentWithoutDevLicense` 应为 `1`。

> 实测：开启后**新进程即时生效**，无需注销/重启（§三 第 3 条命令应变为 `dir-symlink : OK`）。
> 需关闭时把值改回 `0`，或在设置里关掉。

### 方案 B：本地插件手动建 junction —— 无需任何特权

本地插件（`plugins-local/*`）可以**预先**把链接建好，loader 检测到"已是链接且指向同一目标"就直接复用，不再尝试创建 symlink。

一键脚本：`scripts/setup-local-plugins.mjs`
```powershell
cd d:\CodeProjects\quartz-fullstack
node scripts/setup-local-plugins.mjs              # 按需：装依赖 + 构建 + 建 junction（幂等，可反复跑）
node scripts/setup-local-plugins.mjs --force      # 强制重装依赖 + 重建 + 重连
node scripts/setup-local-plugins.mjs --build-only # 只装 + 构建
node scripts/setup-local-plugins.mjs --link-only  # 只建 junction
node scripts/setup-local-plugins.mjs --config     # 只处理 quartz5/quartz.config.yaml 引用的本地插件
node scripts/setup-local-plugins.mjs --only=graph-pro,search-pro
node scripts/setup-local-plugins.mjs --exclude=content-meta-pro,aggregation-pro
```

手动等价命令：
```powershell
New-Item -ItemType Junction -Path '<repo>\quartz5\.quartz\plugins\<名>' -Target '<repo>\plugins-local\<名>'
```

> `junction` 免特权，是文档 §六 里"手动建 junction 绕过 EPERM"的做法；脚本把它自动化了。

### 方案 C：改造 loader 源码（备选，**当前未采用**）

把 `gitLoader.ts` 里两处 `fs.symlinkSync(..., "dir")` 改为 Windows 下用 `"junction"`（Node 会把 junction 的 target 规范化为绝对路径，相对 target 亦可用）。另可在 `installPlugin` 的"已安装直接复用"分支补一句 `linkPeerDependencies(pluginDir)`，让迁机后丢失的 peer 链自动补回。

- 优点：任意 Windows 机器（CI/他人机器）免配置即可跑。
- 缺点：属于对上游的改动，需记入 `QUARTZ5-COMMANDS.md` §七 核心补丁清单，升级上游时逐一核对。
- **本次已按用户要求回退，源码保持原样**；如将来要"跨机器免配置"，可再加回。

---

## 五、迁机后插件状态修复（如 E: → D: 整体拷贝）

整体拷贝仓库后，符号链接/软链**不会**跟着复制，会产生一批"半损坏"插件：

1. **本地插件 junction 丢失** → 跑方案 B 的脚本重建即可。
2. **社区插件的 peer 链丢失**（`node_modules/preact` 等） → 一般可向上解析到 `quartz5/node_modules` 仍能跑；要彻底干净就重装该插件（删掉 `.quartz5/plugins/<名>` 后重构建）。
3. **社区插件缺 `dist`** → 构建报 `Failed to instantiate plugin ... Cannot find module`。
   原因：loader 对"已安装"插件会 early-return，**不会**补建 `dist`。手动补：
   ```powershell
   cd quartz5\.quartz\plugins\<名>
   npm run build          # 若报 'tsup' is not recognized，先 npm install
   ```

---

## 六、常见坑

| 现象 | 原因 / 处理 |
|---|---|
| `EPERM: operation not permitted, symlink ...` | 见 §二/§四，开开发者模式或用 junction |
| `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]` | CodeBuddy/IDE 的批量删除守卫拦截了 npm 的清理；先手动删目标目录，或改用非 IDE 终端跑 `npm install` |
| `Cannot find module @rollup/rollup-win32-x64-msvc` | npm 可选依赖已知 bug；删掉 `package-lock.json` + `node_modules` 后重装，或单独 `npm i @rollup/rollup-win32-x64-msvc` |
| `spacer: post-install build failed: spawnSync cmd.exe ETIMEDOUT` | loader 内 `npm install` 单步 120s 超时；重跑构建通常即可（网络/首次安装慢） |
| 插件改了没生效 | 忘 `npm run build`（junction 只同步源码目录，`dist` 需手动构建） |
| `dir-symlink : OK` 但构建仍报 EPERM | 用的是旧进程/旧终端；新开一个终端再跑 |

---

## 七、验证清单

```powershell
# 1) 软链能力（应为 dir-symlink : OK）
node -e "const fs=require('fs'),p=require('path');const d=p.resolve('.tmp-link-test');fs.rmSync(d,{recursive:true,force:true});fs.mkdirSync(p.join(d,'t'),{recursive:true});try{fs.symlinkSync('t',p.join(d,'l'),'dir');console.log('dir-symlink : OK')}catch(e){console.log('dir-symlink : FAIL '+e.code)};fs.rmSync(d,{recursive:true,force:true});"

# 2) 本地插件 junction 状态（应全是 Junction 且 dist=True）
node -e "const fs=require('fs');const p='d:/CodeProjects/quartz-fullstack/quartz5/.quartz/plugins';for(const n of fs.readdirSync(p)){const s=fs.lstatSync(p+'/'+n);console.log(n.padEnd(26),'isLink='+s.isSymbolicLink(),'dist='+fs.existsSync(p+'/'+n+'/dist'));}"

# 3) 小输入验证构建（~15s），应无 EPERM / Failed to install / Failed to instantiate
cd d:\CodeProjects\quartz-fullstack\quartz5
npx quartz build -d docs -o ../output/rm-test 2>&1 | Select-String -Pattern 'EPERM|Failed to install|Failed to instantiate|post-install|Emitted|Done processing'
```
