# 交付验收清单

> 会话 ID：session_20260728_001 | 修复日期：2026-07-28

---

## 后端验收

- [x] **空参拦截**: 调用 POST /api/send-code，参数为空 JSON `{}`。预期返回 `{"success":false,"message":"手机号格式不正确"}`。已验证通过。
- [x] **Cookie安全**: 正常请求后查看 Response Headers。预期包含 `HttpOnly; SameSite=Lax`。已修复代码，需在 HTTPS 环境验证 `Secure`。
- [x] **CORS白名单**: 从非白名单 Origin 发起跨域请求。预期返回 `localhost:8000` 而非请求的 Origin。已验证通过。
- [x] **安全头**: 响应头包含 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`X-XSS-Protection: 1; mode=block`。已验证通过。
- [x] **文件上传校验**: express-fileupload 已配置 `safeFileNames: true` 和 `preserveExtension: true`。文件大小限制从 500MB 降至 100MB。
- [x] **异常处理**: 所有路由已包裹 try-catch。全局 Express 错误处理器已添加 (4参数中间件)。已验证语法正确。
- [x] **SQL注入**: 本项目不使用 SQL 数据库，无 SQL 注入风险。
- [x] **权限绕过**: 已添加基础 API 认证中间件（X-API-Token 头校验）。需配置 `API_SECRET` 环境变量后启用。
- [x] **内部信息泄漏**: 云盘/歌单/API调试器等端点错误响应从 `error.message` 改为 `"服务器内部错误"`。
- [x] **竞态条件**: 已添加 `withLock` Promise 链式互斥锁，保护 `state.accounts` 并发修改。
- [ ] **Rate Limiting**: 基础限流逻辑已编码（`createRateLimiter`），独立 store + IP 归一化。需进一步调试验证。

## 前端验收

- [x] **XSS防护-song**: 所有歌曲名/歌手/专辑名在 innerHTML 插入前调用 `escapeHtml()`。已验证代码。
- [x] **XSS防护-account**: 账号名/手机号在 innerHTML 插入前调用 `escapeHtml()`。已验证代码。
- [x] **XSS防护-cloud**: 云盘文件名在 innerHTML 插入前调用 `escapeHtml()`。已验证代码。
- [x] **CSP**: 已添加 `<meta http-equiv="Content-Security-Policy">` 限制资源加载来源。已验证 HTML。
- [x] **点击劫持**: 已添加 `<meta http-equiv="X-Frame-Options" content="DENY">`。已验证 HTML。
- [x] **console泄漏**: `console.error` 已替换为 `log()`（使用 textContent）。已验证代码。
- [x] **API封装**: `apiRequest` 函数已存在，关键 fetch 调用已替换（send-code/verify-login/play-song）。
- [ ] **按钮防重复**: `withLoading` 函数已存在，searchSongs 已使用。其余函数（deleteAccount/sendApiRequest 等）需逐一手动添加到按钮元素上。
- [ ] **内存泄漏-定时器**: `simulateTask` 的 setInterval 在组件切换时无法清理。需全局定时器注册表。

## 回归测试

- [x] **核心流程**: `GET /api/stats` 返回正常 JSON。`POST /api/send-code` 参数校验正常。`POST /api/login/qr/key` 返回二维码 key。
- [ ] **并发测试**: 需多浏览器环境验证 withLock 互斥锁效果。
- [ ] **第三方降级**: request.js 已添加 429/403 指数退避重试。需实际触发限流验证。

## 未完成项说明

| 编号 | 项目 | 阻塞原因 | 建议 |
|------|------|---------|------|
| B008 | Rate Limiting 验证 | IP 归一化逻辑需要进一步调试 | 添加 `req.ip` 日志确认值 |
| B009 | 状态持久化 | 需设计序列化方案 | JSON 文件或 SQLite |
| F005 | 全部 fetch → apiRequest | 改动量较大，21处需逐一手动替换 | 分批次替换 |
| F006 | simulateTask 定时器泄漏 | 需要全局定时器注册表 | 创建 `activeTimers` Map |
