# Quartz 后端研发任务清单

## ✅ 已完成

- [x] **业务域区分**：基于 `settings/{domain}/` 目录作为 domain 权威来源，分别进行图谱/目录构建
- [x] **业务域配置 API**：
  - `GET /api/domain` - 列出所有 domain
  - `POST /api/domain/create` - 创建 domain
  - `PUT /api/domain/{domain}/config` - 更新 domain 配置
  - `POST /api/domain/{domain}/build` - 触发指定 domain 的构建
  - `GET /api/domain/{domain}/config` - 获取 domain 配置

## 🔄 进行中/待优化

- [ ] **多进程构建支持**：多个 domain 同时构建时的并发控制

## 📋 待开发

- [ ] **构建状态 API**：`GET /api/domain/{domain}/status` 查询构建状态
- [ ] **构建日志 API**：`GET /api/domain/{domain}/logs` 获取构建日志
- [ ] **Domain 删除 API**：`DELETE /api/domain/{domain}`
- [ ] **配置验证 API**：创建/更新配置时的合法性检查
