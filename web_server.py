#!/usr/bin/env python3
"""网易云音乐命令行播放器 Web 控制台"""

import json
import os
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPT_DIR, "netease_player.py")


def run_cmd(args, timeout=120):
    """执行 netease_player.py 命令，返回 stdout, stderr, exit_code, success"""
    cmd = [sys.executable, SCRIPT] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=SCRIPT_DIR)
        output = proc.stdout + proc.stderr
        return {
            "success": proc.returncode == 0,
            "code": proc.returncode,
            "output": output.strip() or "(no output)",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "code": -1, "output": "命令执行超时 (>120s)"}
    except Exception as e:
        return {"success": False, "code": -1, "output": str(e)}


def check_status():
    """检查登录状态"""
    result = run_cmd(["status"])
    is_logged = "已登录" in result["output"]
    return {"logged_in": is_logged, "output": result["output"]}


def get_html():
    return open(os.path.join(SCRIPT_DIR, "index.html"), encoding="utf-8").read()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_html().encode("utf-8"))
            return

        if path == "/api/status":
            self._send_json(check_status())
            return

        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/exec":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            cmd_str = body.get("cmd", "").strip()

            if not cmd_str:
                self._send_json({"success": False, "output": "请输入命令"}, 400)
                return

            args = cmd_str.split()
            if args[0] in ("login",) and ("--qr" in args):
                self._send_json({"success": False, "output": "二维码登录请在终端执行，网页不支持扫码"})
                return

            result = run_cmd(args, timeout=180)
            self._send_json(result)
            return

        self.send_error(404)


def main():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running at http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
