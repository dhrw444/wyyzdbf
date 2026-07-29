# 音乐自动化技能

## 描述
基于 OpenInterpreter 的 AI 编码代理，为网易云音乐多账号任务平台提供智能化任务执行能力。

## 功能特性
- **智能任务生成**：根据用户需求自动生成和执行音乐任务
- **多账号协同**：跨多个账号执行复杂任务序列
- **错误恢复**：自动检测和处理任务执行中的错误
- **数据分析**：分析用户行为模式，优化任务执行策略

## 集成方式
在网易云项目的主服务器中添加 AI 编码代理能力。

## 使用方法
```javascript
const { MusicAutomationSkill } = require('./skills/music-automation')

// 创建技能实例
const musicAutomation = new MusicAutomationSkill({
  interpreter: musicAgent,
  ncmApi: require('./server')
})

// 执行智能任务
const result = await musicAutomation.executeSmartTask({
  accountId: '123',
  task: '创建包含10首流行歌曲的歌单'
})
```

## 配置
- 支持多种 AI 模型（Kimi、DeepSeek、Qwen等）
- 可配置任务执行权限和沙盒环境
- 支持任务优先级和并发控制