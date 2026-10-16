# Navigation History Pro

Quartz 5 本地组件插件：在当前业务域内后退、前进。遵循 `docs/advanced/making plugins.md` 和 `creating components.md`，通过 `@quartz-community/types`、组件资源和 `nav` / `prenav` / `render` 事件接入。

## 接入

在仓库根目录运行：

```powershell
node scripts/setup-local-plugins.mjs --only=navigation-history-pro
```

业务域 YAML：

```yaml
plugins:
  - source: ../plugins-local/navigation-history-pro
    enabled: true
    options:
      showLabels: false
      restoreScroll: true
    layout:
      position: beforeBody
      priority: 4
      group: pageNavigation
  - source: github:quartz-community/breadcrumbs
    enabled: true
    options: { rootName: 首页 }
    layout:
      position: beforeBody
      priority: 5
      condition: not-index
      group: pageNavigation

layout:
  groups:
    pageNavigation:
      priority: 4
      direction: row
      gap: 0.5rem
```

已有 breadcrumbs 配置时只增加 `group`，不要再注册第二次。插件也可独立放在其他布局区域。修改 YAML、插件后需重新生成页面；不会自动更新已有业务域配置。

## 行为

- 用 `configuration.baseUrl` 的路径界定业务域，保留查询参数、维度页 scope/filter 和锚点。
- 直接进入页面时后退置灰；业务域内新导航启用后退，回退后启用前进；打开新链接清空前进分支。
- 按钮调用原生 `history.go()`，浏览器按钮与站内按钮共用真实历史。通过命名空间保存标记，保留其他插件的 history state。
- sessionStorage 保存当前标签页的历史索引与滚动位置；存储不可用时仍可在内存中使用。刷新后尽量恢复，未知历史项保守地建立新边界，避免按钮带用户离开业务域。
- 跨域/跨业务域记录不纳入当前按钮的可用范围。浏览器自己的后退仍可离开业务域。
- 默认恢复页面滚动位置；不保存图谱展开状态。前后退导航期间按钮暂时禁用，避免重复触发。
- 中文、英文标签；图标有 aria-label、title、键盘焦点样式，移动端使用较大点击区域。

## 开发

```powershell
npm run typecheck
npm test
npm run build
```

插件封装浏览器 History API 的 pushState/replaceState 以观察 SPA 的真实入栈，不修改 Quartz 核心路由；与第三方直接替换这些方法的插件同时使用时需验证兼容性。
