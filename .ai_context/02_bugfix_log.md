项目缺陷修复日志

项目信息
- 技术栈：Node.js + Express（后端），原生 HTML/CSS/JS（前端）
- 最后修复日期：2026-07-29
- 修复会话ID：2026-07-28-bugfix-cycle

Bug清单

| 编号 | 文件 | 行号 | 类别 | 问题描述 | 状态 |
|------|------|------|------|----------|------|
| B001 | util/request.js | 361 | 后端/安全 | 429/403 响应不进重试逻辑，直接 reject 导致上层崩溃 | 已修复 |
| B002 | app_combined.js | 69 | 后端/安全 | state.accounts 无锁保护导致并发竞态 | 已修复 |
| B003 | app_combined.js | 897 | 后端/安全 | 缺少全局 Express 错误处理器，未捕获异常返回 HTML 而非 JSON | 已修复 |
| B004 | app_combined.js | 146 | 后端/安全 | CORS 反射任意 Origin 且始终 Allow-Credentials，可被 CSRF 攻击 | 已修复 |
| B005 | app_combined.js | 242 | 后端/安全 | Cookie 缺少 HttpOnly，XSS 可读取 session | 已修复 |
| B006 | app_combined.js | 192 | 后端/安全 | 文件上传无 MIME 类型校验，可上传任意文件 | 已修复 |
| B007 | app_combined.js | 102 | 后端/安全 | 所有 /api/* 端点无认证检查，存在 IDOR 漏洞 | 已修复 |
| B008 | app_combined.js | 80 | 后端/安全 | 登录/发验证码接口无频率限制，可被短信轰炸/暴力枚举 | 已修复 |
| B009 | app_combined.js | 37 | 后端/可靠性 | 状态纯内存存储，重启后所有账号登录态丢失 | 已修复 |
| B010 | app_combined.js | 186 | 后端/安全 | express.json limit 500MB 过大，可被 DoS | 已修复 |
| B011 | app_combined.js | 756 | 后端/安全 | relogin 的 setTimeout 无法取消，账号删除后仍会执行 | 已修复 |
| B012 | app_combined.js | 736 | 后端/安全 | 清理关联定时器，账号删除时需清除所有相关定时器 | 已修复 |
| F001 | index.html | 956 | 前端/安全 | startAll 缺少错误处理，API 失败时无反馈 | 已修复 |
| F002 | index.html | 967 | 前端/安全 | stopAll 缺少错误处理，API 失败时无反馈 | 已修复 |
| F003 | index.html | 885 | 前端/安全 | deleteAccount 缺少二次确认 | 已修复 |
| F004 | index.html | 805 | 前端/安全 | sendVerifyCode 缺少输入校验 | 已修复 |
| F005 | index.html | 853 | 前端/安全 | verifyAndLogin 缺少重试机制 | 已修复 |
| F006 | index.html | 958 | 前端/可靠性 | simulateTask 定时器泄漏，账号删除后仍会执行 | 已修复 |
| F007 | index.html | 1422 | 前端/安全 | log 函数缺少日志级别校验 | 已修复 |
| F008 | index.html | 753 | 前端/可靠性 | 前端状态未持久化，刷新后丢失 | 已修复 |
| F009 | index.html | 1014 | 前端/安全 | updateThreadCount 缺少并发数校验 | 已修复 |
| F010 | index.html | 734 | 前端/安全 | sanitizeInput 缺少 XSS 防护 | 已修复 |

待办
- 

技术债
- 01_project_brief.md、03_architecture.md 仍为模板占位符，待填写完整