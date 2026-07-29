#!/usr/bin/env python3
"""通过手机短信验证码登录网易云音乐"""

import sys
import requests

sys.path.insert(0, "/workspace")
from netease_player import _api_post, _save_cookies

session = requests.Session()

phone = input("手机号: ").strip()
if not phone:
    sys.exit("手机号不能为空")

countrycode = input("国家代码（默认86）: ").strip() or "86"

# 发送验证码
result = _api_post(
    "https://music.163.com/weapi/sms/captcha/sent",
    {"cellphone": phone, "ctcode": countrycode},
    session=session,
)
if result.get("code") != 200:
    sys.exit(f"发送验证码失败: {result}")
print("验证码已发送，请查收短信")

captcha = input("请输入短信验证码: ").strip()
if not captcha:
    sys.exit("验证码不能为空")

result = _api_post(
    "https://music.163.com/weapi/login/cellphone",
    {"phone": phone, "countrycode": countrycode, "captcha": captcha, "rememberLogin": "true"},
    session=session,
)
if result.get("code") == 200:
    _save_cookies(session)
    nickname = result.get("profile", {}).get("nickname", phone)
    print(f"登录成功 - {nickname}")
    sys.exit(0)

sys.exit(f"登录失败 [{result.get('code')}]: {result.get('message', result)}")