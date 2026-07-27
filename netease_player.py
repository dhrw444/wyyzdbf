#!/usr/bin/env python3
"""网易云音乐命令行播放器 - 登录 / 搜索 / 播放"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import pickle
import random
import subprocess
import sys
import time
from pathlib import Path

import requests
from Cryptodome.Cipher import AES

CONFIG_DIR = Path.home() / ".netease_player"
COOKIE_FILE = CONFIG_DIR / "cookies.pkl"
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
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
        data = json.dumps(data)
    data_bytes = data.encode("utf-8")
    secret = binascii.hexlify(os.urandom(16))[:16]
    params = _aes_encrypt(_aes_encrypt(data_bytes, NONCE), secret).decode()
    enc_sec_key = _rsa_encrypt(secret, PUBKEY, MODULUS)
    return {"params": params, "encSecKey": enc_sec_key}


def _api_post(url, data, cookies=None):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://music.163.com",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    encrypted = _encrypt_params(data)
    resp = requests.post(url, data=encrypted, headers=headers, cookies=cookies, timeout=15)
    return resp.json()


def _save_cookies(session):
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(session.cookies.get_dict(), f)


def _load_cookies():
    if not COOKIE_FILE.exists():
        return None
    with open(COOKIE_FILE, "rb") as f:
        return pickle.load(f)


def _md5(text):
    return hashlib.md5(text.encode()).hexdigest()


# ---------- 登录 ----------

def login_cellphone(phone, password=None, countrycode="86"):
    session = requests.Session()

    if password:
        md5_pwd = _md5(password)
        data = {"phone": phone, "countrycode": countrycode, "password": md5_pwd, "rememberLogin": "true"}
        result = _api_post("https://music.163.com/weapi/login/cellphone", data, cookies=session.cookies)
        if result.get("code") == 200:
            _save_cookies(session)
            nickname = result.get("profile", {}).get("nickname", phone)
            print(f"登录成功 - {nickname}")
            return session
        sys.exit(f"登录失败 [{result.get('code')}]: {result.get('message', result)}")

    # 无密码则发验证码
    result = _api_post(
        "https://music.163.com/weapi/sms/captcha/sent",
        {"cellphone": phone, "ctcode": countrycode},
    )
    if result.get("code") != 200:
        sys.exit(f"发送验证码失败: {result}")

    print("验证码已发送，请查收短信")
    captcha = input("请输入短信验证码: ").strip()
    data = {
        "phone": phone,
        "countrycode": countrycode,
        "captcha": captcha,
        "rememberLogin": "true",
    }
    result = _api_post("https://music.163.com/weapi/login/cellphone", data, cookies=session.cookies)
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
    result = _api_post("https://music.163.com/weapi/login", data, cookies=session.cookies)
    if result.get("code") == 200:
        _save_cookies(session)
        nickname = result.get("profile", {}).get("nickname", email)
        print(f"登录成功 - {nickname}")
        return session
    sys.exit(f"登录失败 [{result.get('code')}]: {result.get('message', result)}")


def login_qr():
    session = requests.Session()

    key_data = _api_post("https://music.163.com/weapi/login/qrcode/unikey", {"type": "1"})
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
            cookies=session.cookies,
        )
        code = result.get("code")
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
            print(f"状态: {result}")
            time.sleep(3)
    sys.exit("扫码超时")


def get_session():
    cookies = _load_cookies()
    if cookies is None:
        return None
    session = requests.Session()
    session.cookies.update(cookies)
    return session


def check_login():
    session = get_session()
    if session is None:
        print("未登录，请先执行: python netease_player.py login -p <手机号>")
        return None

    result = _api_post(
        "https://music.163.com/weapi/w/nuser/account/get",
        {},
        cookies=session.cookies,
    )
    if result.get("code") == 200:
        profile = result.get("profile", {})
        print(f"已登录 - {profile.get('nickname', 'N/A')} (UID: {profile.get('userId', 'N/A')})")
        return session
    print("登录态已过期，请重新登录")
    return None


# ---------- 搜索 ----------

def search_songs(keyword, limit=20):
    session = get_session()
    if session is None:
        return None

    data = {
        "s": keyword,
        "type": "1",
        "limit": str(limit),
        "offset": "0",
        "total": "true",
    }
    result = _api_post(
        "https://music.163.com/weapi/cloudsearch/get/web",
        data,
        cookies=session.cookies,
    )
    if result.get("code") != 200:
        print(f"搜索失败: {result}")
        return []

    songs = result.get("result", {}).get("songs", [])
    results = []
    for song in songs:
        artists = "/".join(a.get("name", "") for a in song.get("ar", []))
        album = song.get("al", {}).get("name", "N/A")
        duration = song.get("dt", 0) // 1000
        results.append({
            "id": song["id"],
            "name": song["name"],
            "artists": artists,
            "album": album,
            "duration": duration,
        })
    return results


# ---------- 获取播放地址 ----------

def get_song_url(song_id, level="standard"):
    session = get_session()
    if session is None:
        return None

    level_map = {
        "standard": "standard",
        "higher": "higher",
        "exhigh": "exhigh",
        "lossless": "lossless",
        "hires": "hires",
    }
    data = {"ids": f"[{song_id}]", "level": level_map.get(level, level), "encodeType": "aac"}
    result = _api_post(
        "https://music.163.com/weapi/song/enhance/player/url/v1",
        data,
        cookies=session.cookies,
    )
    if result.get("code") != 200:
        print(f"获取歌曲地址失败: {result}")
        return None

    song_data = result.get("data", [])
    if not song_data:
        return None

    info = song_data[0]
    if info.get("code") == 200 and info.get("url"):
        br = info.get("br", 0) // 1000
        print(f"音质: {br}kbps")
        return info["url"]

    code_map = {
        -110: "无版权或需要 VIP",
        -104: "需要 VIP",
    }
    msg = code_map.get(info.get("code"), f"code={info.get('code')}")
    print(f"无法获取播放地址: {msg}")
    return None


# ---------- 歌词 ----------

def get_lyrics(song_id):
    session = get_session()
    if session is None:
        return None

    result = _api_post(
        "https://music.163.com/weapi/song/lyric",
        {"id": str(song_id), "lv": -1, "tv": -1, "csrf_token": ""},
        cookies=session.cookies,
    )
    if result.get("code") != 200:
        return None
    lrc = result.get("lrc", {})
    return lrc.get("lyric", "")


def show_lyrics(song_id):
    lyrics = get_lyrics(song_id)
    if lyrics:
        print("\n--- 歌词 ---")
        for line in lyrics.strip().split("\n"):
            clean = line.strip()
            if clean and not any(clean.startswith(f"[{tag}:") for tag in ("ti", "ar", "al", "by", "offset")):
                print(clean)
        print("------------\n")


# ---------- 歌单 ----------

def get_user_playlists(uid):
    session = get_session()
    if session is None:
        return None

    data = {"uid": str(uid), "wordwrap": "7", "offset": "0", "total": "true", "limit": "1000"}
    result = _api_post(
        "https://music.163.com/weapi/user/playlist",
        data,
        cookies=session.cookies,
    )
    if result.get("code") != 200:
        print(f"获取歌单失败: {result}")
        return []

    playlists = result.get("playlist", [])
    return [
        {
            "id": pl["id"],
            "name": pl["name"],
            "track_count": pl.get("trackCount", 0),
            "creator": pl.get("creator", {}).get("nickname", ""),
        }
        for pl in playlists
    ]


def get_playlist_tracks(playlist_id):
    session = get_session()
    if session is None:
        return None

    result = _api_post(
        "https://music.163.com/api/v3/playlist/detail",
        {"id": str(playlist_id), "total": "true", "limit": "1000", "n": "1000", "offset": "0"},
        cookies=session.cookies,
    )
    if result.get("code") != 200:
        print(f"获取歌单详情失败: {result}")
        return []

    tracks = result.get("playlist", {}).get("tracks", [])
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "artists": "/".join(a.get("name", "") for a in t.get("ar", [])),
            "album": t.get("al", {}).get("name", "N/A"),
            "duration": t.get("dt", 0) // 1000,
        }
        for t in tracks
    ]


# ---------- 每日推荐 ----------

def daily_recommend():
    session = get_session()
    if session is None:
        return None

    result = _api_post(
        "https://music.163.com/weapi/v2/discovery/recommend/songs",
        {"csrf_token": ""},
        cookies=session.cookies,
    )
    if result.get("code") != 200:
        print(f"获取每日推荐失败 [{result.get('code')}]: {result.get('message', result)}")
        return []

    songs = result.get("data", {}).get("dailySongs", [])
    if not songs:
        print("未获取到每日推荐 (可能是当天已生成过推荐)")
        return []

    return [
        {
            "id": s["id"],
            "name": s["name"],
            "artists": "/".join(a.get("name", "") for a in s.get("ar", [])),
            "album": s.get("al", {}).get("name", "N/A"),
            "duration": s.get("dt", 0) // 1000,
        }
        for s in songs
    ]


# ---------- 交互式选择 ----------

def pick_song(songs):
    if not songs:
        print("没有找到歌曲")
        return None
    for i, s in enumerate(songs):
        mins, secs = divmod(s["duration"], 60)
        print(f"  [{i}] {s['name']} - {s['artists']} ({s['album']}) [{mins}:{secs:02d}]")
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

def play_audio(url, title=""):
    """播放单首歌曲，放完后自动结束"""
    mpv_path = subprocess.run(["which", "mpv"], capture_output=True, text=True).stdout.strip()
    ffplay_path = subprocess.run(["which", "ffplay"], capture_output=True, text=True).stdout.strip()

    if mpv_path:
        cmd = [mpv_path, "--no-video", url]
    elif ffplay_path:
        cmd = [ffplay_path, "-nodisp", "-autoexit", url]
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
        print(f"\n[{idx}] {s['name']} - {s['artists']} [{m}:{sec:02d}] (已播放 {acc//60}分{acc%60}秒, 剩余 {remain_m}分{remain_s}秒)")
        try:
            play_audio(s["url"], f"{s['name']} - {s['artists']}")
        except KeyboardInterrupt:
            print("\n播放已终止")
            return
        acc += s["duration"]
    total_m, total_s = divmod(acc, 60)
    print(f"\n===== 播放完毕，共 {idx} 首，累计 {total_m}分{total_s}秒 =====")

    print("未找到 mpv / ffplay，正在下载音频...")
    return _download_audio(url, title)


def _download_audio(url, title=""):
    safe = "".join(c for c in title if c.isalnum() or c in " _-") or "song"
    filepath = Path(f"/tmp/{safe}.mp3")
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

def search_all_songs(keyword, max_results=50):
    """搜索歌手/关键词，获取尽可能多的歌曲"""
    all_songs = []
    offset = 0
    while len(all_songs) < max_results:
        remain = max_results - len(all_songs)
        batch = min(remain, 30)
        data = {
            "s": keyword,
            "type": "1",
            "limit": str(batch),
            "offset": str(offset),
            "total": "true",
        }
        result = _api_post(
            "https://music.163.com/weapi/cloudsearch/get/web",
            data,
            cookies=get_session().cookies if get_session() else {},
        )
        if result.get("code") != 200:
            break
        songs = result.get("result", {}).get("songs", [])
        if not songs:
            break
        for song in songs:
            artists = "/".join(a.get("name", "") for a in song.get("ar", []))
            duration = song.get("dt", 0) // 1000
            all_songs.append({
                "id": song["id"],
                "name": song["name"],
                "artists": artists,
                "album": song.get("al", {}).get("name", "N/A"),
                "duration": duration,
            })
        offset += batch
    return all_songs


def check_playable(song_id):
    """检测单首歌曲是否可播放"""
    data = {"ids": f"[{song_id}]", "level": "standard", "encodeType": "aac"}
    result = _api_post(
        "https://music.163.com/weapi/song/enhance/player/url/v1",
        data,
        cookies=get_session().cookies if get_session() else {},
    )
    if result.get("code") != 200:
        return False, None, ""
    info = result.get("data", [{}])[0]
    if info.get("code") == 200 and info.get("url"):
        return True, info["url"], f"{info.get('br', 0) // 1000}kbps"
    reason_map = {-110: "无版权", -104: "需VIP", -100: "已下架"}
    return False, None, reason_map.get(info.get("code"), f"不可用(code={info.get('code')})")


def stats_artist(keyword, max_results=50):
    """统计某歌手/关键词的歌曲数和总时长"""
    print(f"\n正在搜索: {keyword} ...")
    songs = search_all_songs(keyword, max_results)
    if not songs:
        print("未找到歌曲")
        return None

    total_duration = sum(s["duration"] for s in songs)
    total_min, total_sec = divmod(total_duration, 60)
    total_hour = total_min // 60
    total_min = total_min % 60

    print(f"\n===== 搜索结果统计 =====")
    print(f"匹配歌曲: {len(songs)} 首")
    print(f"总时长: {total_hour}小时{total_min}分{total_sec}秒")
    print(f"========================\n")

    print("歌曲列表:")
    for i, s in enumerate(songs):
        m, sec = divmod(s["duration"], 60)
        print(f"  [{i}] {s['name']} - {s['artists']} [{m}:{sec:02d}]")

    # 检测可播放性
    print(f"\n正在检测可播放歌曲...")
    playable = []
    unplayable = []
    for i, s in enumerate(songs):
        ok, url, info = check_playable(s["id"])
        if ok:
            playable.append({**s, "url": url, "quality": info})
        else:
            unplayable.append({**s, "reason": info})
        pct = (i + 1) / len(songs) * 100
        print(f"\r检测进度: {i+1}/{len(songs)} ({pct:.0f}%)", end="", flush=True)

    p_duration = sum(s["duration"] for s in playable)
    p_min, p_sec = divmod(p_duration, 60)

    u_duration = sum(s["duration"] for s in unplayable)
    u_min, u_sec = divmod(u_duration, 60)

    print(f"\n\n===== 可播放性分析 =====")
    print(f"可播放: {len(playable)} 首, 总时长 {p_min}分{p_sec}秒")
    print(f"不可播放: {len(unplayable)} 首, 总时长 {u_min}分{u_sec}秒")

    if unplayable:
        print(f"\n不可播放歌曲:")
        for s in unplayable:
            m, sec = divmod(s["duration"], 60)
            print(f"  {s['name']} - {s['artists']} [{m}:{sec:02d}] ({s.get('reason', '未知')})")

    return {"songs": songs, "playable": playable, "unplayable": unplayable}


# ---------- CLI ----------

def _fmt_duration(sec):
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(
        description="网易云音乐命令行播放器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python netease_player.py login -p 13800138000          # 手机号+密码登录
  python netease_player.py login -p 13800138000 --sms    # 手机号+短信验证码登录
  python netease_player.py login -p user@example.com     # 邮箱登录
  python netease_player.py login --qr                    # 二维码登录
  python netease_player.py search 周杰伦                  # 搜索歌曲
  python netease_player.py stats 周杰伦                   # 统计歌手歌曲数/时长+可播放分析
  python netease_player.py stats 周杰伦 --play-n 5        # 统计后连续播放前5首
  python netease_player.py stats 周杰伦 --play-min 30     # 统计后连续播放30分钟
  python netease_player.py playlist                      # 我的歌单
  python netease_player.py daily                         # 每日推荐
  python netease_player.py play --id 123456              # 按ID播放
  python netease_player.py status                        # 查看登录状态
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

    p_list = sub_cmd.add_parser("playlist", help="我的歌单")
    p_list.add_argument("--lyrics", action="store_true", help="显示歌词")

    p_daily = sub_cmd.add_parser("daily", help="每日推荐")
    p_daily.add_argument("--lyrics", action="store_true", help="显示歌词")

    p_stats = sub_cmd.add_parser("stats", help="统计歌手歌曲数/时长 + 可播放性")
    p_stats.add_argument("keyword", help="歌手名或关键词")
    p_stats.add_argument("-n", "--max", type=int, default=50, help="最大搜索数量")
    p_stats.add_argument("--play-n", type=int, default=0, metavar="N", help="统计后连续播放前 N 首")
    p_stats.add_argument("--play-min", type=int, default=0, metavar="M", help="统计后连续播放 M 分钟")

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

    session = check_login()
    if session is None:
        return

    if args.cmd == "search":
        songs = search_songs(args.keyword, args.limit)
        song = pick_song(songs)
        if song is None:
            return
        url = get_song_url(song["id"])
        if url is None:
            return
        if args.lyrics:
            show_lyrics(song["id"])
        play_audio(url, f"{song['name']} - {song['artists']}")

    elif args.cmd == "play":
        url = get_song_url(args.id, args.level)
        if url is None:
            return
        if args.lyrics:
            show_lyrics(args.id)
        play_audio(url, str(args.id))

    elif args.cmd == "playlist":
        uid_resp = _api_post(
            "https://music.163.com/weapi/w/nuser/account/get",
            {},
            cookies=session.cookies,
        )
        uid = uid_resp.get("profile", {}).get("userId")
        if not uid:
            sys.exit("无法获取用户 ID")

        playlists = get_user_playlists(uid)
        pl = pick_playlist(playlists)
        if pl is None:
            return
        print(f"\n加载歌单: {pl['name']} ...")
        tracks = get_playlist_tracks(pl["id"])
        song = pick_song(tracks)
        if song is None:
            return
        url = get_song_url(song["id"])
        if url is None:
            return
        if args.lyrics:
            show_lyrics(song["id"])
        play_audio(url, f"{song['name']} - {song['artists']}")

    elif args.cmd == "daily":
        print("获取每日推荐 ...")
        songs = daily_recommend()
        song = pick_song(songs)
        if song is None:
            return
        url = get_song_url(song["id"])
        if url is None:
            return
        if args.lyrics:
            show_lyrics(song["id"])
        play_audio(url, f"{song['name']} - {song['artists']}")

    elif args.cmd == "stats":
        result = stats_artist(args.keyword, args.max)
        if result is None:
            return
        playable = result["playable"]
        if not playable:
            print("\n没有可播放的歌曲")
            return

        if args.play_n > 0:
            play_n_songs(playable, args.play_n)
        elif args.play_min > 0:
            play_n_minutes(playable, args.play_min)
        else:
            song = pick_song(playable)
            if song is None:
                return
            play_audio(song["url"], f"{song['name']} - {song['artists']}")


if __name__ == "__main__":
    main()
