# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [运维部署|构建方法|测试方法|排错调试|工作流协作|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 条目

### 项目安全约束
- Date: 2026-07-28
- Context: Agent 在执行全栈缺陷修复时发现
- Category: 环境配置
- Instructions:
  - 网易云 API 加密密钥（crypto.js 中的 presetKey/linuxapiKey/eapiKey）是协议所必需的常量，不可移除
  - Cookie 使用 HttpOnly + SameSite=Lax 防护，但网易云API需要前端传递 cookie 给后端
  - 项目使用内存状态存储（state 对象），重启后所有账号登录态丢失
  - 认证中间件通过 X-API-Token 头校验，默认密钥为 music-platform-2024

### 启动与测试
- Date: 2026-07-28
- Context: Agent 在执行修复后的验证时发现
- Category: 构建方法
- Instructions:
  - 启动命令：`node app_combined.js`，监听端口 8000
  - 验证 API：`curl http://localhost:8000/api/stats`
  - 语法检查：`node -c /workspace/app_combined.js`
  - 测试限流需要发送超过 5 次请求到 /api/send-code

### 代码标记规范
- Date: 2026-07-28
- Context: Agent 在批量修复缺陷时建立
- Category: 工作流协作
- Instructions:
  - 每个 Bug 修复使用 [FIX-Bxxx] 或 [FIX-Fxxx] 标记
  - 标记格式：`[FIX-编号] 日期 | 后端/前端 | 类别 | 问题 | 修改 | 状态`
  - 后端从 B001 开始，前端从 F001 开始
  - 所有修复记录在 .ai_context/02_bugfix_log.md
