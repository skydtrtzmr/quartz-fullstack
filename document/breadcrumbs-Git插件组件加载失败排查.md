# breadcrumbs Git 插件组件加载失败排查

## 现象

`nest-small` 的构建日志 `server/logs/tasks/task-nest-small-1790647359.log` 中出现：

```text
Plugin "breadcrumbs" declares components but failed to load them
```

本次构建仍然成功：解析了 65 个 Markdown 文件，输出 248 个文件。因此这条消息是组件加载警告，不是构建失败；受影响的是页面中的面包屑组件。

## 已确认的原因

`settings/nest-small/quartz.config.yaml` 启用了 Git 源 `github:quartz-community/breadcrumbs`。本机缓存目录 `quartz5/.quartz/plugins/breadcrumbs` 中有插件源码和依赖，但缺少 `dist/components/index.js`。插件的 `package.json` 将该文件声明为 `./components` 的导入入口，组件加载器找不到它，因而发出上述警告。

直接运行 `npm run build` 也失败。缓存中的 Rollup 版本为 `4.62.2`；其 Windows 原生依赖 `@rollup/rollup-win32-x64-msvc` 虽然存在，但 Node 加载 `.node` 文件时报告“不是有效的 Win32 应用程序”（`ERR_DLOPEN_FAILED`）。Rollup 将这一底层错误包装成“Cannot find module”提示，所以不能仅凭提示断定该包不存在。

## 修复步骤（PowerShell）

在项目所在机器上执行：

```powershell
Set-Location -LiteralPath 'D:\CodeProjects\quartz-fullstack\quartz5\.quartz\plugins\breadcrumbs'
npm ci --include=optional
npm run build
Test-Path -LiteralPath '.\dist\components\index.js'
```

最后一行应输出 `True`。`npm ci` 按当前 `package-lock.json` 重新安装依赖，会自动重建 `node_modules`；`--include=optional` 明确安装 Rollup 所需的可选依赖。此步骤需要能够访问 npm registry。无需删除 `package-lock.json`，也无需把插件配置改成 npm 源。

随后重新触发 `nest-small` 构建，确认新日志中不再出现 `Plugin "breadcrumbs" declares components but failed to load them`，并检查非首页页面的面包屑是否正常显示。

## 如果重装后仍失败

先在同一目录检查原生依赖能否直接加载：

```powershell
node -e "require('@rollup/rollup-win32-x64-msvc'); console.log('Rollup native module OK')"
```

如果仍报 `ERR_DLOPEN_FAILED`，查看其底层错误和当前 Node 的架构，再核对 npm 下载源与本机环境；不要只看 Rollup 包装后的“Cannot find module”提示。

## 后续注意

当前插件安装器发现 Git 缓存目录已存在时，会直接复用它，并不检查组件入口是否已经构建。因此仅重新触发 Quartz 构建，通常不会自动补齐这个缓存中的 `dist`；需要先完成上述依赖重装与插件构建。

参考：[npm ci 文档](https://docs.npmjs.com/cli/v11/commands/npm-ci/)、[npm 可选依赖问题记录](https://github.com/npm/cli/issues/4828)。
