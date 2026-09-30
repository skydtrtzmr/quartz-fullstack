# GraphPro 增量构建偶发卡死排查记录

> 结论先说：`plugins-local/graph-pro` 的增量局部图谱生成里，有一段"顺着目录往上找祖先"的 `while`
> 在遇到以 `/` 开头的 slug（唯一来源是根页面 `/`）时会**死循环**，进程占满一个 CPU 核、不产出任何日志、
> 不退出。定时任务批量改 mtime 触发增量构建时如果命中了根页面，就会"永久卡住"。

- 影响面：所有使用 `graph-pro`（本仓 `plugins-local/graph-pro`）**增量构建（`--sqlite`，不带 `--reset`）**的域
- 触发概率：偶发。取决于本次变更集合里是否会带出根页面 `/`
- 现场特征：任务日志卡在 GraphPro 这个 emitter 上；`/status` 永远 `running`；`node.exe` 满一个核
- 修复：`plugins-local/graph-pro/src/emitters/graphLocal.ts` 祖先回溯循环补 `if (slash === 0) break`，
  然后 **重新 `npm run build` 生成 `dist/index.js`**（运行时加载的是 dist）

---

## 一、问题现象

### 1. 服务端表现

- 某些**增量**构建（定时任务触发、不带 `reset`）会永久卡住，后台不报错、不退出。
- `{{ip}}/api/domain/{{domain}}/status?user=admin&pwd=password123` 永远返回 `running`。
- 任务日志（`logs/tasks/task-{domain}-{ts}.log`）停在某个位置不再增长。
- 服务器上 `node.exe` 持续吃满一个核，且**没有任何输出**。

### 2. 日志停在哪儿

补 emitter 级日志**之前**，日志尾部是（`server/logs/why/tasks/task-test1-1790683202.log`）：

```
ContentIndex: Updated _dimensions/项目负责人/管理员
ContentIndex: Final index has 373 entries
```

补 emitter 级日志**之后**，能再精确定位一步：

```
ContentIndex: Final index has 373 entries
[emitter] <- ContentIndex 完成，14ms，产出 4 个文件     ← ContentIndex 是好的，14ms 就结束了
[emitter] -> GraphPro (partialEmit, content=394)        ← 卡在这里，永远等不到 "<-"
```

也就是说：**卡点不在 ContentIndex，而在它后面的 `GraphPro` 这个 emitter 内部**。
（`ContentIndex: Final index has ...` 之后没有 `[GraphPro]` 日志，是因为 `[GraphLocal] Incremental update...`
这行日志打印得比较晚，前面还有读 `contentIndex.json`、算受影响页、扫祖先目录等步骤。）

### 3. 进程状态（关键证据）

服务器上一个卡住的构建进程实测：

```
Id    StartTime              CPU
6120  2026/9/29 20:28:34     61423.45     ← 累计 CPU ≈ 17.06 小时
6120  2026/9/29 20:28:34     61444.70     ← 隔一会儿再采样，又涨了 21 秒
```

`CPU 时间` 是累计 CPU 秒数，不是百分比。**进程存活 ≈ 17.1 小时、累计 CPU ≈ 17.06 小时**
⇒ 从启动第一秒起就平均占满一个核。

> 这一步就把"等 I/O"排除了：阻塞在 `ReadFile/WriteFile`/锁上的线程是在内核里睡觉的，
> CPU 时间几乎不增长。**CPU 时间 ≈ 存活时间 = 用户态死循环/自旋**。

### 4. 为什么状态会永远 `running`

Go 服务侧的任务状态只是内存里的一张表，条目只在 `cmd.Run()` 返回后才删除：

```74:78:server/api.go
func runBuildAsyncTask(enableOptional bool, domain string) {
	defer func() {
		// 任务结束时清理状态
		domainTaskManager.EndTask(domain)
	}()
```

```1093:1099:server/domain_config.go
	if domainTaskManager.IsRunning(domain) {
		state := domainTaskManager.GetTaskState(domain)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status": "running", "domain": "%s", "taskId": "%s", "startTime": "%s"}`,
			domain, state.TaskID, state.StartTime.Format(time.RFC3339))
		return
	}
```

死循环 → `cmd.Run()` 不返回 → 表里的条目不清 → `/status` 永远 `running`，日志永远停在那一行。

### 5. 会留下"孤儿进程"

Windows 上父进程退出不会杀子进程，而当前实现没有 Job Object：

- 若服务（或整个进程树）在这期间被重启/强杀，这个 node 进程就变成孤儿，继续空转，谁也管不到它；
- 反过来，如果服务是被"重启"的，任务表被清空，下一次构建不会被 `Busy` 挡住 —— 于是"卡住的构建"
  在日志上看起来就像"凭空出现"，并且任务日志里**不会有 `=== TASK-... END ===`**（因为 `cmd.Run()` 从未返回）。

### 6. 为什么"有时候才卡"

- 全量构建（`reset=true`）、或"没有文件变更"（`No changes detected`）都正常；
- 只有**检测到少量变更、且走增量 `partialEmit`** 的构建会卡，且**不是每次**。

---

## 二、排查过程

### 步骤 1：从任务日志的最后一行划定范围

`ContentIndex: Final index has ...` 是 ContentIndex 在 4 次 `write()` **之前**打印的，所以最初只能划出
"ContentIndex 收尾 / GraphLocal 开头"这么一段。范围太大，光看日志无法继续。

### 步骤 2：用 CPU 时间区分"死循环"和"等 I/O"

见上文 1.3。结论：**用户态死循环**，于是方向从"文件句柄/杀软/网络盘"转到"找那段循环代码"。

### 步骤 3：补日志，把范围缩到某个 emitter

在 `quartz5/quartz/build.ts` 的增量 emitter 循环里加壳（所有 emitter 都从这里过）：

```ts
const runEmitter = async (emitter, content, forceFull = false) => {
  const mode = forceFull || coldBuild ? "emit" : emitter.partialEmit ? "partialEmit" : "emit(fallback)"
  const t0 = Date.now()
  const filesBefore = emittedFiles
  lastEmitterName = emitter.name
  console.log(`[emitter] -> ${emitter.name} (${mode}, content=${content.length})`)
  try {
    // ...原有逻辑不动...
    console.log(`[emitter] <- ${emitter.name} 完成，${Date.now() - t0}ms，产出 ${emittedFiles - filesBefore} 个文件`)
  } catch (err) {
    console.log(`[emitter] xx ${emitter.name} 异常，${Date.now() - t0}ms:`, err)
    throw err
  }
}
```

外加阶段边界日志、以及进程退出兜底：

```ts
let lastEmitterName = ""
process.on("exit", (code) => console.log(`[exit] code=${code} lastEmitter=${lastEmitterName}`))
```

有了这组日志，"卡住"就能一眼读成 **`-> GraphPro` 没有对应的 `<-`**。
（注意：被 `taskkill /F` 强杀时 `process.on("exit")` 不会触发，这是平台限制。）

### 步骤 4：写一个可重复的触发脚本

`scripts/touchAndBuild.ps1`：对齐到整十分，把 `input/{domain}` 下的 `.md` mtime 批量改成当前时间，
然后立刻跑一次**不带 `--reset`** 的 `--sqlite` 构建，日志落到 `scripts/logs/touchbuild-*.log`。
这与服务器上"定时任务先改 mtime，再调构建接口"的场景等价。

关键参数：

```powershell
.\scripts\touchAndBuild.ps1 -Domain demo-region -Once                    # 只跑一轮
.\scripts\touchAndBuild.ps1 -Domain demo-region -TouchLimit 31 -Once     # 只随机改 31 个文件的 mtime
.\scripts\touchAndBuild.ps1 -Domain demo-region -TouchLimit 0 -Once      # 改全部（必含根 index.md）
.\scripts\touchAndBuild.ps1 -Domain demo-region -InspectPort 9229 -Once  # 顺带开 inspector
```

### 步骤 5：偶发卡住时抓 JS 调用栈

死循环期间 `setInterval` 这类 JS 侧定时器会被饿死，只能从**外部**抓栈。做法：

1. 构建命令带 `--inspect=127.0.0.1:9229`（脚本用 `-InspectPort`；Go 服务改 `config.json` 的 `command.interpreter_args`）；
2. 卡住后用 `scripts/dumpJsStack.mjs` 连上去发 `Debugger.pause`（V8 能中断正在执行的同步循环）：

```powershell
node scripts/dumpJsStack.mjs            # 连 9229，暂停并打印调用栈
node scripts/dumpJsStack.mjs auto       # 端口从最新 scripts/logs/touchbuild-*.log 里读
node scripts/dumpJsStack.mjs --profile 8  # 不暂停，采样 8 秒看 CPU 热点
```

实测结果（服务器现场）：

```
=== 已暂停（reason=other）JS 调用栈 ===
 0  partialEmit  @ file:///C:/Project/quartz-fullstack/plugins-local/graph-pro/dist/index.js:313:52
```

两个关键信息：

- 栈顶就是 `partialEmit` 本体（不是它调用的 `calculateLocalGraph`），说明死循环在它**自己的循环体**里；
- 加载路径是 `plugins-local/graph-pro/dist/index.js` —— **运行时加载的是编译产物 dist，不是 `src/`**
  （这也解释了为什么改 `src/` 不生效；`dist/` 在 `.gitignore` 里，所以全局搜代码也搜不到它）。

### 步骤 6：读那一行，找到循环

```309:316:plugins-local/graph-pro/dist/index.js
      for (const affected of [...affectedSlugs]) {
        let slash = affected.lastIndexOf("/");
        while (slash >= 0) {
          const parent = affected.slice(0, slash + 1);
          if (linkIndex.has(parent)) affectedSlugs.add(parent);
          slash = affected.lastIndexOf("/", slash - 1);
        }
      }
```

栈顶停留的 `:313` 正是 `linkIndex.has(parent)` / `affectedSlugs.add(parent)` 这一句。

### 步骤 7：确认"什么 slug 会让它转不出来"

从 dist 产物里读到 `@quartz-community/utils` 的 `simplifySlug` 实现：

```30:33:plugins-local/graph-pro/dist/index.js
function simplifySlug(fp) {
  const res = stripSlashes(trimSuffix(fp, "index"));
  return res.length === 0 ? "/" : res;
}
```

- `simplifySlug("index")` → 空串 → **`"/"`**（根页面）
- `simplifySlug("项目/index")` → `"项目/"`（尾斜杠，代码注释里也写了"实测形式是 `项目/`"）
- 其余 slug 都被 `stripSlashes` 去掉了前导斜杠

**唯一会产生"以 `/` 开头"的 slug 就是根页面 `/`。**

---

## 三、根因

### 1. 直接原因：`lastIndexOf` 的负 fromIndex 会被钳成 0

```ts
let slash = affected.lastIndexOf("/")
while (slash >= 0) {
  const parent = affected.slice(0, slash + 1)
  if (linkIndex.has(parent)) affectedSlugs.add(parent)
  slash = affected.lastIndexOf("/", slash - 1)   // ← slash 为 0 时，fromIndex = -1
}
```

当 `affected` 以 `/` 开头（`"/"`、`"/xxx"`）：

1. `slash = 0`（位置 0 就是那个 `/`）；
2. `parent = "/"`，加进集合（无害）；
3. `lastIndexOf("/", -1)` —— JS 会把负数 `fromIndex` **钳成 0**，于是"只在位置 0 找 `/`"，
   而位置 0 恰恰就是 `/` → **返回 0**；
4. `slash` 永远是 0 → 死循环。

| `affected` | `slash` 变化 | 是否终止 |
|---|---|---|
| `"/"` | 0 → `lastIndexOf("/", -1)` → 0 → … | **死循环** |
| `"项目/"` | 2 → `lastIndexOf("/", 1)` → -1 | 终止 |
| `"项目/a"` | 3 → `lastIndexOf("/", 2)` → -1 | 终止 |
| `"a/b/c"` | 3 → 1 → `lastIndexOf("/", 0)` → -1 | 终止 |

### 2. 什么情况下 `affectedSlugs` 里会出现 `/`

`GraphLocal.partialEmit` 里的 `affectedSlugs` 由这几路灌入：变更文件本身的 slug、其
"上一次局部图谱"里的所有节点、其出链/标签、以及所有链到它的页面（入链），最后再补每个的祖先目录。
于是有两条路径能带出 `/`：

1. **根 `index.md` 参与了本次变更** → `simplifySlug("index") = "/"` 直接进集合；
2. **某个变更页的"上一次局部图谱"里把根页面当邻居带了进来**（例如它被根 `index.md` 链接过），
   那么该页变更时，`previous.nodes` 里的 `"/"` 也会进集合。

第 2 条解释了"偶发"：改哪个页面、以及它跟根页面的链接关系，都会影响是否命中 `/`。
`-TouchLimit 0`（改全部文件）必然包含根 `index.md`，因此是**确定性复现**手段。

---

## 四、解决方案

### 1. 源码修复（必须改这里）

`plugins-local/graph-pro/src/emitters/graphLocal.ts`：

```407:419:plugins-local/graph-pro/src/emitters/graphLocal.ts
      // 文件夹图谱包含所有后代文件；增删或关联变化时重算每一级祖先目录。
      for (const affected of [...affectedSlugs]) {
        let slash = affected.lastIndexOf("/")
        while (slash >= 0) {
          const parent = affected.slice(0, slash + 1) as SimpleSlug
          if (linkIndex.has(parent)) affectedSlugs.add(parent)
          // ⚠️ 以 "/" 开头的 slug（最典型是根页面 "/"）必须在这里收尾：
          // 否则 next = lastIndexOf("/", -1) 会被钳成 fromIndex=0，又命中位置 0 的 "/"，
          // slash 永远停在 0 → 死循环（100% CPU、无日志输出）。
          if (slash === 0) break
          slash = affected.lastIndexOf("/", slash - 1)
        }
      }
```

这个改法的性质：**只对"以 `/` 开头"的输入改变行为，而这类输入正是原来会打转的**。
该加的祖先（包括 `/` 本身）一个都不少，只是"到 0 必须收尾"。等价写法 `while (slash > 0)`
也可以，但会漏掉 `/` 这个祖先，所以选了 `break` 这种"行为不变、只保证终止"的形式。

### 2. 重新编译（关键，别漏）

运行期加载的是 `plugins-local/graph-pro/dist/index.js`，**只改 `src/` 不 build 等于没改**：

```powershell
cd plugins-local/graph-pro
npm run build
```

服务器同样要更新那份 dist（构建后同步过去）。若暂时不方便编译，可先热修服务器的
`plugins-local/graph-pro/dist/index.js`，在 `affectedSlugs.add(parent)` 之后插入一行：

```js
          if (slash === 0) break;
```

### 3. 验证

```powershell
# 触碰全部 md（必然包含根 index.md → "/" 进 affectedSlugs）：
# 修复前必卡（60 秒超时被强杀、日志停在 [emitter] -> GraphPro），修复后 ~10 秒成功
.\scripts\touchAndBuild.ps1 -Domain demo-region -TouchLimit 0 -TimeoutSeconds 60 -Once
```

期望日志（修复后）：

```
[emitter] -> GraphPro (partialEmit, content=...)
[GraphLocal] Incremental update (depth=1)...
[GraphLocal] Changed files: N, Affected pages: M
[GraphLocal] Incremental generation complete: M pages updated
...
[emitter] <- GraphPro 完成，...ms，产出 ... 个文件
Done incremental build in ~10s
```

手工最小复现（针对第 1 条路径）：只改**根** `input/{domain}/index.md`（内容随便加一行），
然后用接口触发一次**不带 `reset`** 的构建（`POST /api/domain/{domain}/build`）——修复前必卡。

> 注意：子目录的 `index.md`（如 `项目/index.md`）**不是**触发条件，它们的 simplifySlug 结果是
> `项目/`（尾斜杠），循环能正常结束。

---

## 五、经验与后续建议

### 1. 这类"祖先回溯"循环的正确写法

错误模式（本 bug）：用 `lastIndexOf(sep, pos - 1)` 递减，遇到"位置 0 就是分隔符"时 `pos` 卡在 0。
推荐改成"从头往后扫"或显式收尾，二选一：

```ts
// 写法 A：显式收尾（本次采用，改动最小）
if (slash === 0) break

// 写法 B：正向扫描，天然不存在钳位问题
for (let i = affected.indexOf("/"); i >= 0; i = affected.indexOf("/", i + 1)) {
  const parent = affected.slice(0, i + 1)
  if (linkIndex.has(parent)) affectedSlugs.add(parent)
}
```

### 2. 同类循环审计结论

仓库里其它"逐层向上回退"的循环都是安全写法（用 `slash > 0 ? slice : ""`、`idx < 0 ? ""`、
或先 `includes("/")` 判断），已逐一确认，**无需修改**：

- `plugins-local/aggregation-pro/src/compiler.ts`
- `plugins-local/aggregation-page-pro/src/util/rules.ts`
- `plugins-local/note-properties-pro/src/util/propertiesChain.ts`
- `plugins-local/explorer-pro/src/util/fileTrie.ts`
- `plugins-local/backlinks-pro/src/components/Backlinks.tsx`
- `plugins-local/*/src/components/scripts/*.inline.ts`（若干）

### 3. 服务端建议补的防护（本次未做）

1. **构建超时 / 看门狗**：构建超时或"任务日志 N 分钟没有增长"就 `taskkill /T /F` 子进程并标记失败，
   这样即使再出现任何死循环，也只会损失 N 分钟，`/status` 不会被永久钉在 `running`。
2. **Windows Job Object（`KILL_ON_JOB_CLOSE`）**：服务退出/崩溃时子进程一起死，避免孤儿进程空转一夜。
3. **可见性**：`Busy` 分支、非 POST 的 405 分支目前静默；建议补日志并带上 `query`/`remote`/`User-Agent`；
   `/build` 响应补 `Cache-Control: no-store`（`/status`、`/logs` 已有）。

### 4. 排查工具沉淀

| 工具 | 用途 |
|---|---|
| `scripts/touchAndBuild.ps1` | 复现"定时任务改 mtime + 增量构建"：`-TouchLimit 0/31`、`-InspectPort`、`-TimeoutSeconds` |
| `scripts/dumpJsStack.mjs` | 连 `--inspect` 端口，`Debugger.pause` 抓 JS 调用栈；`--profile N` 采样 CPU 热点 |
| `quartz5/quartz/build.ts` 里的 `[emitter]` 日志 | 一眼看出卡在哪个 emitter（`->` 没有配对的 `<-`） |
| CPU 时间 vs 存活时间 | 区分"死循环"（两者接近）和"等 I/O"（CPU 不涨） |

### 5. 两个容易踩的坑

1. **改了插件 `src/` 不生效**：运行期优先加载 `dist/`；而 `dist/`、`.quartz-cache/` 等目录被
   `.gitignore` 忽略，所以按名字搜代码时经常"搜不到"运行中的那份代码。
2. **`--inspect` 抓栈是唯一能在"同步死循环"期间拿到现场的手段**；日志、`setInterval` 心跳在这类
   卡死下都不会触发。端口被上一个卡死的进程占用时，新进程的 inspector 会绑定失败，直接连那个
   占着端口的进程即可。

---

## 附录：本次涉及的文件

| 文件 | 说明 |
|---|---|
| `plugins-local/graph-pro/src/emitters/graphLocal.ts` | **修复点**：祖先回溯循环加 `if (slash === 0) break` |
| `plugins-local/graph-pro/dist/index.js` | 运行时实际加载物；改完 `src` 必须 `npm run build` 重新生成 |
| `quartz5/quartz/build.ts` | 增量 emitter 循环加 `[emitter] ->/<-`、`[phase]`、`[exit]` 日志 |
| `plugins-local/content-index-pro/src/emitter.ts` | 加 `[write] start/done`、`ContentIndex: serializing/serialized` 日志（同样需 build 才生效） |
| `plugins-local/graph-pro/src/util/write.ts` | 同上（写局部图谱的 write 加日志） |
| `scripts/touchAndBuild.ps1` | 复现脚本 |
| `scripts/dumpJsStack.mjs` | 抓 JS 栈 / CPU 采样工具 |
