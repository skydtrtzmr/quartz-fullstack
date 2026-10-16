import { mkdir, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import path from "node:path"

// 独立演示目录：5 个聚合，每组 12 项，配合 test1 expandBatchSize: 5。
const directory = fileURLToPath(new URL("../input/test1/batch-demo/", import.meta.url))
await mkdir(directory, { recursive: true })
await writeFile(path.join(directory, "index.md"), `---
title: 五组分批演示
---

同时展开图谱中的 A、B、C、D、E 五个聚合节点，每组有 12 个演示成员，每批展开 5 个。
图谱下方每一行的“加载更多”只加载对应分类，其他分类进度不变。
`)
for (const group of ["A", "B", "C", "D", "E"]) {
  for (let index = 1; index <= 12; index++) {
    const name = `${group}-${String(index).padStart(2, "0")}`
    await writeFile(path.join(directory, `${name}.md`), `---
title: 演示 ${name}
演示分组: ${group}组
---

分批展开演示节点 ${name}。
`)
  }
}
console.log(`Created 5 groups × 12 demo members in ${directory}`)
