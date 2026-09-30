#!/usr/bin/env node
// 抓一个「卡住的 --inspect 构建进程」的 JS 调用栈（同步死循环也能抓：V8 会中断正在跑的 JS）。
//
// 前提：构建进程是带 --inspect 启动的（scripts/touchAndBuild.ps1 -InspectPort 9229、
//       或 Go server 的 config.json → command.interpreter_args 里加 --inspect=127.0.0.1:9229）。
//
// 用法：
//   node scripts/dumpJsStack.mjs                  # 连 127.0.0.1:9229，暂停并打印调用栈
//   node scripts/dumpJsStack.mjs 9230             # 指定端口
//   node scripts/dumpJsStack.mjs auto             # 从最新的 scripts/logs/touchbuild-*.log 里读端口
//   node scripts/dumpJsStack.mjs --profile 8      # 不暂停，采样 8 秒，打印 CPU 热点（自耗时占比）
//
// 需要 Node 22+（用全局 WebSocket / fetch，无需装依赖）。
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)

if (typeof WebSocket === "undefined") {
  console.error("当前 node 没有全局 WebSocket（需要 Node 22+）")
  process.exit(2)
}

function portFromNewestLog() {
  const dir = path.join(here, "logs")
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.startsWith("touchbuild-") && f.endsWith(".log"))
    .map((f) => ({ f, t: fs.statSync(path.join(dir, f)).mtimeMs }))
    .sort((a, b) => b.t - a.t)
  for (const { f } of files) {
    const m = fs.readFileSync(path.join(dir, f), "utf-8").match(
      /Debugger listening on ws:\/\/127\.0\.0\.1:(\d+)\//,
    )
    if (m) {
      console.log(`[info] 从 ${f} 读到 inspector 端口 ${m[1]}`)
      return Number(m[1])
    }
  }
  throw new Error("没在 scripts/logs/*.log 里找到 'Debugger listening on ws://127.0.0.1:PORT'")
}

const rest = []
let profileSeconds = 0
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--profile") profileSeconds = Number(args[++i] ?? 5) || 5
  else rest.push(args[i])
}
const port = rest[0] ? (rest[0] === "auto" ? portFromNewestLog() : Number(rest[0])) : 9229
const base = `http://127.0.0.1:${port}`

let list
try {
  list = await (await fetch(`${base}/json`)).json()
} catch (err) {
  console.error(`连不上 ${base}/json —— 构建进程是不是没带 --inspect，或者已经退出了？`)
  console.error(String(err))
  process.exit(2)
}
const target = list.find((t) => t.webSocketDebuggerUrl)
if (!target) {
  console.error("inspector 上没有可调试目标")
  process.exit(2)
}

const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  ws.onopen = () => res()
  ws.onerror = (e) => rej(e)
})

let seq = 0
const pending = new Map()
const scriptUrls = new Map() // scriptId -> 文件路径（Debugger.scriptParsed 事件里带的）
const send = (method, params = {}) =>
  new Promise((res) => {
    const id = ++seq
    pending.set(id, res)
    ws.send(JSON.stringify({ id, method, params }))
  })

ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg.result ?? msg)
    pending.delete(msg.id)
    return
  }
  if (msg.method === "Debugger.scriptParsed") {
    if (msg.params.url) scriptUrls.set(msg.params.scriptId, msg.params.url)
    return
  }
  if (msg.method === "Debugger.paused") {
    console.log(`\n=== 已暂停（reason=${msg.params.reason}）JS 调用栈 ===`)
    const frameLoc = (f) => {
      const { lineNumber, columnNumber, scriptId } = f.location
      const url = f.url || scriptUrls.get(scriptId) || `scriptId=${scriptId}`
      return `${url}:${lineNumber + 1}:${columnNumber + 1}`
    }
    msg.params.callFrames.slice(0, 40).forEach((f, i) => {
      console.log(`${String(i).padStart(2)}  ${f.functionName || "(anonymous)"}  @ ${frameLoc(f)}`)
    })
    process.exit(0)
  }
}

await send("Debugger.enable")

if (profileSeconds > 0) {
  await send("Profiler.enable")
  await send("Profiler.setSamplingInterval", { interval: 1000 })
  await send("Profiler.start")
  console.log(`[info] 采样 ${profileSeconds}s ...`)
  await new Promise((r) => setTimeout(r, profileSeconds * 1000))
  const { profile } = await send("Profiler.stop")
  const byId = new Map(profile.nodes.map((n) => [n.id, n]))
  const total = profile.nodes.reduce((a, n) => a + (n.hitCount ?? 0), 0) || 1
  const top = [...profile.nodes].sort((a, b) => (b.hitCount ?? 0) - (a.hitCount ?? 0)).slice(0, 20)
  console.log(`\n=== CPU 热点（总采样 ${total}）===`)
  for (const n of top) {
    if (!n.hitCount) continue
    const cf = byId.get(n.id)?.callFrame ?? {}
    console.log(
      `${((n.hitCount / total) * 100).toFixed(1).padStart(5)}%  ${cf.functionName || "(anonymous)"}  @ ${cf.url || "(native)"}:${(cf.lineNumber ?? -1) + 1}`,
    )
  }
  process.exit(0)
}

console.log(`[info] 已连上 127.0.0.1:${port}，发送 Debugger.pause ...`)
await send("Debugger.pause")
setTimeout(() => {
  console.error("[warn] 10 秒内没等到 paused 事件；改用 DevTools 的 Pause 按钮，或试 --profile 8")
  process.exit(3)
}, 10000)
