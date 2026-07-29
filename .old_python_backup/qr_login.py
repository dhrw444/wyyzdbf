#!/usr/bin/env python3
"""通过二维码登录网易云音乐"""

import sys
import time
import qrcode
import io

sys.path.insert(0, "/workspace")
from netease_player import _api_post, _save_cookies

import requests

session = requests.Session()

key_data = _api_post("https://music.163.com/weapi/login/qrcode/unikey", {"type": "1"})
unikey = key_data.get("unikey")
if not unikey:
    print(f"获取二维码 key 失败: {key_data}")
    sys.exit(1)

qr_url = f"https://music.163.com/login?codekey={unikey}"

qr = qrcode.QRCode()
qr.add_data(qr_url)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")

buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

img_path = "/tmp/netease_qr.png"
img.save(img_path)
print(f"二维码图片已生成: {img_path}")
print(f"链接: {qr_url}")
print("请用网易云音乐 APP 扫码登录...")

for i in range(60):
    result = _api_post(
        "https://music.163.com/weapi/login/qrcode/client/login",
        {"key": unikey, "type": "1"},
        cookies=session.cookies,
    )
    code = result.get("code")
    if code == 803:
        _save_cookies(session)
        nickname = result.get("profile", {}).get("nickname", "用户")
        print(f"\n登录成功 - {nickname}")
        sys.exit(0)
    elif code == 800:
        time.sleep(3)
    elif code == 801:
        if i % 3 == 0:
            print("等待扫码...")
        time.sleep(3)
    elif code == 802:
        print("请在手机上确认登录...")
        time.sleep(3)
    else:
        time.sleep(3)

print("\n扫码超时，请重试")
sys.exit(1)
