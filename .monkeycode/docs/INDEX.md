# 网易云音乐命令行播放器 - 文档

运行在 Linux 服务器上的网易云音乐 CLI 播放器，支持多种登录方式、歌曲搜索、在线播放、歌手统计和批量播放控制。

**快速链接**: [架构](./ARCHITECTURE.md) | [接口](./INTERFACES.md) | [开发者指南](./DEVELOPER_GUIDE.md)

---

## 核心文档

### [架构](./ARCHITECTURE.md)
系统设计、技术栈、加密层、认证流程、播放引擎和统计系统的完整说明。包含 Mermaid 架构图、登录时序图和统计播放流程图。

### [接口](./INTERFACES.md)
所有 CLI 命令的完整参考，包括 `login`（4 种方式）、`search`、`play`、`playlist`、`daily`、`stats-search`、`stats-playlist`、`stats-daily` 的参数说明和使用示例。

### [开发者指南](./DEVELOPER_GUIDE.md)
环境搭建、运行指令、编码规范、命名约定、常见任务（调试加密、API 测试、扩展功能）的分步指南。

---

## 快速参考

### 命令速查

```bash
# 登录
python3 netease_player.py login --qr
python3 netease_player.py login -p 13800138000 -P password
python3 netease_player.py login -p 13800138000 --sms
python3 netease_player.py login -p user@example.com

# 状态
python3 netease_player.py status

# 搜索播放
python3 netease_player.py search 周杰伦
python3 netease_player.py play --id 123456

# 歌单 / 每日推荐
python3 netease_player.py playlist
python3 netease_player.py daily

# 统计
python3 netease_player.py stats-search 周杰伦
python3 netease_player.py stats-search 周杰伦 --play-n 5
python3 netease_player.py stats-search 周杰伦 --play-min 30
python3 netease_player.py stats-playlist 12345678 -a 林俊杰
python3 netease_player.py stats-daily -a 陈奕迅
```

### 重要文件

| 文件 | 目的 |
|------|------|
| `netease_player.py` | 主程序（864 行），包含全部功能 |
| `qr_login.py` | 独立二维码登录辅助脚本 |
| `requirements.txt` | Python 依赖（requests, pycryptodomex） |
| `~/.netease_player/cookies.json` | 登录凭证存储 |

### 依赖安装

```bash
# Python 依赖
pip3 install --break-system-packages -r requirements.txt

# ffmpeg（提供 ffplay 播放器）
DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg
```

---

## 入门指南

### 首次使用
1. **[架构](./ARCHITECTURE.md)** — 了解系统如何运作
2. **[开发者指南](./DEVELOPER_GUIDE.md)** — 安装依赖并运行
3. **[接口](./INTERFACES.md)** — 探索可用命令

### 需要扩展功能
1. **[架构](./ARCHITECTURE.md)** — 查看子系统划分
2. **[开发者指南 - 常见任务](./DEVELOPER_GUIDE.md)** — 分步开发指南
