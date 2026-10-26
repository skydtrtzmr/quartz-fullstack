// One-time source migration, not a server-side compatibility path.
// Run from quartz5: node --import tsx ../scripts/migrate-global-graph.mts
import fs from "node:fs"
import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { resolveGraphViewConfig } from "../plugins-local/graph-pro/src/options"
import { sharedGraphOptions } from "../quartz5/quartz/plugins/loader/shared-graph"
const require = createRequire(new URL("../quartz5/package.json", import.meta.url))
const YAML = require("yaml")
const root = new URL("../", import.meta.url)
const keys = ["maxVisibleNodes", "expandBatchSize", "loadBatchSize", "coreMinLinks"]
const views = { local: "localGraph", folder: "folderGraph", dimension: "dimensionGraph", global: "globalGraph" }
const files = ["quartz5/quartz.config.yaml", ...fs.readdirSync(new URL("settings/", root), { withFileTypes: true })
  .filter(x => x.isDirectory()).map(x => `settings/${x.name}/quartz.config.yaml`)
  .filter(x => fs.existsSync(new URL(x, root)))]
for (const file of files) {
  const path = new URL(file, root), raw = fs.readFileSync(path, "utf8"), doc = YAML.parseDocument(raw)
  const entry = doc.get("plugins").items.find((p: any) => String(p.get("source")).endsWith("/graph-pro"))
  if (!entry) continue
  const opts = entry.get("options"), original = opts.toJSON()
  if (doc.getIn(["configuration", "graph"])) {
    sharedGraphOptions(doc.getIn(["configuration", "graph"]).toJSON(), original)
    continue
  }
  const before = Object.fromEntries(Object.keys(views).map(view => [view, resolveGraphViewConfig(original, view as any)]))
  const defaults = Object.fromEntries(keys.map(key => [key, original.graphDefaults?.[key] ?? original.graph?.[key] ?? ({ maxVisibleNodes: 500, expandBatchSize: 20, loadBatchSize: 100, coreMinLinks: 0 } as any)[key]]))
  const policy: any = { defaults }
  for (const [view, source] of Object.entries(views)) {
    const values: any = {}
    for (const key of keys) if ((before as any)[view][key] !== defaults[key]) values[key] = (before as any)[view][key]
    if (view === "global") {
      values.folders = original.globalGraph?.folders ?? []
      values.coreAggregationMaxLevels = original.globalGraph?.coreAggregationMaxLevels ?? 2
    }
    if (Object.keys(values).length) policy[view] = values
  }
  for (const section of ["graph", "graphDefaults", ...Object.values(views)]) {
    const node = opts.get(section)
    if (!node) continue
    for (const key of [...keys, ...(section === "globalGraph" ? ["folders", "coreAggregationMaxLevels"] : [])]) node.delete(key)
    if (!node.items.length) opts.delete(section)
  }
  const updated = sharedGraphOptions(policy, opts.toJSON())
  for (const view of Object.keys(views)) assert.deepEqual(resolveGraphViewConfig(updated, view as any), (before as any)[view], `${file}: ${view} changed`)
  doc.setIn(["configuration", "graph"], policy)
  const printed = opts.clone(); delete printed.anchor
  const replacement = YAML.stringify(printed).trimEnd().split("\n").map((x: string) => "      " + x).join("\n")
  let output = raw.slice(0, opts.range[0]) + replacement.trimStart() + "\n" + raw.slice(opts.range[2])
  const marker = output.indexOf("  defaultDateType:"); assert(marker > 0)
  const global = YAML.stringify(policy).trimEnd().split("\n").map((x: string) => "    " + x).join("\n")
  output = output.slice(0, marker) + "  # 四类图谱的业务参数；插件只保留渲染及构建细节。\n  graph:\n" + global + "\n" + output.slice(marker)
  assert.deepEqual(YAML.parse(output), doc.toJS(), file)
  fs.writeFileSync(path, output)
  console.log(file)
}
