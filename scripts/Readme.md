# 生成大区模式业务域
python scripts/generate_test_md.py --domain demo-region --profile region --clean

# 生成硬上限模式业务域
python scripts/generate_test_md.py --domain demo-core --profile core --clean

# 清理所有旧业务域并生成
uv run python scripts/generate_test_md.py --domain demo-region --profile region --clean --clean-all

# 打包

uv run python .\scripts\pack-project.py

# 生成 WTE 培训知识库业务域（设备 120 / 缺陷单 500 / 经验案例 200 / 培训课程 80 / 员工 60）
python scripts/generate_train_md.py --domain wte-train --clean

注意，`generate_test_md.py` / `generate_train_md.py` 会同时按 **v5 规则**生成业务域配置
`settings/{domain}/quartz.config.yaml`（实现见 `scripts/v5_domain_config.py`）：整棵继承
`server/config.json` 的 `template_file`，只改写 `pageTitle` / `baseUrl` /
`configuration.aggregation` / `note-properties-pro` 的属性链 / `graph-pro` 的
`globalGraph.{folders,coreNodeLimit}`，注释与 YAML 锚点原样保留；
`generate_nested_md.py` 只生成内容，不写配置，配置应通过产品 API 产生。

> ⚠️ `generate_test_md.py --clean-all` 会递归删掉 `input/`、`output/`、`settings/` 下所有其它域
> （删除前会打印待删清单），非必要不要用。
> 改了域配置必须加 `--reset` 全量重建，例如：
> `cd quartz5 && npm run quartz -- build -d ../input/{domain} -o ../output/{domain} --settings ../settings/{domain} --sqlite --cacheDir ../cache/{domain} --reset`

# 生成嵌套目录测试内容（多层子文件夹 + 每目录多字段 + echarts 样例 + 附件页）
python scripts/generate_nested_md.py --domain nest-full --size full --clean
python scripts/generate_nested_md.py --domain nest-small --size small --clean

# 也可显式控制数量（-1 = 按 size 默认，0 = 不生成）
python scripts/generate_nested_md.py --domain nest-full --size full --clean --charts 8 --attachments 12

内容说明：
- 多层子目录（组织/总部、项目/核心项目/2024、任务/在办 任务 等）与边界目录名（build/status/logs）。
- `附件/` 下是「解析后的附件文本」md；frontmatter 的 `附件下载` 字段带指向公共 `assets/` 的真实下载链接（服务端以 `/assets/...` 提供）。
- 部分普通文件会在 frontmatter 或正文中以 wikilink 引用附件 md（不是直接引用下载链接）。
- `图表/` 下是 ```` ```echarts ```` 样例，由 `echarts-pro` 渲染。

注意：`generate_nested_md.py` 的 `--clean` 只清 `input/{domain}`，不会删其它域；也没有 `--clean-all`。

# 运行业务域与文件夹级配置系统测试（默认起独立端口 9767 的临时服务实例）
node scripts/test_domain_api.mjs

# 测完保留产物并另起后台实例，直接给可浏览的链接
node scripts/test_domain_api.mjs --serve

# 只保留产物不启动后台实例（可用 TEST_PORT 指定端口）
TEST_PORT=9768 node scripts/test_domain_api.mjs --keep-output

测试脚本会自动：编译 server、起独立服务、通过 API 建域/改配置/触发 reset 构建、
对 HTTP/YAML/产物做三层断言；默认删除测试用的 settings/output/cache，只保留 input 内容资产。


---

uv:

# 清理所有旧业务域并生成
uv run python scripts/generate_test_md.py --domain demo-region --profile region --clean --clean-all

# 生成嵌套目录测试内容
uv run python scripts/generate_nested_md.py --domain nest-full --size full --clean