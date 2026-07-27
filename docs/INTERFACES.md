# CLI 命令参考

本项目是一个 CLI 命令行工具，所有交互通过子命令和参数完成。

## 主入口

```bash
python3 netease_player.py <command> [options]
```

## 登录命令

### `login` — 登录网易云音乐

**手机号 + 密码**
```bash
python3 netease_player.py login -p <手机号> -P <密码>
```
- `-p` / `--phone`: 手机号（必填）
- `-P` / `--password`: 密码（未提供则交互式输入）

**短信验证码**
```bash
python3 netease_player.py login -p <手机号> --sms
```
- 系统发送验证码后，终端提示输入

**邮箱登录**
```bash
python3 netease_player.py login -p <邮箱> -P <密码>
```
- 自动检测 `@` 符号，走邮箱登录流程
- 密码未提供时交互式输入

**二维码登录**
```bash
python3 netease_player.py login --qr
```
- 终端打印 ASCII 二维码
- 180 秒内扫码有效
- 每 3 秒轮询一次状态，最多 60 次

## 状态查询

### `status` — 查看当前登录态

```bash
python3 netease_player.py status
```
输出: 未登录 或 已登录 - `<昵称>` (UID: `<uid>`)

## 歌曲搜索与播放

### `search` — 搜索歌曲并交互式选择播放

```bash
python3 netease_player.py search <关键词> [-n <数量>] [--lyrics]
```
- `keyword`: 搜索关键词
- `-n` / `--limit`: 返回数量（默认 20）
- `--lyrics`: 播放时显示歌词

### `play` — 按歌曲 ID 直接播放

```bash
python3 netease_player.py play --id <歌曲ID> [--level <品质>] [--lyrics]
```
- `--id`: 歌曲 ID（必填）
- `--level`: 音质（`standard` / `higher` / `exhigh` / `lossless` / `hires`，默认 `standard`）
- `--lyrics`: 显示歌词

## 歌单与推荐

### `playlist` — 浏览用户歌单并播放

```bash
python3 netease_player.py playlist [--lyrics]
```
- 列出当前用户所有歌单
- 选择歌单后列出歌曲
- 选择歌曲后播放

### `daily` — 每日推荐浏览与播放

```bash
python3 netease_player.py daily [--lyrics]
```
- 获取每日推荐 30 首
- 交互式选择播放

## 统计命令

### `stats-search` — 搜索统计

```bash
python3 netease_player.py stats-search <关键词> [-n <上限>] [--play-n <N>] [--play-min <M>]
```
- `keyword`: 搜索关键词（通常为歌手名）
- `-n` / `--max`: 最大搜索数量（默认 50）
- `--play-n N`: 统计后连续播放前 N 首可播放歌曲
- `--play-min M`: 统计后连续播放 M 分钟

输出包括：
- 总匹配歌曲数量和总时长
- 可播放歌曲数量和总时长
- 不可播放歌曲数量和总时长（标注原因：无版权/需VIP/已下架）
- 完整歌曲列表

### `stats-playlist` — 歌单统计

```bash
python3 netease_player.py stats-playlist <歌单ID> [-a <歌手名>] [--play-n <N>] [--play-min <M>]
```
- `playlist_id`: 歌单 ID 或 URL 中的数字部分
- `-a` / `--artist`: 按歌手名过滤（模糊匹配）
- `--play-n N`: 统计后连续播放前 N 首
- `--play-min M`: 统计后连续播放 M 分钟

### `stats-daily` — 每日推荐统计

```bash
python3 netease_player.py stats-daily [-a <歌手名>] [--play-n <N>] [--play-min <M>]
```
- `-a` / `--artist`: 按歌手名过滤（模糊匹配）
- `--play-n N`: 统计后连续播放前 N 首
- `--play-min M`: 统计后连续播放 M 分钟

## 完整使用示例

```bash
# 1. 登录
python3 netease_player.py login --qr

# 2. 查看状态
python3 netease_player.py status

# 3. 搜索并播放
python3 netease_player.py search 晴天

# 4. 统计周杰伦所有歌曲并播放 5 首
python3 netease_player.py stats-search 周杰伦 --play-n 5

# 5. 统计歌单中林俊杰的歌曲并播放 30 分钟
python3 netease_player.py stats-playlist 12345678 -a 林俊杰 --play-min 30

# 6. 每日推荐中找陈奕迅的歌
python3 netease_player.py stats-daily -a 陈奕迅
```
