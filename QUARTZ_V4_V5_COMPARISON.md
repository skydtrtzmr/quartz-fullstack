# Quartz v4 (client) vs v5 (quartz-5) 详细对比分析

## 1. 项目定位

| 维度 | v4 (client) | v5 (quartz-5) |
|------|-------------|---------------|
| **版本** | 4.5.2 | 5.0.0 |
| **定位** | 单一完整项目 | 核心框架 + 插件生态 |
| **架构** | 单体架构 | 微内核 + 外部插件 |
| **状态** | 你的定制版本，有大量自定义功能 | 官方最新版，社区插件生态 |

## 2. 架构差异

### 2.1 插件系统

**v4 (client)**
```typescript
// 内置插件，直接引用
import * as Plugin from "./quartz/plugins"

Plugin.GraphLocalEmitter({
  depth: 1,
  showTags: true,
})
```

**v5 (quartz-5)**
```yaml
# 从 GitHub 加载外部插件
plugins:
  - source: github:quartz-community/graph
    enabled: true
    options:
      localGraph:
        depth: 1
```

**关键变化**：
- v4: 插件是核心代码的一部分，直接 `import`
- v5: 插件从 npm/GitHub 动态安装，有独立的 loader 系统
- v5 新增 `quartz.lock.json` 锁定插件版本

### 2.2 配置系统

**v4 (client)**
- 格式: TypeScript (`quartz.config.ts`)
- 特点: 可以写逻辑代码（你的版本有运行时 JSON 覆盖机制）
- 位置: 项目根目录

**v5 (quartz-5)**
- 格式: YAML (`quartz.config.default.yaml`)
- 特点: 声明式，有 JSON Schema 校验
- 位置: 项目根目录，支持模板继承

**v4 特有功能**（你添加的）：
```typescript
// 运行时 JSON 覆盖
if (settingsPath) {
  const configJsonPath = path.join(settingsPath, "config.json")
  Object.assign(config.configuration, override)
}
```

### 2.3 Graph 组件

| 特性 | v4 (client) | v5 (quartz-5) |
|------|-------------|---------------|
| **位置** | `quartz/components/Graph.tsx` | 外部插件 `quartz-community/graph` |
| **脚本** | `graph.inline.ts`, `graph2.inline.ts` | 在插件内部 |
| **预计算** | ✅ 你实现的 `GraphLocalEmitter` | ❌ 无 |
| **多域名支持** | ✅ 有 `basePath` 处理 | 未知 |

**v4 特有优化**（你的文档 `graph-loading-optimization.md`）：
- 预加载 fetchData
- 优化 BFS 邻域计算
- 降低 Simulation 收敛标准
- 世代计数器防竞态（计划中）

### 2.4 SPA 路由

**v4 (client)** - 你修改过的版本：
```typescript
// 你添加的（已注释）
// - 首屏加载守护
// - toast 提示
// - 捕获阶段拦截 click
// - __firstScreenLoaded 全局标志
```

**v5 (quartz-5)** - 原版：
```typescript
// 标准的 cleanup 机制
const cleanupFns: Set<(...args: any[]) => void> = new Set()
window.addCleanup = (fn) => cleanupFns.add(fn)

// navigate 时调用 cleanup
function _navigate(url, isBack) {
  cleanupFns.forEach((fn) => fn())
  cleanupFns.clear()
  // ...
}
```

## 3. 目录结构对比

### v4 (client)
```
client/
├── quartz/
│   ├── components/         # 组件齐全
│   │   ├── Graph.tsx       # 内置 Graph
│   │   ├── Explorer.tsx
│   │   ├── Explorer2.tsx
│   │   ├── Search.tsx
│   │   ├── Search2.tsx
│   │   └── ...
│   ├── plugins/
│   │   ├── emitters/       # 包含 GraphLocalEmitter
│   │   │   ├── graphLocal.tsx
│   │   │   └── graphLocal.test.ts
│   │   └── ...
│   └── ...
├── docs/
│   ├── graph-loading-optimization.md  # 你的分析文档
│   └── upgrading.md
└── quartz.config.ts        # TypeScript 配置
```

### v5 (quartz-5)
```
quartz-5/
├── quartz/
│   ├── components/         # 核心组件（无 Graph）
│   │   ├── frames/         # 新增：页面框架
│   │   └── scripts/
│   │       └── spa.inline.ts   # 无拦截逻辑
│   ├── plugins/
│   │   ├── loader/         # 新增：插件加载器
│   │   │   ├── config-loader.ts
│   │   │   └── install-plugins.ts
│   │   └── emitters/       # 简化版
│   ├── cli/
│   │   └── templates/      # 项目模板
│   └── ...
├── docs/
│   ├── features/
│   │   └── graph view.md   # 指向社区插件
│   └── plugins/
│       └── Graph.md        # 社区插件文档
├── quartz.config.default.yaml   # YAML 配置
└── quartz.lock.json        # 插件版本锁定
```

## 4. 功能差异

### v4 特有功能

1. **局部图谱预计算** (`GraphLocalEmitter`)
   - 构建时为每个页面生成局部图谱 JSON
   - SHA-256 目录分片
   - 前端优先加载预计算数据

2. **多域名支持**
   - `basePath` 处理子路径部署
   - 运行时 JSON 配置覆盖

3. **虚拟节点索引**
   - 处理 Obsidian 中的悬空链接
   - 动态计算虚拟节点

4. **自定义优化**
   - 预加载 fetchData
   - BFS 邻域计算优化
   - Simulation 快速收敛参数

### v5 特有功能

1. **社区插件生态**
   - 从 GitHub/npm 安装插件
   - 版本锁定机制
   - 插件市场支持

2. **YAML 配置**
   - JSON Schema 校验
   - 模板继承系统

3. **Worker 模式**
   - `bootstrap-worker.mjs`
   - 并行构建支持

4. **加密页面** (`EncryptedPages`)
   - 密码保护页面
   - 客户端解密

5. **Canvas 支持**
   - `.canvas` 文件渲染

## 5. 代码质量对比

### SPA inline script

| 特性 | v4 (client) | v5 (quartz-5) |
|------|-------------|---------------|
| **行数** | ~289 行（含注释代码） | 214 行 |
| **拦截逻辑** | 有（已注释） | 无 |
| **首屏守护** | 有（已注释） | 无 |
| **复杂度** | 较高（自定义逻辑多） | 简洁 |

### Graph inline script

| 特性 | v4 (client) | v5 (quartz-5) |
|------|-------------|---------------|
| **文件数** | 2个 (`graph.inline.ts`, `graph2.inline.ts`) | 在插件内部 |
| **行数** | ~680 + ~1000 行 | 未知 |
| **对象池** | ✅ 有 | 未知 |
| **预计算支持** | ✅ 有 | ❌ 无 |

## 6. 迁移建议

### 如果你要从 v4 迁移到 v5

**可以保留的功能**：
- Graph 预计算（需要提交给 quartz-community/graph 插件）
- 多域名 basePath 支持
- 虚拟节点索引

**需要重新实现的**：
- 运行时 JSON 配置覆盖 → 改为 YAML 配置
- 首屏加载守护 → 不推荐，应考虑优化性能本身
- 自定义 emitter → 改为社区插件

### 如果你要继续使用 v4

建议基于 `graph.inline.ts` 而非 `graph2.inline.ts`，并添加：
1. 世代计数器防竞态
2. 优化的 BFS 邻域计算
3. 保持预计算系统

## 7. 关键文件对比表

| 文件 | v4 (client) | v5 (quartz-5) | 差异 |
|------|-------------|---------------|------|
| `spa.inline.ts` | 有拦截逻辑（注释） | 原版 | 你的修改 vs 官方 |
| `graph.inline.ts` | 有 | 无（外部插件） | 内置 vs 社区 |
| `quartz.config` | `.ts` | `.yaml` | TS vs YAML |
| `Graph.tsx` | 有 | 无 | 内置 vs 外部 |
| `Explorer2.tsx` | 有 | 未知 | v4 特有 |
| `Search2.tsx` | 有 | 未知 | v4 特有 |
| `VirtualNodePage` | 有 | 未知 | v4 特有 |
| 插件加载器 | 无 | 有 | v5 新增 |

## 8. 总结

**v4 (client)** 是你的**高度定制版本**，特点：
- 针对图谱加载做了大量优化
- 支持预计算局部图谱
- 多域名部署支持
- 有 SPA 拦截逻辑（已注释）

**v5 (quartz-5)** 是**官方现代化版本**，特点：
- 社区插件生态
- 更简洁的架构
- 更好的可扩展性
- Graph 功能依赖外部插件

**你的选择**：
1. 继续维护 v4，修复竞态问题
2. 迁移到 v5，将预计算功能贡献给社区
3. 混合方案：v5 核心 + v4 的 Graph 预计算插件
