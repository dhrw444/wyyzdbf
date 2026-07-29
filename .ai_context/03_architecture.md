架构说明

关键文件职责
- app_combined.js：核心入口文件，集成 Express 服务、API 路由、中间件、状态管理
- module/：431+ 个 NetEase Music API 模块，每个文件代理一个后端接口
- util/request.js：HTTP 请求封装，支持超时、重试、429/403/502 错误处理
- util/logger.js：JSON 结构化日志，含敏感信息脱敏
- util/validator.js：参数校验工具
- util/crypto.js：加密工具
- util/fileHelper.js：文件操作工具
- index.html：前端多标签 UI 界面，原生 HTML/CSS/JS
- .state.json：状态持久化文件，存储账号、任务、Session 数据

前后端交互方式
- 前端通过 fetch API 请求后端 /api/* 端点
- 后端 Express 路由转发请求至 module/ 中的对应 API 模块
- API 模块通过 util/request.js 向 NetEase Music 服务器发起实际请求
- 响应经后端处理后返回前端 JSON 格式
- 前端多标签架构：任务管理、账号管理、日志查看等

数据库表关系
- 无传统数据库，使用内存对象 + .state.json 文件持久化
- state.accounts：账号信息（phone, status, running, progress 等）
- state.runningTasks：运行中的任务
- state.loginSessions：登录 Session（phone -> { cookies, createTime }）
- state.nextId：自增 ID
- state.maxThreads：最大并发线程数

第三方接口清单
- NetEase Music API（通过 module/ 代理）
- 短信验证码接口（/api/send-code）
- 登录接口（/api/verify-login）
- 任务管理接口（/api/task/start, /api/task/stop, /api/task/start-all, /api/task/stop-all）