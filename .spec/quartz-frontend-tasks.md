# Quartz 前端研发任务清单

## ✅ 已完成

### P0 - 基础体验优化
- [x] **构建缓存问题**：新增页面后图谱没有自动重绘 - 已解决 ✅
  - 实现位置：`client/quartz/components/scripts/graph.inline.ts`
  - 修复内容：添加全局追踪变量（`activeSimulations`、`activeRafIds`）和强制清理函数

### P1 - 图谱核心功能
- [x] **图谱-边显示优化**：
  - [x] 增加有向边箭头（`showArrows` 配置，默认开启）- 配置文件：`client/quartz/components/Graph.tsx`
  - [x] 增加记录边名称（`sourceField`，追溯边的来源类型，显示正文引用或 YAML 属性）
  - [x] 边标签样式优化（字号跟随配置、描边提高可读性、分辨率优化防模糊）
  - [x] 展开/收起边缘节点时边标签正确创建和销毁
  - 实现位置：`client/quartz/components/scripts/graph2.inline.ts`

- [x] **图谱-节点中心数字徽章**：
  - [x] 全局图谱核心节点中心显示关联数量（配置 `countLabelMin`/`countLabelMaxDisplay`）
  - [x] 添加 `resolution` 解决数字模糊问题
  - [x] 悬浮到数字上触发节点高亮效果（颜色、光标一致）
  - [x] 点击数字可转发到节点触发展开/收起
  - 实现位置：`client/quartz/components/scripts/graph2.inline.ts`

- [x] **图谱-构建时优化**：
  - [x] 构建时预计算每个页面的局部图谱关联节点
  - [x] 按节点 ID 拆分为多个 JSON 文件（使用 MD5 哈希分片：`{md5(0,2)}/{md5(2,2)}/{slug}.json`）
  - [x] graph2.inline.ts 读取预计算数据，depth ≤ 2 时使用预计算，depth > 2 时回退到 BFS
  - 实现位置：`client/quartz/plugins/emitters/graphLocal.tsx`
  - 配置：可通过 `quartz.config.ts` 中 `graph.precomputeLocal` 开关控制

- [x] **首屏图谱竞态条件修复**：
  - [x] 添加全局追踪变量防止 D3 simulation 和 RAF 泄漏
  - [x] 新增 `forceStopAllSimulations()` 和 `cancelAllRafs()` 函数
  - [x] 修改 `cleanupLocalGraphs()` 在每次清理时强制停止旧资源
  - 实现位置：`client/quartz/components/scripts/graph.inline.ts`

### P2 - 搜索功能优化
- [x] **全文检索优化**：
  - [x] 支持复合检索（同时包含多个 `#` 标签或 `@` 属性）
  - [x] 添加 `-` 符号支持，用于排除指定内容
  - [x] 支持三种 YAML 查询模式：
    - `@key` - 搜索包含该键的文档
    - `@:value` - 搜索所有字段的值
    - `@key:value` - 搜索指定键值对
  - [x] 排除功能：`-#tag`、`-@key:value`、`-文本`
  - 实现位置：`client/quartz/components/scripts/search2.inline.ts`（第 602-685 行）

### P3 - 目录与链接优化
- [x] **反向链接按文件夹分组**：
  - [x] 按 slug 路径自动构建多级树形分组（根目录文件直接显示，子文件夹默认折叠）
  - [x] 总数 ≤ threshold（默认 20）时全部分组默认展开
  - [x] 总数 > threshold 时启用分批加载：根目录文件首批直接显示，各组展开后分批追加
  - [x] 组件总高度受限，滚动条在内部，不影响页面整体滚动
  - 实现位置：`client/quartz/components/Backlinks.tsx` + `client/quartz/components/styles/backlinks.scss`

- [x] **反向链接聚合分组**：
  - [x] 支持多级聚合：文件夹 + 多个 frontmatter 字段
  - [x] 配置文件：`settings/{domain}/layout.json` 的 `aggregation.backlinks` 节点
  - [x] 文件夹配置：
    - `folder.depth`: -1=完整层级, 0=禁用, 默认1
    - `folder.flatten`: true=扁平化, false=保留层级，默认true
  - [x] 字段配置：
    ```json
    "fields": [
      { "field": "date", "granularity": "year" },
      { "field": "客户" },
      { "field": "tags" }
    ]
    ```
  - [x] 字段显示格式：
    - `date`/`tags`：只显示值（如 "2024年"、"重要"）
    - 其他字段：显示 "键: 值"（如 "客户: 甲公司"）
  - [x] 日期格式化：支持字符串和 Date 对象，按 granularity 聚合（year/month/quarter）
  - 实现位置：`client/quartz/components/Backlinks.tsx` + `client/quartz.layout.ts`

- [x] **文件夹页分批加载**：
  - [x] `PageList` 组件支持 `batchLoad` 配置
  - [x] 文件夹页默认启用（首批 20 条，每次追加 20 条）
  - 实现位置：`client/quartz/components/PageList.tsx` + `client/quartz/components/scripts/pageList.inline.ts`

---

## 📋 常用配置速查

### 图谱边箭头显示
**文件**：`client/quartz/components/Graph.tsx`

```ts
const defaultOptions: GraphOptions = {
  localGraph: {
    showArrows: true,  // 局部图谱默认开启箭头
  },
  globalGraph: {
    showArrows: true,  // 全局图谱默认开启箭头
  },
}
```

### 反向链接组件总高度
**文件**：`client/quartz/components/styles/backlinks.scss`

```scss
.backlinks {
  // [HEIGHT-CONTROL] 关键：让反向链接组件在 sidebar 中占据所有剩余空间
  flex: 1 1 auto;
}

.backlinks > ul.backlinks-list {
  // [HEIGHT-CONTROL] 关键：在 .backlinks 内部占据剩余高度
  flex: 1 1 auto;
  // [HEIGHT-CONTROL] 关键：允许 flex item 被压缩，否则内容多时无法限制高度
  min-height: 0;
}
```

### 反向链接分批加载阈值
**文件**：`client/quartz/components/Backlinks.tsx`

```ts
const defaultOptions: BacklinksOptions = {
  threshold: 20,  // 总数超过此值时启用分批加载和默认折叠
}
```

### 局部图谱预计算配置
**文件**：`quartz.config.ts` 或 domain 的 `config.json`

```ts
graph: {
  precomputeLocal: true,  // 启用局部图谱预计算
  localDepth: 1,          // 预计算深度，默认 1
  fallbackToBfs: true,   // 当预计算数据不可用时回退到 BFS
}
```

### 反向链接聚合配置
**文件**：`settings/{domain}/layout.json`

```json
{
  "backlinks": {
    "hideWhenEmpty": false
  },
  "aggregation": {
    "backlinks": {
      "folder": {
        "depth": 1,
        "flatten": false
      },
      "fields": [
        { "field": "date", "granularity": "year" },
        { "field": "客户" },
        { "field": "tags" }
      ]
    }
  }
}
```

**配置说明**：
- `folder.depth`：
  - `-1`: 保留完整文件夹层级
  - `0`: 禁用文件夹聚合
  - `1`: 只保留第一级文件夹（默认）
- `folder.flatten`：
  - `true`: 扁平化所有文件夹到根级
  - `false`: 保留层级结构
- `fields`：按字段依次聚合，支持日期（date）和其他任意 frontmatter 属性
- `granularity`：日期粒度，可选 `year`/`month`/`quarter`

---

## 🔄 下一阶段建议（按优先级排序）

### 🔴 P0 - 图谱追踪展示（核心功能）
这是提升用户体验的关键功能，建议优先实现：

- [ ] **图谱-关联节点深度/广度控制**
  - 默认展示直接相关的 m 个节点、间接相关的 n 层节点（m、n 可配置）
  - 建议配置项：`localGraph.depth`、`globalGraph.maxConnections`

- [ ] **图谱-详情列表组件**
  - 图谱下方增加列表区域，展示与当前节点直接相关的节点详情
  - 支持点击列表项跳转到对应节点

- [ ] **图谱-关联追溯交互**
  - 用户可以点击边或节点继续追溯关联关系
  - 支持回退到上一级

### 🟡 P1 - 图谱聚合节点（高级功能）
- [ ] **图谱-聚合节点**
  - 按指定聚合字段（属性、标签或日期范围）聚合同类节点
  - 显示每个聚合节点包含的子节点数量
  - 聚合节点可以展开
  - 配置来源：`domain_config.json` 中的 `AggregationFields.GraphFields`

### 🟢 P2 - 目录与链接优化
- [ ] **反向链接优化**
  - 支持根据 domain 配置调整排序
  - 后续可扩展：按 frontmatter 属性字段聚合（一级/二级多级聚合）
  - 无对应聚合字段的链接归入"未分类"组

- [ ] **目录与文件夹页优化**
  - 目录：支持根据 domain 配置调整排序
  - 文件夹页：支持根据 domain 配置调整排序

---

## 💡 技术实现建议

### 图谱功能建议
- 图谱功能建议单独制作页面，支持与 U3 系统内功能嵌套关联使用
- 通过 API 接受图谱 JSON 数据，便于与 U3 集成

### 数据统一说明
- 不建议 Backlinks 直接读取局部图谱 JSON 分片（SSG 时序冲突、depth 限制导致数据不完整）
- 构建时基于 `allFiles` 完成分组和首批渲染，客户端仅负责追加
- 远期可在 `GraphLocalEmitter` 中复用链接遍历逻辑，额外输出轻量 `backlinks.json` 分片

### 性能优化建议
- 局部图谱预计算已实现，建议进行性能测试验证效果
- 可使用 Chrome DevTools Performance Monitor 观察 JS event listeners 和 Memory 使用情况
- 详见：`.spec/首屏图谱未完全渲染问题/IMPLEMENTATION_SUMMARY.md`

---

## 📋 待办事项

### 布局优化
- [ ] **右侧边栏布局调整**：
  - 当前问题：右侧边栏同时显示局部图谱、目录、反向链接，内容较拥挤
  - 待解决：设计更合理的布局方案（可考虑折叠、标签页切换、或调整各组件占比）

### 功能测试
- [ ] **反向链接增量更新测试**：
  - 验证修改 frontmatter 字段后聚合结果是否正确更新
  - 验证新增/删除文件后层级结构是否正确调整
  - 验证配置变更（添加/删除聚合字段）后的效果
