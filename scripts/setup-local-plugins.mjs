#!/usr/bin/env node
/**
 * 本地插件一键脚本：安装依赖 -> 构建(tsup) -> 接入 quartz5/.quartz/plugins(junction)
 *
 * 背景：quartz 的 loader 在安装「本地路径插件」时用 fs.symlinkSync(repo, dest, "dir")，
 * 而 Windows 非管理员 / 未开开发者模式下这一步会 EPERM 失败，插件被静默跳过（不生效）。
 * 见 QUARTZ5-COMMANDS.md §六 末段。本脚本改用 **junction**（无需特权），并在构建前
 * 幂等地补好，避免每次手动 mklink。
 *
 * 用法（在仓库根目录执行）：
 *   node scripts/setup-local-plugins.mjs                  # 处理 plugins-local 下所有含 package.json 的插件
 *   node scripts/setup-local-plugins.mjs --force          # 强制重装依赖 + 重新构建 + 重建 junction
 *   node scripts/setup-local-plugins.mjs --build-only     # 只安装 + 构建，不动 junction
 *   node scripts/setup-local-plugins.mjs --link-only      # 只建 junction，不构建
 *   node scripts/setup-local-plugins.mjs --only=graph-pro,search-pro
 *   node scripts/setup-local-plugins.mjs --exclude=content-meta-pro
 *   node scripts/setup-local-plugins.mjs --config          # 只处理 quartz5/quartz.config.yaml 引用的本地插件
 *   node scripts/setup-local-plugins.mjs --config=path/to/quartz.config.yaml
 *
 * 退出码：0 全部成功；1 存在失败项。
 */
import fs from "node:fs"
import path from "node:path"
import { execSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, "..")
const PLUGINS_LOCAL = path.join(REPO_ROOT, "plugins-local")
const PLUGINS_CACHE = path.join(REPO_ROOT, "quartz5", ".quartz", "plugins")
const DEFAULT_CONFIG = path.join(REPO_ROOT, "quartz5", "quartz.config.yaml")

// ---------------------------------------------------------------- 参数解析
const rawArgs = process.argv.slice(2)
const hasFlag = (...names) => names.some((n) => rawArgs.includes(`--${n}`))
function getOpt(name) {
  const idx = rawArgs.findIndex((a) => a === `--${name}` || a.startsWith(`--${name}=`))
  if (idx === -1) return undefined
  const hit = rawArgs[idx]
  if (hit.includes("=")) return hit.slice(hit.indexOf("=") + 1)
  const next = rawArgs[idx + 1]
  return next && !next.startsWith("--") ? next : ""
}
const parseList = (v) =>
  new Set(
    String(v ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  )

if (hasFlag("help", "h")) {
  console.log(fs.readFileSync(fileURLToPath(import.meta.url), "utf8").split("\n").slice(1, 22).join("\n"))
  process.exit(0)
}

const FORCE = hasFlag("force")
const BUILD_ONLY = hasFlag("build-only")
const LINK_ONLY = hasFlag("link-only")
const ONLY = parseList(getOpt("only"))
const EXCLUDE = parseList(getOpt("exclude"))
const configRaw = getOpt("config")
const USE_CONFIG = configRaw !== undefined
const CONFIG_PATH =
  configRaw === undefined ? DEFAULT_CONFIG : configRaw ? path.resolve(REPO_ROOT, configRaw) : DEFAULT_CONFIG

// ---------------------------------------------------------------- 终端着色
const useColor = !hasFlag("no-color") && process.stdout.isTTY
const paint = (code) => (s) => (useColor ? `\x1b[${code}m${s}\x1b[0m` : s)
const green = paint(32)
const red = paint(31)
const yellow = paint(33)
const cyan = paint(36)
const dim = paint(2)

const ok = (s) => green(s)
const bad = (s) => red(s)
const warn = (s) => yellow(s)
const step = (s) => cyan(s)
const info = (s) => dim(s)

// ---------------------------------------------------------------- 工具函数
function listPluginDirs() {
  if (!fs.existsSync(PLUGINS_LOCAL)) return []
  return fs
    .readdirSync(PLUGINS_LOCAL, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort()
}

function hasPackageJson(name) {
  return fs.existsSync(path.join(PLUGINS_LOCAL, name, "package.json"))
}

/** 从一份 quartz 配置文件里提取所有 ../plugins-local/<name> 的插件名 */
function readConfigLocalNames(configPath) {
  const names = new Set()
  if (!fs.existsSync(configPath)) return names
  const text = fs.readFileSync(configPath, "utf8")
  const re = /source:\s*['"]?[^'"\s]*[\\/]plugins-local[\\/]([^'"\s#]+)/g
  let m
  while ((m = re.exec(text))) names.add(m[1].replace(/[\\/]+$/, ""))
  return names
}

function norm(p) {
  return path.resolve(p).toLowerCase()
}

function removeLink(dest) {
  // Windows junction 用 rmdir；POSIX 目录软链用 unlink
  try {
    fs.rmdirSync(dest)
    return
  } catch {}
  try {
    fs.unlinkSync(dest)
    return
  } catch {}
  throw new Error(`无法移除已存在的链接：${dest}`)
}

/** 镜像 loader 的复用判定（gitLoader.ts:441-454）：是链接且 realpath 指向同一目标 => 复用 */
function ensureJunction(name, target) {
  fs.mkdirSync(PLUGINS_CACHE, { recursive: true })
  const dest = path.join(PLUGINS_CACHE, name)

  let st = null
  try {
    st = fs.lstatSync(dest)
  } catch {}

  if (st) {
    if (st.isSymbolicLink()) {
      let same = false
      try {
        same = norm(fs.realpathSync(dest)) === norm(fs.realpathSync(target))
      } catch {}
      if (same && !FORCE) return "reuse"
      removeLink(dest)
      fs.symlinkSync(target, dest, process.platform === "win32" ? "junction" : "dir")
      return "relink"
    }
    // 真实目录（通常是社区插件被下到同名目录）：默认不动，避免误删
    if (!FORCE) return "skip-real-dir"
    fs.rmSync(dest, { recursive: true, force: true })
  }

  fs.symlinkSync(target, dest, process.platform === "win32" ? "junction" : "dir")
  return st ? "relink" : "create"
}

function runNpm(command, cwd) {
  execSync(command, { cwd, stdio: "inherit", shell: true })
}

// ---------------------------------------------------------------- 目标筛选
const allDirs = listPluginDirs()
const buildable = allDirs.filter(hasPackageJson)
const noPackage = allDirs.filter((n) => !hasPackageJson(n))

const defaultConfigNames = readConfigLocalNames(DEFAULT_CONFIG) // 仅用于信息提示

let targets = buildable
if (USE_CONFIG) {
  const cfgNames = readConfigLocalNames(CONFIG_PATH)
  targets = targets.filter((n) => cfgNames.has(n))
  const missing = [...cfgNames].filter((n) => !fs.existsSync(path.join(PLUGINS_LOCAL, n)))
  if (missing.length) {
    console.log(warn(`⚠ 配置 ${path.relative(REPO_ROOT, CONFIG_PATH)} 引用了不存在的本地插件：${missing.join(", ")}`))
  }
}
if (ONLY.size) targets = targets.filter((n) => ONLY.has(n))
if (EXCLUDE.size) targets = targets.filter((n) => !EXCLUDE.has(n))

// ---------------------------------------------------------------- 主流程
console.log(cyan("== 本地插件 构建 + junction =="))
console.log(info(`仓库根目录 : ${REPO_ROOT}`))
console.log(info(`插件源目录 : ${PLUGINS_LOCAL}`))
console.log(info(`接入目录   : ${PLUGINS_CACHE}`))
console.log(info(`模式       : ${[FORCE && "force", BUILD_ONLY && "build-only", LINK_ONLY && "link-only", USE_CONFIG && "config-only"].filter(Boolean).join(", ") || "默认(按需)"}`))
console.log(info(`目标插件   : ${targets.length ? targets.join(", ") : "(无)"}`))
console.log("")

const failures = []
const summary = []

for (const name of targets) {
  const dir = path.join(PLUGINS_LOCAL, name)
  const steps = []
  console.log(cyan(`▶ ${name}`))
  try {
    if (!LINK_ONLY) {
      const hasModules = fs.existsSync(path.join(dir, "node_modules"))
      if (FORCE || !hasModules) {
        console.log(step("   · npm install"))
        runNpm("npm install", dir)
        steps.push("install")
      } else {
        steps.push("deps:ok")
      }

      const hasDist = fs.existsSync(path.join(dir, "dist"))
      if (FORCE || !hasDist) {
        console.log(step("   · npm run build"))
        runNpm("npm run build", dir)
        steps.push("build")
      } else {
        steps.push("dist:ok")
      }
    }

    if (!BUILD_ONLY) {
      const r = ensureJunction(name, dir)
      const label =
        r === "create"
          ? ok("link:create")
          : r === "reuse"
            ? ok("link:reuse")
            : r === "relink"
              ? ok("link:relink")
              : warn("link:skip(real-dir)")
      steps.push(label)
      if (r === "create" || r === "relink") {
        console.log(step(`   · junction -> ${dir}`))
      }
    }
    console.log(`   ${ok("✓")} ${steps.join("  ")}`)
    if (!USE_CONFIG && !defaultConfigNames.has(name)) {
      console.log(info(`   (提示：未被 quartz5/quartz.config.yaml 引用，junction 后仍不会生效，除非配置里启用)`))
    }
    summary.push({ name, steps, failed: false })
  } catch (err) {
    console.log(`   ${bad("✗ 失败")} ${err && err.message ? err.message : err}`)
    failures.push(name)
    summary.push({ name, steps, failed: true })
  }
  console.log("")
}

// ---------------------------------------------------------------- 汇总
if (noPackage.length) {
  console.log(warn(`⚠ 以下目录没有 package.json（空/未初始化），已跳过：${noPackage.join(", ")}`))
}
console.log(cyan("== 结果 =="))
for (const s of summary) {
  console.log(`  ${s.failed ? bad("✗") : ok("✓")} ${s.name.padEnd(22)} ${s.steps.join("  ")}`)
}
if (failures.length) {
  console.log(bad(`\n共 ${failures.length} 个失败：${failures.join(", ")}`))
  process.exit(1)
}
console.log(ok(`\n全部完成（${summary.length} 个插件）。`))
