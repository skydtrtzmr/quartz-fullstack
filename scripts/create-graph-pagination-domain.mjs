import { mkdir, readFile, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import path from "node:path"

// node scripts/create-graph-pagination-domain.mjs [每组成员数=200]
// grouped / plain 数据相同，仅分类规则不同。不会修改 test1 的内容。
const perGroup = Number(process.argv[2] ?? 200)
if (!Number.isInteger(perGroup) || perGroup < 12) throw new Error("每组成员数必须是 >=12 的整数")
const root = fileURLToPath(new URL("../", import.meta.url))
const domain = "graph-demo"
const input = path.join(root, "input", domain)
const settings = path.join(root, "settings", domain)
await mkdir(settings, { recursive: true })
let config = await readFile(path.join(root, "settings/test1/quartz.config.yaml"), "utf8")
config = config.replace(/^  pageTitle:.*$/m, "  pageTitle: 图谱分页演示")
  .replace(/^  baseUrl:.*$/m, `  baseUrl: localhost/${domain}`)
  .replace(/^      folders: \{Proj:.*$/m, "      folders: {grouped: [演示分组], plain: []}")
  .replace(/        expandBatchSize: \d+/, "        expandBatchSize: 5\n        # 首屏预算 40，后续允许主动分批加载；插件默认首屏 500。\n        maxVisibleNodes: 40\n        loadBatchSize: 10")
await writeFile(path.join(settings, "quartz.config.yaml"), config)
await mkdir(input, { recursive: true })
await writeFile(path.join(input, "index.md"), `---
title: 图谱分页演示
---

相同的 ${perGroup * 5} 个成员，比较聚合分批与无聚合的首屏限量加载。

- [[grouped/index|有聚合：五组独立加载]]
- [[plain/index|无聚合：首屏限量与继续加载]]

首屏最多 40 个节点（包含聚合节点），后续主动加载可以超过 40。聚合每批 5 项，无聚合每批 10 项。
`)
for (const folder of ["grouped", "plain"]) {
  const directory = path.join(input, folder)
  await mkdir(directory, { recursive: true })
  await writeFile(path.join(directory, "index.md"), `---
title: ${folder === "grouped" ? "有聚合 · 五组分批" : "无聚合 · 首屏限量"}
---

共 ${perGroup * 5} 个成员。${folder === "grouped" ? "依次展开 A～E 五组，在底部分类条选择要加载的组。每次加载 5 项，图中节点超过首屏预算 40 后仍可继续加载，各组进度独立。" : "分类规则为空。首屏仅显示 40 个节点，点击“当前图谱”的加载按钮，每次再显示 10 个节点，可以超过首屏预算。"}
`)
  for (const group of ["A", "B", "C", "D", "E"]) {
    for (let index = 1; index <= perGroup; index++) {
      const name = `${group}-${String(index).padStart(4, "0")}`
      await writeFile(path.join(directory, `${name}.md`), `---
title: 演示 ${name}
演示分组: ${group}组
---

图谱分页演示成员 ${name}。
${group === "A" && index === 1 ? `\n[[${folder}/a-0002]]\n[[未创建的演示节点]]\n[[_dimensions/演示分组/a组]]\n` : ""}
`)
    }
  }
}
console.log(`${domain}: grouped and plain each have ${perGroup * 5} members; maxVisibleNodes=40, expandBatchSize=5`)
