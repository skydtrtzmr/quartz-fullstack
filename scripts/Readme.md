# 生成大区模式业务域
python scripts/generate_test_md.py --domain demo-region --profile region --clean

# 生成硬上限模式业务域
python scripts/generate_test_md.py --domain demo-core --profile core --clean

# 清理所有旧业务域并生成
uv run python scripts/generate_test_md.py --domain demo-region --profile region --clean --clean-all

# 打包

uv run python .\scripts\pack-project.py

注意，`generate_test_md.py` 会同时生成业务域配置文件（v4 风格）；`generate_nested_md.py` 只生成内容，不写配置，配置应通过产品 API 产生。

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