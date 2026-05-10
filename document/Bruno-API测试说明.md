# Bruno API 测试说明

## 什么是 Bruno

Bruno 是一款开源的 API 测试客户端（类似 Postman/Insomnia），使用纯文本格式（`.bru`）存储接口请求，可直接通过 Git 管理。

## 导入方式

1. 下载并安装 [Bruno](https://www.usebruno.com/)
2. 打开 Bruno → 点击 **Open Collection**
3. 选择项目根目录下的 `bruno-api-test/` 文件夹
4. 所有接口请求会自动加载

## 集合结构

| 文件 | 接口 | 说明 |
|------|------|------|
| `列出所有业务域.bru` | `GET /api/domains` | 列出当前所有业务域 |
| `创建业务域.bru` | `POST /api/domain/{domain}` | 创建新业务域 |
| `修改业务域配置.bru` | `PUT /api/domain/{domain}` | 更新业务域配置与布局 |
| `删除业务域.bru` | `DELETE /api/domain/{domain}` | 删除业务域 |
| `触发指定业务域构建.bru` | `POST /api/domain/{domain}/build` | 触发指定业务域构建 |
| `获取业务域构建状态.bru` | `GET /api/domain/{domain}/status` | 查询构建任务状态 |
| `获取业务域日志.bru` | `GET /api/domain/{domain}/logs` | 获取构建日志 |
| `获取任务.bru` | `GET /api/tasks` | 获取任务列表 |
| `清理output垃圾-预览.bru` | `POST /api/cleanup/preview` | 预览 output 清理结果 |
| `清理output垃圾-确认删除.bru` | `POST /api/cleanup/confirm` | 确认清理 output 垃圾文件 |

## 环境变量

当前集合中的请求默认使用以下值：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| Base URL | `http://127.0.0.1:8766` | 后端服务地址 |
| `user` | `admin` | 认证用户名 |
| `pwd` | `password123` | 认证密码 |

如需修改，请在 Bruno 中创建环境变量并替换请求中的硬编码值。
