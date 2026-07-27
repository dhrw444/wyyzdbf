# Netease Player

网易云音乐命令行播放器，支持 Linux 服务器无 GUI 环境运行。提供登录、搜索、在线播放、歌单管理和歌手歌曲统计功能。

## 安装

```bash
# 克隆仓库
git clone https://github.com/dhrw444/netease-player.git
cd netease-player

# 安装 Python 依赖
pip3 install --break-system-packages -r requirements.txt

# 安装 ffmpeg（提供 ffplay 播放器）
DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg
```

## 快速开始

### 1. 登录

```bash
# 二维码登录（推荐）
python3 netease_player.py login --qr

# 手机号 + 密码
python3 netease_player.py login -p 13800138000

# 手机号 + 短信验证码
python3 netease_player.py login -p 13800138000 --sms

# 邮箱登录
python3 netease_player.py login -p user@example.com

# 查看登录状态
python3 netease_player.py status
```

### 2. 搜索播放

```bash
# 搜索歌曲（交互式选择）
python3 netease_player.py search 周杰伦

# 按歌曲 ID 直接播放
python3 netease_player.py play --id 186016

# 显示歌词
python3 netease_player.py search 晴天 --lyrics
```

### 3. 歌单与每日推荐

```bash
# 浏览个人歌单
python3 netease_player.py playlist

# 每日推荐
python3 netease_player.py daily
```

### 4. 歌手统计

统计歌手的歌曲数量、总时长和可播放性。

```bash
# 搜索统计
python3 netease_player.py stats-search 周杰伦

# 统计后连续播放 5 首
python3 netease_player.py stats-search 周杰伦 --play-n 5

# 统计后连续播放 30 分钟
python3 netease_player.py stats-search 周杰伦 --play-min 30

# 歌单中某歌手的统计
python3 netease_player.py stats-playlist 12345678 -a 林俊杰

# 每日推荐中某歌手的统计
python3 netease_player.py stats-daily -a 陈奕迅
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `login` | 登录（-p 手机号/邮箱, -P 密码, --sms, --qr） |
| `status` | 查看登录状态 |
| `search <关键词>` | 搜索歌曲，交互式选择播放 |
| `play --id <ID>` | 按歌曲 ID 播放（--level 音质, --lyrics 歌词） |
| `playlist` | 浏览个人歌单并播放 |
| `daily` | 每日推荐浏览播放 |
| `stats-search <关键词>` | 搜索统计（--play-n N, --play-min M） |
| `stats-playlist <ID>` | 歌单统计（-a 歌手过滤, --play-n, --play-min） |
| `stats-daily` | 每日推荐统计（-a 歌手过滤, --play-n, --play-min） |

## 播放器后端

按优先级自动选择：

1. **mpv** - `mpv --no-video <url>`
2. **ffplay** (ffmpeg) - `ffplay -nodisp -autoexit <url>`
3. **下载** - HTTP 下载 MP3 到 `/tmp/`

## 登录凭证

登录状态保存在 `~/.netease_player/cookies.json`，JSON 格式持久化。

## 依赖

- Python >= 3.8
- requests >= 2.28.0
- pycryptodomex >= 3.15.0
- ffmpeg（提供 ffplay）
