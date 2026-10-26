# 构建状态与日志验收

本目录是 Bruno 请求、原生 Tests 和响应 Examples；Examples 是预期示意，不能代替实际服务测试。

## 最快使用

1. 编译并启动本次新版本 Go Server；在 Bruno 的 Quartz 集合中选择已有环境（使用其中的 ip）。
2. 父文件夹 Vars 中检查 check_user / check_pwd，默认沿用原集合请求中的凭据；不要改环境中的 domain。
3. 运行“01-正常流程”：创建独立测试域 → 验证 idle/no_logs → 提交 reset 构建 → 有上限地轮询完成 → 校验日志记录 → 校验活动任务列表。
4. 运行“02-接口错误”：401、400、404、405 和无记录查询；不会启动实际构建。
5. 需要异常场景时，阅读“03-手动场景”中各请求的 Docs，手动准备后设置 check_manual_case。默认 off，集合运行时这些请求跳过；单独发送会提示先准备。

可以运行整个父文件夹：正常与错误流程执行，手动场景默认跳过。正常流程会触发测试域真实构建；编写本集合时没有发送这些请求。
正常构建失败会使成功断言失败，随后日志请求可用于定位，不会把 failed 当作“测试全部通过”。

## 变量

- ip：继承已有本地/公司测试环境。
- check_domain：创建请求生成 bruno-build-check-秒级时间，随后由运行时变量传给后续请求。不要手动指向已有业务域。
- check_task_id：提交响应中自动保存，用于状态、日志的一致性断言。
- check_missing_domain：不会创建的域，供 404 / idle / no_logs 测试。
- check_max_polls / check_poll_ms：默认 180 次、间隔 1000 ms，只控制 Bruno 等待，不改变服务构建超时策略。
- check_manual_case：off / busy / failure / unknown / restart / startup / logio。结束后恢复 off。

## 结果判读

- succeeded：真实完成，退出码 0。
- failed：真实失败，有错误信息；启动失败时没有 exitCode。
- unknown：日志缺少完整可靠的结果行，不能从正文“成功/失败”判断终态。
- idle / no_logs：没有活动任务，也没有可查询日志。
- Busy：仍有同域活动任务，HTTP 为 200。
- 最新日志格式：logs/tasks/<taskId>.log，最后一行以 @@QUARTZ_TASK_RESULT@@ 开头；无单独结果文件。

已有旧格式日志仍可查看，没有固定结果行时 unknown 是预期结果。
排队需要另一个域仍在构建且服务为 serial；Examples 已展示 queued，不能靠一次快速构建保证碰到该状态。

## 作用范围与清理

只有“创建测试域”和“提交构建”类请求写入测试数据；其他请求只查询或应在启动构建前被拒绝。
没有自动删除业务域、修改 YAML、截断日志或改服务配置的脚本。
正常流程结束后会保留测试域、站点输出、缓存和日志，方便查看。需要清理时，确认没有活动任务后，用现有“删除业务域”请求显式填写 check_domain 并选择是否删除输入/输出。
同秒结束后再次提交的 ID/日志重名边界按原约定暂不测试或改造。

## 格式依据

使用 Bruno 原生 Tests、运行时变量、Runner 分支与 Examples，脚本 API 参见官方文档：https://docs.usebruno.com/testing/script/javascript-reference 。
