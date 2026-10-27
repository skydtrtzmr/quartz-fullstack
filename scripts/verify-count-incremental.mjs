/** 历史计数增量回归脚本。需要特定的 nested-add 基线及对应构建缓存，不是可重复的一键测试。
 * 操作范围仅限 count-regression-demo；会新增、修改、移动、删除该测试域的输入文件并构建。
 * 基线与历史结果见 document/计数增量回归验证说明.md。本次整理未重新执行测试。
 */
import fs from "node:fs"
import path from "node:path"
import { spawnSync } from "node:child_process"
import assert from "node:assert/strict"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("../", import.meta.url))
const domain = "count-regression-demo"
const input = path.join(root, "input", domain)
const output = path.join(root, "output", domain)
const results = []
const resultDir = path.join(root, ".task-builds", domain)
function build(stage) {
  const run = spawnSync(process.execPath, ["--no-deprecation", "./quartz/bootstrap-cli.mjs", "build", "--sqlite", "--cacheDir", `../cache/${domain}`, "-d", `../input/${domain}`, "-o", `../output/${domain}`, "--settings", `../settings/${domain}`, "--concurrency=2"], { cwd: path.join(root, "quartz5"), encoding: "utf8" })
  fs.writeFileSync(path.join(resultDir, `${stage}.log`), run.stdout + run.stderr)
  assert.equal(run.status, 0, run.stdout + run.stderr)
}
function check(stage, folders, missing) {
  for (const [folder, count] of Object.entries(folders)) {
    const html = fs.readFileSync(path.join(output, folder, "index.html"), "utf8")
    assert.ok(html.includes(`此文件夹下有${count}条笔记。`), `${stage}: ${folder} count`)
    if (folder === "project") assert.ok(html.includes("目录正文必须保留。"))
    if (folder === "project/nested") assert.ok(html.includes("嵌套目录正文必须保留。"))
  }
  const graph = JSON.parse(fs.readFileSync(path.join(output, "graph/dimensions/type/未分类.json"), "utf8"))
  assert.equal(graph.matched.length, missing, `${stage}: dimension count`)
  assert.ok(graph.matched.every(item => !item.slug.endsWith("/") && !item.slug.endsWith("/index")))
  results.push({ stage, folders, missing, passed: true })
  console.log(`${stage}: passed`)
}
check("nested-add", { project: 3, "project/nested": 2 }, 3)
fs.mkdirSync(resultDir, { recursive: true })
fs.writeFileSync(path.join(input, "project/e.md"), "---\ntitle: 新增同层项目 E\n---\n同层新增。\n")
build("direct-add")
check("direct-add", { project: 4, "project/nested": 2 }, 4)
fs.writeFileSync(path.join(input, "project/nested/d.md"), "---\ntitle: 修改分类 D\ntype: 专项\n---\n修改分类。\n")
build("classification-change")
check("classification-change", { project: 4, "project/nested": 2 }, 3)
fs.renameSync(path.join(input, "project/nested/d.md"), path.join(input, "people/d.md"))
build("move")
check("move", { project: 4, "project/nested": 1, people: 2 }, 3)
fs.unlinkSync(path.join(input, "people/d.md"))
fs.unlinkSync(path.join(input, "project/e.md"))
build("delete")
check("delete", { project: 3, "project/nested": 1, people: 1 }, 2)
fs.writeFileSync(path.join(resultDir, "results.json"), JSON.stringify(results, null, 2))
