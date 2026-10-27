import test from "node:test"
import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { synchronize } from "./sync-domain-configs.mjs"

const YAML = createRequire(new URL("../quartz5/package.json", import.meta.url))("yaml")

test("sync preserves domain values while updating shared plugin structure", () => {
  const template = YAML.parseDocument(`configuration:
  pageTitle: template
  graph:
    precomputeLocal: true
    local: {maxVisibleNodes: 500, fontSize: 0.75, showTags: true}
    global: {folders: [template-folder]}
  properties:
    branches: {default: [], folders: {Assets: [download]}}
plugins:
  - source: graph-pro
    processing: false
    layout: {position: header, component: Overlay}
  - source: graph-pro
    layout: {position: right, component: Local}
    options: {defaultOption: true}
  - source: navigation-history-pro
    enabled: true
    layout: {position: header, priority: 1}
layout: {groups: {toolbar: {direction: row}}}
`)
  const domain = YAML.parseDocument(`configuration:
  pageTitle: domain
  graph:
    precomputeLocal: false
    local: {maxVisibleNodes: 40, fontSize: 0, showTags: false}
    global: {folders: []}
  properties:
    branches: {default: [owner], folders: {project: [status, owner]}}
plugins:
  - source: graph-pro
    enabled: false
    options: {customOption: 0}
    layout: {position: left, component: Local}
  - source: graph-pro
    layout: {position: beforeBody, component: Overlay}
  - source: domain-extra
    enabled: true
layout: {groups: {oldGroup: {direction: row}}}
`)
  const original = domain.toJS()
  const result = synchronize(template, domain)
  const data = result.toJS()
  assert.deepEqual(domain.toJS(), original)
  assert.deepEqual(data.configuration, original.configuration)
  assert.equal(data.plugins[0].processing, false)
  assert.deepEqual(data.plugins[0].layout, { position: "header", component: "Overlay" })
  assert.equal(data.plugins[1].enabled, false)
  assert.deepEqual(data.plugins[1].options, { customOption: 0, defaultOption: true })
  assert.deepEqual(data.plugins[2], template.toJS().plugins[2])
  assert.equal(data.plugins[3].source, "domain-extra")
  assert.deepEqual(data.layout, template.toJS().layout)
  assert.equal(synchronize(template, result).toString(), result.toString())
})

test("ambiguous duplicate components are rejected before writing", () => {
  const doc = YAML.parseDocument(`configuration: {}
plugins: [{source: duplicate}, {source: duplicate}]
layout: {}
`)
  assert.throws(() => synchronize(doc, doc), /重复/)
})
