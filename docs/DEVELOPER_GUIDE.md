# 开发者指南

## 项目目的

netease_player 是一个运行在 Linux 服务器上的网易云音乐命令行播放器。它实现了网易云音乐的 weapi 加密协议，提供完整的登录、搜索、播放、歌单管理和歌曲统计功能。

**核心职责**:
- 模拟客户端加密协议与网易云 API 交互
- 支持多种登录方式（手机号/邮箱/二维码）
- 提供命令行交互式歌曲播放
- 按歌手统计可播放歌曲数量和总时长
- 支持按首数或时长批量连续播放

## 环境搭建

### 前置条件

- Python >= 3.8
- ffmpeg（提供 `ffplay` 播放器）
- Linux 服务器（无 GUI 环境）

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd <repo-name>

# 安装 Python 依赖
pip3 install --break-system-packages -r requirements.txt

# 安装 ffmpeg（如果尚未安装）
DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg
```

### 验证安装

```bash
# 确认 ffplay 可用
which ffplay

# 确认 Python 依赖
python3 -c "import requests, Cryptodome.Cipher; print('OK')"
```

## 运行

```bash
# 查看帮助
python3 netease_player.py --help

# 二维码登录
python3 netease_player.py login --qr

# 手机号+密码登录
python3 netease_player.py login -p 13800138000 -P your_password

# 手机号+短信验证码登录
python3 netease_player.py login -p 13800138000 --sms

# 邮箱登录
python3 netease_player.py login -p user@example.com -P your_password

# 查看登录状态
python3 netease_player.py status

# 搜索歌曲
python3 netease_player.py search 周杰伦

# 按 ID 播放
python3 netease_player.py play --id 123456

# 浏览歌单
python3 netease_player.py playlist

# 每日推荐
python3 netease_player.py daily

# 歌手统计
python3 netease_player.py stats-search 周杰伦

# 统计后连播 5 首
python3 netease_player.py stats-search 周杰伦 --play-n 5

# 统计后连播 30 分钟
python3 netease_player.py stats-search 周杰伦 --play-min 30
```

## 编码规范

### 项目约定

- 单文件架构：所有核心逻辑在 `netease_player.py`
- 辅助脚本独立：`qr_login.py` 是可选的独立二维码登录工具
- Cookie 存储在 JSON 格式：`~/.netease_player/cookies.json`
- 环境变量：不使用 `.env`，配置通过命令行参数传入

### 命名

| 类型 | 约定 | 示例 |
|------|------|------|
| 函数 | snake_case | `search_songs()`, `get_song_url()` |
| 常量 | SCREAMING_SNAKE | `CONFIG_DIR`, `COOKIE_FILE`, `NONCE` |
| 私有函数 | _leading_underscore | `_api_post()`, `_encrypt_params()` |

### 函数签名约定

- 所有需要登录态的函数接受 `cookies=None` 可选参数
- `cookies` 为 `None` 时自动调用 `_get_cookies_dict()` 获取当前登录态
- 内部循环中使用的函数（如 `check_playable()`）在调用方统一获取一次 cookies，避免重复 I/O

```python
def search_songs(keyword, limit=20, cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    # ...
```

### 错误处理

- API 调用失败返回 `{"code": -1, "message": "error"}` 格式
- 登录失败调用 `sys.exit()` 立即退出
- 播放失败打印错误信息并继续下一首

## 常见任务

### 调试加密逻辑

单个加密测试：
```python
python3 -c "
from netease_player import _encrypt_params
print(_encrypt_params({'s': '周杰伦', 'type': '1', 'limit': '1'}))
"
```

### 手动测试 API 调用

```python
python3 -c "
from netease_player import _api_post, _get_cookies_dict
cookies = _get_cookies_dict()
result = _api_post('https://music.163.com/weapi/w/nuser/account/get', {}, cookies=cookies)
print(result)
"
```

### 添加新的统计维度

找到 `_print_stats()` 函数（约 578 行），在统计输出区添加新的统计维度：

```python
def _print_stats(songs, playable, unplayable, label=""):
    # ... 现有逻辑 ...
    # 添加新的统计维度，如按专辑分组
    # album_stats = {}
    # for s in songs:
    #     album = s.get('album', 'N/A')
    #     album_stats[album] = album_stats.get(album, 0) + 1
```

### 更换播放器后端

修改 `_find_player()` 函数中的优先级列表（约 444 行）：
```python
def _find_player():
    for name in ["my_custom_player", "mpv", "ffplay"]:
        # ...
```

### 修改 Cookie 存储路径

修改顶部的 `CONFIG_DIR` 常量（约 20 行）：
```python
CONFIG_DIR = Path.home() / ".my_custom_player_dir"
```

## 关键文件

| 文件 | 目的 |
|------|------|
| `netease_player.py` | 主程序，包含所有功能和 CLI 入口 |
| `qr_login.py` | 独立二维码登录（可脱离主程序使用） |
| `requirements.txt` | Python 依赖声明 |
| `~/.netease_player/cookies.json` | 登录凭证持久化存储 |
