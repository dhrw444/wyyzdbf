# 统一播放功能文档

## 概述

统一播放接口 `POST /api/play`，支持灵活组合三个维度：
- **指定歌手**: 播放特定歌手的歌曲
- **指定歌数**: 最多播放多少首
- **指定时长**: 最多播放多少分钟

三者可以任意组合，同时指定时**歌数优先**，再按时长截断。

## 统一播放接口

### API 端点
```
POST /api/play
```

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `mode` | string | 否 | `'mix'` | `'artist'`=歌手模式, `'mix'`=混合模式 |
| `artist_id` | string | 否 | - | 歌手ID，指定后获取该歌手歌曲 |
| `artist_name` | string | 否 | - | 歌手名称，用于搜索 |
| `count` | number | 否 | 不限 | 最多播放歌曲数量 |
| `minutes` | number | 否 | 不限 | 最多播放分钟数 |

### 组合示例

```bash
# 1. 播放歌手A，不限制歌数和时长（默认10首）
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"mode":"artist","artist_id":"6452"}'

# 2. 播放歌手A，最多100首歌
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"mode":"artist","artist_id":"6452","count":100}'

# 3. 播放歌手A，最多30分钟
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"mode":"artist","artist_id":"6452","minutes":30}'

# 4. 播放歌手A，最多100首歌且最多30分钟（歌数优先，按时长截断）
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"mode":"artist","artist_id":"6452","count":100,"minutes":30}'

# 5. 按歌手名搜索，播放最多10首
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"artist_name":"周杰伦","count":10}'

# 6. 播放热门歌曲，最多30分钟
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"minutes":30}'

# 7. 播放热门歌曲，最多20首
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"count":20}'
```

### 响应示例

```json
{
  "success": true,
  "message": "开始播放 15 首歌曲（最多 100 首，最多 30 分钟），共 28 分钟",
  "song_id": 186016,
  "url": "https://music.163.com/song/media/outer/url?id=186016.mp3",
  "br": 320000,
  "total_songs": 15,
  "total_duration": 1680,
  "mode": "artist",
  "songs": [
    { "id": 186016, "name": "七里香", "artists": "周杰伦", "album": "七里香", "duration": 345 },
    { "id": 186017, "name": "晴天", "artists": "周杰伦", "album": "叶惠美", "duration": 269 }
  ]
}
```

## 兼容旧端点

旧端点仍然可用，但建议使用统一接口：

| 旧端点 | 等价于统一接口 |
|--------|---------------|
| `POST /api/play/artist` | `POST /api/play`，mode='artist' |
| `POST /api/play/count` | `POST /api/play`，传count参数 |
| `POST /api/play/duration` | `POST /api/play`，传minutes参数 |

## 前端使用

搜索页面已集成播放控制面板，支持：
1. 输入歌手名/歌曲名搜索
2. 在播放控制中输入歌数或分钟数
3. 点击"播放结果"按条件播放
4. 点击"播放歌手全部"播放搜索到的歌手歌曲

## 条件组合逻辑

```
count 和 minutes 同时指定时：
  1. 先按 count 选择歌曲
  2. 再按 minutes 截断（总时长超过 minutes 时停止）
  3. 两个条件都不满足时，取所有歌曲

count 和 minutes 都不指定时：
  默认取 10 首
```