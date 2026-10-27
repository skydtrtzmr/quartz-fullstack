#!/usr/bin/env node
/** 同步业务域 YAML 结构：保留业务值、目录规则、插件开关/选项；插件布局及处理标记跟随当前模板。 */
import fs from "node:fs"
import path from "node:path"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"
import { isDeepStrictEqual, parseArgs } from "node:util"

const root = fileURLToPath(new URL("../", import.meta.url))
const require = createRequire(new URL("../quartz5/package.json", import.meta.url))
const YAML = require("yaml")

// folders 中的目录名是业务数据，不从模板注入其他域的目录规则。
function fillMissing(template, current, location = "") {
  if (!YAML.isMap(template) || !YAML.isMap(current) || location.endsWith(".folders")) return current.clone()
  const result = current.clone()
  for (const pair of template.items) {
    const key = pair.key.value
    result.set(key, result.has(key)
      ? fillMissing(pair.value, result.get(key, true), `${location}.${key}`)
      : pair.value.clone())
  }
  return result
}

// 同源插件可注册多个组件；processing 是要同步的标记，不作为组件身份的一部分。
function pluginKey(plugin) {
  return JSON.stringify([plugin.get("source"), plugin.getIn(["layout", "component"]) ?? ""])
}

export function synchronize(template, domain) {
  const result = fillMissing(template.contents, domain.contents)
  const existing = domain.get("plugins").items
  const keys = existing.map(pluginKey)
  if (new Set(keys).size !== keys.length) throw new Error("重复的插件/组件条目，请先明确布局")
  const byKey = new Map(existing.map(plugin => [pluginKey(plugin), plugin]))
  const plugins = template.get("plugins").clone()
  plugins.items = plugins.items.map(base => {
    const current = byKey.get(pluginKey(base))
    if (!current) return base
    byKey.delete(pluginKey(base))
    const merged = fillMissing(base, current)
    for (const key of ["layout", "order", "processing"]) {
      if (base.has(key)) merged.set(key, base.get(key, true).clone())
      else merged.delete(key)
    }
    return merged
  })
  // 模板外插件不静默删除，保留在末尾。
  plugins.items.push(...Array.from(byKey.values(), plugin => plugin.clone()))
  result.set("plugins", plugins)
  result.set("layout", template.get("layout").clone())
  const output = domain.clone()
  output.contents = result
  return output
}

function readConfig(file) {
  const raw = fs.readFileSync(file, "utf8")
  const doc = YAML.parseDocument(raw)
  if (doc.errors.length) throw new Error(`${file}: ${doc.errors[0].message}`)
  if (!YAML.isMap(doc.get("configuration")) || !YAML.isSeq(doc.get("plugins")) || !YAML.isMap(doc.get("layout"))) {
    throw new Error(`${file}: 需要 configuration/plugins/layout 三段`)
  }
  return { raw, doc }
}

function main() {
  const { values } = parseArgs({ options: {
    write: { type: "boolean" }, check: { type: "boolean" }, domain: { type: "string", multiple: true },
  } })
  if (values.write && values.check) throw new Error("--write 与 --check 不能同时使用")
  const template = readConfig(path.join(root, "quartz5/quartz.config.yaml")).doc
  const settings = path.join(root, "settings")
  const names = fs.readdirSync(settings, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && fs.existsSync(path.join(settings, entry.name, "quartz.config.yaml")))
    .map(entry => entry.name).sort()
  for (const name of values.domain ?? []) if (!names.includes(name)) throw new Error(`业务域不存在: ${name}`)
  const selected = values.domain ? names.filter(name => values.domain.includes(name)) : names
  const changes = []
  for (const name of selected) {
    const file = path.join(settings, name, "quartz.config.yaml")
    const { raw, doc } = readConfig(file)
    const next = synchronize(template, doc)
    if (isDeepStrictEqual(next.toJS(), doc.toJS())) {
      console.log(`OK      ${name}`)
    } else {
      changes.push({ name, file, raw, next })
      console.log(`UPDATE  ${name}`)
    }
  }
  if (values.write && changes.length) {
    const backup = path.join(root, ".task-builds/config-sync", new Date().toISOString().replaceAll(":", "-"))
    fs.mkdirSync(backup, { recursive: true })
    for (const { name, raw } of changes) fs.writeFileSync(path.join(backup, `${name}.yaml`), raw)
    for (const { file, next } of changes) {
      const temporary = `${file}.sync-${process.pid}.tmp`
      try {
        fs.writeFileSync(temporary, next.toString({ lineWidth: 0, flowCollectionPadding: false }))
        fs.renameSync(temporary, file)
      } finally {
        if (fs.existsSync(temporary)) fs.unlinkSync(temporary)
      }
    }
    console.log(`已更新 ${changes.length} 个域，备份: ${backup}`)
  } else if (changes.length) {
    console.log(`${changes.length} 个域需要同步；使用 --write 应用。`)
    process.exitCode = 1
  } else {
    console.log(`${selected.length} 个域结构已同步。`)
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main() } catch (error) { console.error(error.message); process.exitCode = 1 }
}
