#!/usr/bin/env python3
"""网易云音乐命令行播放器 - 登录 / 搜索 / 播放 / 统计"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from Cryptodome.Cipher import AES

CONFIG_DIR = Path.home() / ".netease_player"
COOKIE_FILE = CONFIG_DIR / "cookies.json"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
PUBKEY = "010001"
NONCE = b"0CoJUm6Qyw8W8jud"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _aes_encrypt(text, key):
    if isinstance(text, str):
        text = text.encode("utf-8")
    if isinstance(key, str):
        key = key.encode("utf-8")
    pad = 16 - len(text) % 16
    text = text + bytearray([pad] * pad)
    encryptor = AES.new(key, AES.MODE_CBC, b"0102030405060708")
    return base64.b64encode(encryptor.encrypt(text))


def _rsa_encrypt(text, pubkey, modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(pubkey, 16), int(modulus, 16))
    return format(rs, "x").zfill(256)


def _encrypt_params(data):
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    elif not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    data_bytes = data.encode("utf-8")
    secret = binascii.hexlify(os.urandom(16))[:16]
    params = _aes_encrypt(_aes_encrypt(data_bytes, NONCE), secret).decode()
    enc_sec_key = _rsa_encrypt(secret, PUBKEY, MODULUS)
    return {"params": params, "encSecKey": enc_sec_key}


def _api_post(url, data, cookies=None, session=None):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://music.163.com",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    encrypted = _encrypt_params(data)
    try:
        if session is not None:
            resp = session.post(url, data=encrypted, headers=headers, timeout=15)
        else:
            resp = requests.post(url, data=encrypted, headers=headers, cookies=cookies, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"code": -1, "message": str(e)}


def _save_cookies(session):
    tmp = COOKIE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(session.cookies.get_dict(), ensure_ascii=False, indent=2))
    tmp.replace(COOKIE_FILE)


def _load_cookies():
    if not COOKIE_FILE.exists():
        return None
    try:
        return json.loads(COOKIE_FILE.read_text())
    except Exception:
        return None


def _md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def _get_cookies_dict():
    """获取当前 cookies dict，无登录态返回空 dict"""
    cookies = _load_cookies()
    return cookies if cookies else {}


# ---------- 登录 ----------

def login_cellphone(phone, password=None, countrycode="86"):
    session = requests.Session()

    if password:
        md5_pwd = _md5(password)
        data = {"phone": phone, "countrycode": countrycode, "password": md5_pwd, "rememberLogin": "true"}
        result = _api_post("https://music.163.com/weapi/login/cellphone", data, session=session)
        if result.get("code") == 200:
            _save_cookies(session)
            nickname = result.get("profile", {}).get("nickname", phone)
            print(f"登录成功 - {nickname}")
            return session
        sys.exit(f"登录失败 [{result.get('code')}]: {result.get('message', result)}")

    result = _api_post(
        "https://music.163.com/weapi/sms/captcha/sent",
        {"cellphone": phone, "ctcode": countrycode},
        session=session,
    )
    if result.get("code") != 200:
        sys.exit(f"发送验证码失败: {result}")

    print("验证码已发送，请查收短信")
    captcha = input("请输入短信验证码: ").strip()
    data = {"phone": phone, "countrycode": countrycode, "captcha": captcha, "rememberLogin": "true"}
    result = _api_post("https://music.163.com/weapi/login/cellphone", data, session=session)
    if result.get("code") == 200:
        _save_cookies(session)
        nickname = result.get("profile", {}).get("nickname", phone)
        print(f"登录成功 - {nickname}")
        return session
    sys.exit(f"登录失败 [{result.get('code')}]: {result.get('message', result)}")


def login_email(email, password):
    session = requests.Session()
    md5_pwd = _md5(password)
    data = {"username": email, "password": md5_pwd, "rememberLogin": "true"}
    result = _api_post("https://music.163.com/weapi/login", data, session=session)
    if result.get("code") == 200:
        _save_cookies(session)
        nickname = result.get("profile", {}).get("nickname", email)
        print(f"登录成功 - {nickname}")
        return session
    sys.exit(f"登录失败 [{result.get('code')}]: {result.get('message', result)}")


def login_qr():
    session = requests.Session()

    key_data = _api_post("https://music.163.com/weapi/login/qrcode/unikey", {"type": "1"}, session=session)
    unikey = key_data.get("unikey")
    if not unikey:
        sys.exit(f"获取二维码 key 失败: {key_data}")

    qr_url = f"https://music.163.com/login?codekey={unikey}"
    try:
        import qrcode as qrlib
        qr = qrlib.QRCode()
        qr.add_data(qr_url)
        qr.make()
        qr.print_ascii()
    except ImportError:
        pass
    print(f"\n链接: {qr_url}")
    print("请用网易云音乐 APP 扫描上方二维码登录...")

    for _ in range(60):
        result = _api_post(
            "https://music.163.com/weapi/login/qrcode/client/login",
            {"key": unikey, "type": "1"},
            session=session,
        )
        code = result.get("code") if isinstance(result, dict) else -1
        if code == 800:
            time.sleep(3)
        elif code == 803:
            _save_cookies(session)
            nickname = result.get("profile", {}).get("nickname", "用户")
            print(f"\n登录成功 - {nickname}")
            return session
        elif code == 801:
            print("等待扫码...")
            time.sleep(3)
        elif code == 802:
            print("请在手机上确认登录...")
            time.sleep(3)
        else:
            time.sleep(3)
    sys.exit("扫码超时")


def check_login():
    cookies = _get_cookies_dict()
    if not cookies:
        print("未登录，请先执行: python netease_player.py login -p <手机号>")
        return None

    result = _api_post(
        "https://music.163.com/weapi/w/nuser/account/get",
        {},
        cookies=cookies,
    )
    if result.get("code") == 200:
        profile = result.get("profile", {})
        print(f"已登录 - {profile.get('nickname', 'N/A')} (UID: {profile.get('userId', 'N/A')})")
        return True
    print("登录态已过期，请重新登录")
    return None


# ---------- 搜索 ----------

def search_songs(keyword, limit=20, cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    data = {"s": keyword, "type": "1", "limit": str(limit), "offset": "0", "total": "true"}
    result = _api_post("https://music.163.com/weapi/cloudsearch/get/web", data, cookies=cookies)
    if result.get("code") != 200:
        print(f"搜索失败: {result.get('message', result)}")
        return []

    songs = result.get("result", {}).get("songs", [])
    return [_song_to_dict(s) for s in songs]


def search_all_songs(keyword, max_results=50, cookies=None):
    """搜索歌手/关键词，分页获取尽可能多的歌曲"""
    if cookies is None:
        cookies = _get_cookies_dict()
    all_songs = []
    seen_ids = set()
    offset = 0
    while len(all_songs) < max_results:
        remain = max_results - len(all_songs)
        batch = min(remain, 30)
        data = {"s": keyword, "type": "1", "limit": str(batch), "offset": str(offset), "total": "true"}
        result = _api_post("https://music.163.com/weapi/cloudsearch/get/web", data, cookies=cookies)
        if result.get("code") != 200:
            break
        songs = result.get("result", {}).get("songs", [])
        if not songs:
            break
        for song in songs:
            sid = song["id"]
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            all_songs.append(_song_to_dict(song))
        offset += batch
    return all_songs


def _song_to_dict(song):
    artists = "/".join(a.get("name", "") for a in song.get("ar", []))
    return {
        "id": song["id"],
        "name": song["name"],
        "artists": artists,
        "album": song.get("al", {}).get("name", "N/A"),
        "duration": song.get("dt", 0) // 1000,
    }


# ---------- 获取播放地址 ----------

def get_song_url(song_id, level="standard", cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    level_map = {"standard": "standard", "higher": "higher", "exhigh": "exhigh", "lossless": "lossless", "hires": "hires"}
    data = {"ids": f"[{song_id}]", "level": level_map.get(level, level), "encodeType": "aac"}
    result = _api_post("https://music.163.com/weapi/song/enhance/player/url/v1", data, cookies=cookies)
    if result.get("code") != 200:
        return None
    song_data = result.get("data", [])
    if not song_data:
        return None
    info = song_data[0]
    if info.get("code") == 200 and info.get("url"):
        return info["url"]
    return None


def check_playable(song_id, cookies=None):
    """检测单首歌曲是否可播放"""
    if cookies is None:
        cookies = _get_cookies_dict()
    data = {"ids": f"[{song_id}]", "level": "standard", "encodeType": "aac"}
    result = _api_post("https://music.163.com/weapi/song/enhance/player/url/v1", data, cookies=cookies)
    if result.get("code") != 200:
        return False, None, ""
    info = result.get("data", [{}])[0]
    if info.get("code") == 200 and info.get("url"):
        return True, info["url"], f"{info.get('br', 0) // 1000}kbps"
    reason_map = {-110: "无版权", -104: "需VIP", -100: "已下架"}
    return False, None, reason_map.get(info.get("code"), "不可用")


# ---------- 歌词 ----------

def get_lyrics(song_id, cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    result = _api_post(
        "https://music.163.com/weapi/song/lyric",
        {"id": str(song_id), "lv": -1, "tv": -1, "csrf_token": ""},
        cookies=cookies,
    )
    if result.get("code") != 200:
        return None
    return result.get("lrc", {}).get("lyric", "")


def show_lyrics(song_id, cookies=None):
    lyrics = get_lyrics(song_id, cookies)
    if lyrics:
        print("\n--- 歌词 ---")
        for line in lyrics.strip().split("\n"):
            clean = line.strip()
            if clean and not any(clean.startswith(f"[{tag}:") for tag in ("ti", "ar", "al", "by", "offset")):
                print(clean)
        print("------------\n")


# ---------- 歌单 ----------

def get_user_playlists(uid, cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    data = {"uid": str(uid), "wordwrap": "7", "offset": "0", "total": "true", "limit": "1000"}
    result = _api_post("https://music.163.com/weapi/user/playlist", data, cookies=cookies)
    if result.get("code") != 200:
        print(f"获取歌单失败: {result.get('message', result)}")
        return []
    return [
        {"id": pl["id"], "name": pl["name"], "track_count": pl.get("trackCount", 0),
         "creator": pl.get("creator", {}).get("nickname", "")}
        for pl in result.get("playlist", [])
    ]


def get_playlist_tracks(playlist_id, cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    result = _api_post(
        "https://music.163.com/api/v3/playlist/detail",
        {"id": str(playlist_id), "total": "true", "limit": "1000", "n": "1000", "offset": "0"},
        cookies=cookies,
    )
    if result.get("code") != 200:
        print(f"获取歌单详情失败: {result.get('message', result)}")
        return []
    tracks = result.get("playlist", {}).get("tracks", [])
    return [_song_to_dict(t) for t in tracks]


# ---------- 每日推荐 ----------

def daily_recommend(cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    result = _api_post(
        "https://music.163.com/weapi/v2/discovery/recommend/songs",
        {"csrf_token": ""},
        cookies=cookies,
    )
    if result.get("code") != 200:
        print(f"获取每日推荐失败 [{result.get('code')}]: {result.get('message', result)}")
        return []
    songs = result.get("data", {}).get("dailySongs", [])
    if not songs:
        print("未获取到每日推荐")
        return []
    return [_song_to_dict(s) for s in songs]


# ---------- 用户 UID ----------

def get_uid(cookies=None):
    if cookies is None:
        cookies = _get_cookies_dict()
    result = _api_post("https://music.163.com/weapi/w/nuser/account/get", {}, cookies=cookies)
    if result.get("code") == 200:
        return result.get("profile", {}).get("userId")
    return None


# ---------- 交互式选择 ----------

def pick_song(songs):
    if not songs:
        print("没有找到歌曲")
        return None
    for i, s in enumerate(songs):
        m, sec = divmod(s["duration"], 60)
        print(f"  [{i}] {s['name']} - {s['artists']} ({s['album']}) [{m}:{sec:02d}]")
    while True:
        choice = input(f"\n选择歌曲 (0-{len(songs)-1}, q 退出): ").strip()
        if choice.lower() == "q":
            return None
        try:
            idx = int(choice)
            if 0 <= idx < len(songs):
                return songs[idx]
        except ValueError:
            pass


def pick_playlist(playlists):
    if not playlists:
        print("没有歌单")
        return None
    for i, pl in enumerate(playlists):
        print(f"  [{i}] {pl['name']} ({pl['track_count']}首) - {pl['creator']}")
    while True:
        choice = input(f"\n选择歌单 (0-{len(playlists)-1}, q 退出): ").strip()
        if choice.lower() == "q":
            return None
        try:
            idx = int(choice)
            if 0 <= idx < len(playlists):
                return playlists[idx]
        except ValueError:
            pass


# ---------- 播放 ----------

def _find_player():
    for name in ["mpv", "ffplay"]:
        path = subprocess.run(["which", name], capture_output=True, text=True).stdout.strip()
        if path:
            return name, path
    return None, None


def play_audio(url, title=""):
    """播放单首歌曲，放完后自动结束"""
    player_name, player_path = _find_player()
    if player_name == "mpv":
        cmd = [player_path, "--no-video", url]
    elif player_name == "ffplay":
        cmd = [player_path, "-nodisp", "-autoexit", "-loglevel", "error", url]
    else:
        print("未找到播放器，正在下载音频...")
        return _download_audio(url, title)

    print(f"播放: {title}")
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except KeyboardInterrupt:
        print("\n播放已停止")
        raise
    return True


def play_n_songs(songs, n):
    """连续播放前 N 首可播放歌曲"""
    if n <= 0 or not songs:
        return
    count = min(n, len(songs))
    print(f"\n===== 连续播放 {count} 首 =====")
    for i, s in enumerate(songs[:count]):
        m, sec = divmod(s["duration"], 60)
        print(f"\n[{i+1}/{count}] {s['name']} - {s['artists']} [{m}:{sec:02d}]")
        try:
            play_audio(s["url"], f"{s['name']} - {s['artists']}")
        except KeyboardInterrupt:
            print("\n播放已终止")
            return
        except Exception as e:
            print(f"\n播放失败，跳过: {e}")
    print(f"\n===== 播放完毕，共 {count} 首 =====")


def play_n_minutes(songs, minutes):
    """连续播放直到累计时长达到指定分钟数"""
    if minutes <= 0 or not songs:
        return
    target_sec = minutes * 60
    acc = 0
    print(f"\n===== 连续播放 {minutes} 分钟 =====")
    idx = 0
    for s in songs:
        if acc >= target_sec:
            break
        idx += 1
        m, sec = divmod(s["duration"], 60)
        remain_sec = target_sec - acc
        remain_m, remain_s = divmod(remain_sec, 60)
        print(f"\n[{idx}] {s['name']} - {s['artists']} [{m}:{sec:02d}] (已播 {acc//60}分{acc%60}秒, 还需 {remain_m}分{remain_s}秒)")
        try:
            play_audio(s["url"], f"{s['name']} - {s['artists']}")
        except KeyboardInterrupt:
            print("\n播放已终止")
            return
        except Exception as e:
            print(f"\n播放失败，跳过: {e}")
        acc += s["duration"]
    total_m, total_s = divmod(acc, 60)
    print(f"\n===== 播放完毕，共 {idx} 首，累计 {total_m}分{total_s}秒 =====")


def _download_audio(url, title=""):
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "", "".join(c for c in title if c.isalnum() or c in " _-"))[:50]
    if not safe:
        safe = f"song_{int(time.time())}"
    filepath = Path(f"/tmp/{safe}.mp3")
    if filepath.exists():
        filepath = Path(f"/tmp/{safe}_{int(time.time()*1000)%10000}.mp3")
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r下载中... {pct:.1f}%", end="", flush=True)
        print(f"\n已保存: {filepath}")
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False


# ---------- 统计 ----------

def _fmt_dur(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}小时{m}分{s}秒"
    return f"{m}分{s}秒"


def _filter_by_artist(songs, artist_keyword):
    """按歌手名过滤歌曲"""
    if not artist_keyword:
        return songs
    kw = artist_keyword.lower()
    return [s for s in songs if kw in s.get("artists", "").lower() or kw in s.get("name", "").lower()]


def _check_playable_batch(songs, cookies):
    """批量检测可播放性"""
    playable = []
    unplayable = []
    total = len(songs)
    for i, s in enumerate(songs):
        ok, url, info = check_playable(s["id"], cookies)
        if ok:
            playable.append({**s, "url": url, "quality": info})
        else:
            unplayable.append({**s, "reason": info})
        pct = (i + 1) / total * 100
        print(f"\r检测进度: {i+1}/{total} ({pct:.0f}%)", end="", flush=True)
    return playable, unplayable


def _print_stats(songs, playable, unplayable, label=""):
    """打印统计结果"""
    total_dur = sum(s["duration"] for s in songs)
    p_dur = sum(s["duration"] for s in playable)
    u_dur = sum(s["duration"] for s in unplayable)

    print(f"\n{'='*40}")
    if label:
        print(f"  {label}")
    print(f"  总匹配: {len(songs)} 首, 总时长 {_fmt_dur(total_dur)}")
    print(f"  可播放: {len(playable)} 首, 总时长 {_fmt_dur(p_dur)}")
    print(f"  不可播放: {len(unplayable)} 首, 总时长 {_fmt_dur(u_dur)}")
    print(f"{'='*40}")

    if songs:
        print(f"\n歌曲列表:")
        for i, s in enumerate(songs):
            m, sec = divmod(s["duration"], 60)
            print(f"  [{i}] {s['name']} - {s['artists']} [{m}:{sec:02d}]")

    if unplayable:
        print(f"\n不可播放歌曲:")
        for s in unplayable:
            m, sec = divmod(s["duration"], 60)
            print(f"  {s['name']} - {s['artists']} [{m}:{sec:02d}] ({s.get('reason', '未知')})")

    return {"songs": songs, "playable": playable, "unplayable": unplayable}


def stats_search(keyword, max_results=50, cookies=None):
    """方式一: 通过搜索统计歌手歌曲"""
    if cookies is None:
        cookies = _get_cookies_dict()
    print(f"\n[搜索统计] 正在搜索: {keyword} ...")
    songs = search_all_songs(keyword, max_results, cookies)
    if not songs:
        print("未找到歌曲")
        return None

    print(f"\n正在检测可播放性...")
    playable, unplayable = _check_playable_batch(songs, cookies)
    return _print_stats(songs, playable, unplayable, f"搜索: {keyword}")


def stats_playlist(playlist_id, artist_filter=None, cookies=None):
    """方式二: 通过歌单统计（可选按歌手过滤）"""
    if cookies is None:
        cookies = _get_cookies_dict()
    print(f"\n[歌单统计] 正在加载歌单: {playlist_id} ...")
    tracks = get_playlist_tracks(playlist_id, cookies)
    if not tracks:
        print("歌单为空或加载失败")
        return None

    filtered = _filter_by_artist(tracks, artist_filter)
    label = f"歌单: {playlist_id}"
    if artist_filter:
        label += f" (歌手过滤: {artist_filter})"

    print(f"\n正在检测可播放性...")
    playable, unplayable = _check_playable_batch(filtered, cookies)
    return _print_stats(filtered, playable, unplayable, label)


def stats_daily(artist_filter=None, cookies=None):
    """方式三: 通过每日推荐统计"""
    if cookies is None:
        cookies = _get_cookies_dict()
    print(f"\n[每日推荐统计] 正在获取推荐 ...")
    songs = daily_recommend(cookies)
    if not songs:
        print("未获取到每日推荐")
        return None

    filtered = _filter_by_artist(songs, artist_filter)
    label = "每日推荐"
    if artist_filter:
        label += f" (歌手过滤: {artist_filter})"

    print(f"\n正在检测可播放性...")
    playable, unplayable = _check_playable_batch(filtered, cookies)
    return _print_stats(filtered, playable, unplayable, label)


def artist_play(artist_name, max_results=50, cookies=None):
    """指定歌手, 搜索并返回可播放歌曲列表(跳过统计打印)"""
    if cookies is None:
        cookies = _get_cookies_dict()
    print(f"\n搜索歌手: {artist_name} ...")
    songs = search_all_songs(artist_name, max_results, cookies)
    if not songs:
        print("未找到歌曲")
        return None

    # 只保留该歌手的歌
    kw = artist_name.lower()
    artist_songs = [s for s in songs if kw in s.get("artists", "").lower()]
    if not artist_songs:
        print(f"搜索结果中未找到歌手 '{artist_name}' 的歌曲")
        return None

    print(f"找到 {len(artist_songs)} 首, 正在检测可播放性...")
    playable, _ = _check_playable_batch(artist_songs, cookies)
    if not playable:
        print("没有可播放的歌曲")
        return None

    total_dur = sum(s["duration"] for s in playable)
    m, s = divmod(total_dur, 60)
    print(f"可播放: {len(playable)} 首, 总时长 {m}分{s}秒")
    return playable


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description="网易云音乐命令行播放器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python netease_player.py login -p 13800138000            # 手机号+密码登录
  python netease_player.py login -p 13800138000 --sms      # 短信验证码登录
  python netease_player.py login -p user@example.com       # 邮箱登录
  python netease_player.py login --qr                      # 二维码登录
  python netease_player.py search 周杰伦                    # 搜索并播放
  python netease_player.py stats-search 周杰伦               # 搜索统计歌曲数/时长
  python netease_player.py stats-search 周杰伦 --play-n 5    # 统计后连播5首
  python netease_player.py stats-search 周杰伦 --play-min 30 # 统计后连播30分钟
  python netease_player.py stats-playlist 123456             # 歌单统计
  python netease_player.py stats-playlist 123456 -a 周杰伦  # 歌单中某歌手统计
  python netease_player.py stats-daily                      # 每日推荐统计
  python netease_player.py stats-daily -a 周杰伦             # 每日推荐中某歌手统计
  python netease_player.py artist 周杰伦                      # 指定歌手，交互选歌播放
  python netease_player.py artist 周杰伦 --play-n 10          # 播放周杰伦 10 首
  python netease_player.py artist 周杰伦 --play-min 30        # 播放周杰伦 30 分钟
  python netease_player.py playlist                          # 浏览歌单
  python netease_player.py daily                             # 每日推荐
  python netease_player.py play --id 123456                  # 按ID播放
  python netease_player.py status                            # 查看登录状态
        """,
    )
    sub_cmd = parser.add_subparsers(dest="cmd")

    p_login = sub_cmd.add_parser("login", help="登录")
    p_login.add_argument("-p", "--phone", help="手机号或邮箱")
    p_login.add_argument("-P", "--password", help="密码")
    p_login.add_argument("--sms", action="store_true", help="短信验证码登录")
    p_login.add_argument("--qr", action="store_true", help="二维码登录")

    sub_cmd.add_parser("status", help="查看登录状态")

    p_search = sub_cmd.add_parser("search", help="搜索歌曲")
    p_search.add_argument("keyword")
    p_search.add_argument("-n", "--limit", type=int, default=20)
    p_search.add_argument("--lyrics", action="store_true", help="显示歌词")

    p_play = sub_cmd.add_parser("play", help="播放指定 ID 歌曲")
    p_play.add_argument("--id", type=int, required=True)
    p_play.add_argument("--lyrics", action="store_true", help="显示歌词")
    p_play.add_argument("--level", default="standard",
                        choices=["standard", "higher", "exhigh", "lossless", "hires"])

    p_list = sub_cmd.add_parser("playlist", help="浏览歌单")
    p_list.add_argument("--lyrics", action="store_true", help="显示歌词")

    p_daily = sub_cmd.add_parser("daily", help="每日推荐")
    p_daily.add_argument("--lyrics", action="store_true", help="显示歌词")

    p_ss = sub_cmd.add_parser("stats-search", help="搜索统计歌曲数/时长")
    p_ss.add_argument("keyword", help="歌手名或关键词")
    p_ss.add_argument("-n", "--max", type=int, default=50, help="最大搜索数量")
    p_ss.add_argument("--play-n", type=int, default=0, metavar="N", help="统计后连续播放前 N 首")
    p_ss.add_argument("--play-min", type=int, default=0, metavar="M", help="统计后连续播放 M 分钟")

    p_sp = sub_cmd.add_parser("stats-playlist", help="歌单统计歌曲数/时长")
    p_sp.add_argument("playlist_id", type=int, help="歌单 ID")
    p_sp.add_argument("-a", "--artist", help="按歌手名过滤")
    p_sp.add_argument("--play-n", type=int, default=0, metavar="N", help="统计后连续播放前 N 首")
    p_sp.add_argument("--play-min", type=int, default=0, metavar="M", help="统计后连续播放 M 分钟")

    p_sd = sub_cmd.add_parser("stats-daily", help="每日推荐统计")
    p_sd.add_argument("-a", "--artist", help="按歌手名过滤")
    p_sd.add_argument("--play-n", type=int, default=0, metavar="N", help="统计后连续播放前 N 首")
    p_sd.add_argument("--play-min", type=int, default=0, metavar="M", help="统计后连续播放 M 分钟")

    p_artist = sub_cmd.add_parser("artist", help="指定歌手播放作品")
    p_artist.add_argument("artist_name", help="歌手名")
    p_artist.add_argument("-n", "--max", type=int, default=50, help="最大搜索数量")
    p_artist.add_argument("--play-n", type=int, default=0, metavar="N", help="播放前 N 首")
    p_artist.add_argument("--play-min", type=int, default=0, metavar="M", help="播放 M 分钟")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "login":
        if args.qr:
            login_qr()
            return
        if not args.phone:
            sys.exit("请提供手机号/邮箱 (-p)")
        if "@" in args.phone:
            pwd = args.password or input("密码: ")
            login_email(args.phone, pwd)
        else:
            if args.sms:
                login_cellphone(args.phone, password=None)
            else:
                pwd = args.password or input("密码: ")
                login_cellphone(args.phone, pwd)
        return

    if args.cmd == "status":
        check_login()
        return

    if not check_login():
        return

    cookies = _get_cookies_dict()

    if args.cmd == "search":
        songs = search_songs(args.keyword, args.limit, cookies)
        song = pick_song(songs)
        if song is None:
            return
        url = get_song_url(song["id"], cookies=cookies)
        if url is None:
            print("无法获取播放地址")
            return
        if args.lyrics:
            show_lyrics(song["id"], cookies)
        play_audio(url, f"{song['name']} - {song['artists']}")

    elif args.cmd == "play":
        url = get_song_url(args.id, args.level, cookies)
        if url is None:
            print("无法获取播放地址")
            return
        if args.lyrics:
            show_lyrics(args.id, cookies)
        play_audio(url, str(args.id))

    elif args.cmd == "playlist":
        uid = get_uid(cookies)
        if not uid:
            sys.exit("无法获取用户 ID")
        playlists = get_user_playlists(uid, cookies)
        pl = pick_playlist(playlists)
        if pl is None:
            return
        print(f"\n加载歌单: {pl['name']} ...")
        tracks = get_playlist_tracks(pl["id"], cookies)
        song = pick_song(tracks)
        if song is None:
            return
        url = get_song_url(song["id"], cookies=cookies)
        if url is None:
            print("无法获取播放地址")
            return
        if args.lyrics:
            show_lyrics(song["id"], cookies)
        play_audio(url, f"{song['name']} - {song['artists']}")

    elif args.cmd == "daily":
        songs = daily_recommend(cookies)
        song = pick_song(songs)
        if song is None:
            return
        url = get_song_url(song["id"], cookies=cookies)
        if url is None:
            print("无法获取播放地址")
            return
        if args.lyrics:
            show_lyrics(song["id"], cookies)
        play_audio(url, f"{song['name']} - {song['artists']}")

    elif args.cmd == "stats-search":
        result = stats_search(args.keyword, args.max, cookies)
        if result is None or not result.get("playable"):
            print("\n没有可播放的歌曲")
            return
        if args.play_n > 0:
            play_n_songs(result["playable"], args.play_n)
        elif args.play_min > 0:
            play_n_minutes(result["playable"], args.play_min)
        else:
            song = pick_song(result["playable"])
            if song:
                play_audio(song["url"], f"{song['name']} - {song['artists']}")

    elif args.cmd == "stats-playlist":
        result = stats_playlist(args.playlist_id, args.artist, cookies)
        if result is None or not result.get("playable"):
            print("\n没有可播放的歌曲")
            return
        if args.play_n > 0:
            play_n_songs(result["playable"], args.play_n)
        elif args.play_min > 0:
            play_n_minutes(result["playable"], args.play_min)
        else:
            song = pick_song(result["playable"])
            if song:
                play_audio(song["url"], f"{song['name']} - {song['artists']}")

    elif args.cmd == "stats-daily":
        result = stats_daily(args.artist, cookies)
        if result is None or not result.get("playable"):
            print("\n没有可播放的歌曲")
            return
        if args.play_n > 0:
            play_n_songs(result["playable"], args.play_n)
        elif args.play_min > 0:
            play_n_minutes(result["playable"], args.play_min)
        else:
            song = pick_song(result["playable"])
            if song:
                play_audio(song["url"], f"{song['name']} - {song['artists']}")

    elif args.cmd == "artist":
        songs = artist_play(args.artist_name, args.max, cookies)
        if songs is None:
            return
        if args.play_n > 0:
            play_n_songs(songs, args.play_n)
        elif args.play_min > 0:
            play_n_minutes(songs, args.play_min)
        else:
            song = pick_song(songs)
            if song:
                play_audio(song["url"], f"{song['name']} - {song['artists']}")


if __name__ == "__main__":
    main()
