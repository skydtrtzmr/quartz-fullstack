import fs from "node:fs"
import path from "node:path"

const root = path.resolve(import.meta.dirname, "..")
const P = (...a) => path.join(root, ...a)
const pl = P("plugins-local")

const NODE_BUILTINS = new Set(["fs", "path", "util", "os", "url", "crypto", "child_process", "events", "stream", "buffer", "module", "process", "assert"])
const strict = /^\s*(?:import\s+.*?\s+from|export\s+.*?\s+from|import)\s*["']([^"'./][^"']*)["']/gm

for (const name of fs.readdirSync(pl)) {
  const dist = path.join(pl, name, "dist")
  if (!fs.existsSync(dist)) {
    console.log(name.padEnd(24), "(no dist)")
    continue
  }
  const bare = new Set()
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, e.name)
      if (e.isDirectory()) walk(full)
      else if (e.name.endsWith(".js")) {
        const txt = fs.readFileSync(full, "utf8")
        for (const m of txt.matchAll(strict)) {
          const spec = m[1]
          const b = spec.split("/")[0]
          if (NODE_BUILTINS.has(b) || b.startsWith("node:")) continue
          const pkg = spec.startsWith("@") ? spec.split("/").slice(0, 2).join("/") : b
          bare.add(pkg)
        }
      }
    }
  }
  walk(dist)
  console.log(name.padEnd(24), [...bare].join(", ") || "(none)")
}
