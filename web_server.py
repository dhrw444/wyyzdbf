#!/usr/bin/env python3
"""多账号任务执行平台 Web 服务器 - 重构版本"""

import json
import os
import subprocess
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPT_DIR, "netease_player.py")

# 全局任务管理器
task_manager = {
    'accounts': {},
    'running_tasks': {},
    'thread_pool': None,
    'max_threads': 4
}

class Account:
    def __init__(self, id, name, phone, password='', status='offline'):
        self.id = id
        self.name = name
        self.phone = phone
        self.password = password
        self.status = status  # online, offline, loading, error
        self.tasks = 0
        self.completed = 0
        self.failed = 0
        self.progress = 0
        self.running = False
        self.last_error = None

class TaskExecutor:
    def __init__(self, account_id, command, callback=None):
        self.account_id = account_id
        self.command = command
        self.callback = callback
        self.running = False
        self.thread = None

    def execute(self):
        self.running = True
        try:
            account = task_manager['accounts'].get(self.account_id)
            if account:
                account.running = True
                account.progress = 0

            result = self.run_command()

            if account:
                account.running = False
                account.progress = 100
                account.tasks += 1
                if result['success']:
                    account.completed += 1
                else:
                    account.failed += 1
                    account.last_error = result.get('output', 'Unknown error')

            if self.callback:
                self.callback(self.account_id, result)

        except Exception as e:
            if self.callback:
                self.callback(self.account_id, {
                    'success': False,
                    'output': str(e)
                })
        finally:
            self.running = False

    def run_command(self):
        """执行 netease_player.py 命令"""
        cmd = [sys.executable, SCRIPT] + self.command.split()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=SCRIPT_DIR
            )
            output = proc.stdout + proc.stderr
            return {
                "success": proc.returncode == 0,
                "code": proc.returncode,
                "output": output.strip() or "(no output)",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "code": -1,
                "output": "命令执行超时 (>180s)"
            }
        except Exception as e:
            return {
                "success": False,
                "code": -1,
                "output": str(e)
            }


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
            with open(os.path.join(SCRIPT_DIR, "index.html"), encoding="utf-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
            return

        if path == "/api/accounts":
            self._send_json(self.get_accounts_data())
            return

        if path == "/api/stats":
            self._send_json(self.get_stats())
            return

        if path == "/api/status":
            self._send_json(self.get_system_status())
            return

        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/account/add":
            return self.handle_add_account()

        if path == "/api/account/remove":
            return self.handle_remove_account()

        if path == "/api/account/relogin":
            return self.handle_relogin_account()

        if path == "/api/task/start":
            return self.handle_start_task()

        if path == "/api/task/stop":
            return self.handle_stop_task()

        if path == "/api/task/start-all":
            return self.handle_start_all()

        if path == "/api/task/stop-all":
            return self.handle_stop_all()

        if path == "/api/settings/threads":
            return self.handle_update_threads()

        if path == "/api/send-code":
            return self.handle_send_code()

        if path == "/api/verify-login":
            return self.handle_verify_login()

        if path == "/api/search":
            return self.handle_search()

        if path == "/api/play":
            return self.handle_play()

        self.send_error(404)

    def handle_add_account(self):
        """添加新账号"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        new_id = max(task_manager['accounts'].keys(), default=0) + 1
        account = Account(
            id=new_id,
            name=data.get('name', f'账号 {new_id}'),
            phone=data.get('phone', ''),
            password=data.get('password', ''),
            status='offline'
        )
        task_manager['accounts'][new_id] = account

        # 自动执行登录
        self.login_account(new_id, account.password)

        self._send_json({
            "success": True,
            "account": self.account_to_dict(account)
        })

    def handle_remove_account(self):
        """删除账号"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        account_id = data.get('id')
        if account_id in task_manager['accounts']:
            # 先停止正在运行的任务
            self.stop_account_tasks(account_id)
            del task_manager['accounts'][account_id]

            self._send_json({"success": True, "message": f"账号 {account_id} 已删除"})
        else:
            self._send_json({"success": False, "message": "账号不存在"}, 404)

    def handle_relogin_account(self):
        """重新登录账号"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        account_id = data.get('id')
        account = task_manager['accounts'].get(account_id)

        if not account:
            self._send_json({"success": False, "message": "账号不存在"}, 404)
            return

        if account.running:
            self._send_json({"success": False, "message": "账号正在执行任务"}, 400)
            return

        # 模拟重新登录
        account.status = 'loading'
        self.login_account(account_id, account.password)

        self._send_json({"success": True, "message": f"重新登录中... 账号 {account_id}"})

    def handle_start_task(self):
        """启动单个账号的任务"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        account_id = data.get('account_id')
        command = self.get_task_command()

        account = task_manager['accounts'].get(account_id)
        if not account:
            self._send_json({"success": False, "message": "账号不存在"}, 404)
            return

        if account.running:
            self._send_json({"success": False, "message": "账号正在执行任务"}, 400)
            return

        if account.status != 'online':
            self._send_json({"success": False, "message": "账号未在线，请先登录"}, 400)
            return

        self.start_account_task(account_id, command)
        self._send_json({"success": True, "message": f"任务已启动 - 账号 {account_id}"})

    def handle_stop_task(self):
        """停止单个账号的任务"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        account_id = data.get('account_id') or data.get('id')
        stopped = self.stop_account_tasks(account_id)

        if stopped:
            self._send_json({"success": True, "message": f"任务已停止 - 账号 {account_id}"})
        else:
            self._send_json({"success": False, "message": "没有正在运行的任务"}, 400)

    def handle_start_all(self):
        """启动所有在线账号的任务"""
        command = self.get_task_command()

        started = []
        for account_id, account in task_manager['accounts'].items():
            if account.status == 'online' and not account.running:
                self.start_account_task(account_id, command)
                started.append(account_id)

        if not started:
            message = "没有可执行的账号（请确保账号在线且未在执行中）"
        else:
            message = f"已启动 {len(started)} 个账号的任务"

        self._send_json({
            "success": True,
            "message": message,
            "started": started
        })

    def handle_stop_all(self):
        """停止所有正在运行的任务"""
        stopped = []
        for account_id in list(task_manager['running_tasks'].keys()):
            if self.stop_account_tasks(account_id):
                stopped.append(account_id)

        self._send_json({
            "success": True,
            "message": f"已停止 {len(stopped)} 个账号的任务",
            "stopped": stopped
        })

    def handle_update_threads(self):
        """更新线程池大小"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))

        thread_count = data.get('max_threads', 4)
        task_manager['max_threads'] = max(1, min(16, thread_count))

        # 重新创建线程池
        if task_manager['thread_pool']:
            task_manager['thread_pool'].shutdown(wait=False)
        task_manager['thread_pool'] = ThreadPoolExecutor(max_workers=task_manager['max_threads'])

        self._send_json({
            "success": True,
            "message": f"线程池大小已更新为 {task_manager['max_threads']}"
        })

    def handle_send_code(self):
        """发送验证码"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        phone = data.get("phone", "").strip()

        if not phone:
            self._send_json({"success": False, "message": "请输入手机号"}, 400)
            return

        import re
        if not re.match(r'^1[3-9]\d{9}$', phone):
            self._send_json({"success": False, "message": "手机号格式不正确"}, 400)
            return

        try:
            from netease_player import send_sms_code
            ok = send_sms_code(phone)
            if ok:
                self._send_json({"success": True, "message": "验证码已发送", "expires": 120})
            else:
                self._send_json({"success": False, "message": "发送验证码失败，请检查手机号是否正确"}, 400)
        except Exception as e:
            self._send_json({"success": False, "message": "发送验证码失败: " + str(e)}, 400)

    def handle_verify_login(self):
        """验证码登录"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        phone = data.get("phone", "").strip()
        code = data.get("code", "").strip()

        if not phone or not code:
            self._send_json({"success": False, "message": "请填写手机号和验证码"}, 400)
            return

        import re
        if not re.match(r'^1[3-9]\d{9}$', phone):
            self._send_json({"success": False, "message": "手机号格式不正确"}, 400)
            return

        if not re.match(r'^\d{6}$', code):
            self._send_json({"success": False, "message": "验证码格式不正确"}, 400)
            return

        try:
            from netease_player import login_with_captcha
            ok = login_with_captcha(phone, code)
            if ok:
                new_id = max(task_manager['accounts'].keys(), default=0) + 1
                account = Account(
                    id=new_id,
                    name=f'账号 {new_id}',
                    phone=phone,
                    password='',
                    status='online'
                )
                task_manager['accounts'][new_id] = account

                self._send_json({
                    "success": True,
                    "message": "登录成功",
                    "account": self.account_to_dict(account)
                })
            else:
                self._send_json({"success": False, "message": "验证码错误或账号不存在"}, 400)
        except Exception as e:
            self._send_json({"success": False, "message": "验证码验证失败: " + str(e)}, 400)
        except Exception as e:
            self._send_json({
                "success": False,
                "message": "发送验证码失败: " + str(e)
            }, 400)

    def handle_verify_login(self):
        """验证码登录"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        phone = data.get("phone", "").strip()
        code = data.get("code", "").strip()

        if not phone or not code:
            self._send_json({"success": False, "message": "请填写手机号和验证码"}, 400)
            return

        # 验证手机号格式
        import re
        phone_reg = r'^1[3-9]\d{9}$'
        if not re.match(phone_reg, phone):
            self._send_json({"success": False, "message": "手机号格式不正确"}, 400)
            return

        # 验证验证码格式
        if not re.match(r'^\d{6}$', code):
            self._send_json({"success": False, "message": "验证码格式不正确"}, 400)
            return

        # 直接调用login_cellphone函数进行验证码登录
        try:
            from netease_player import login_cellphone
            result = login_cellphone(phone, password=code)
            if result is not False:
                # 获取用户信息
                new_id = max(task_manager['accounts'].keys(), default=0) + 1
                account = Account(
                    id=new_id,
                    name=f'账号 {new_id}',
                    phone=phone,
                    password='',
                    status='online'
                )
                task_manager['accounts'][new_id] = account

                self._send_json({
                    "success": True,
                    "message": "登录成功",
                    "account": self.account_to_dict(account)
                })
            else:
                self._send_json({
                    "success": False,
                    "message": "验证码错误或账号不存在"
                }, 400)
        except Exception as e:
            self._send_json({
                "success": False,
                "message": "验证码验证失败: " + str(e)
            }, 400)

    def handle_search(self):
        """处理搜索请求"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        keyword = data.get("keyword", "")

        if not keyword:
            self._send_json({"success": False, "message": "请提供搜索关键词"}, 400)
            return

        try:
            result = self.run_search_command(keyword)
            self._send_json(result)
        except Exception as e:
            self._send_json({"success": False, "message": f"搜索失败: {str(e)}"}, 500)

    def handle_play(self):
        """处理播放歌曲"""
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        song_id = data.get("song_id")

        if not song_id:
            self._send_json({"success": False, "message": "请提供歌曲ID"}, 400)
            return

        # 获取第一个在线账号播放
        online_account = None
        for account in task_manager['accounts'].values():
            if account.status == 'online':
                online_account = account
                break

        if not online_account:
            self._send_json({"success": False, "message": "没有在线账号可用，请先登录账号"}, 400)
            return

        try:
            result = self.run_play_command(song_id)
            self._send_json({
                "success": result['success'],
                "song_id": song_id,
                "output": result.get('output', '')
            })
        except Exception as e:
            self._send_json({"success": False, "message": f"播放失败: {str(e)}"}, 500)

    def login_account(self, account_id, password):
        """执行账号登录"""
        account = task_manager['accounts'].get(account_id)
        if not account:
            return False

        account.status = 'loading'
        result = self.run_login_command(account.phone, password)

        if result['success']:
            account.status = 'online'
            return True
        else:
            account.status = 'error'
            account.last_error = result.get('output', '登录失败')
            return False

    def start_account_task(self, account_id, command):
        """启动账号任务"""
        account = task_manager['accounts'].get(account_id)
        if not account:
            return False

        if not command:
            command = self.get_task_command()

        executor = TaskExecutor(account_id, command, self.task_completed_callback)
        task_manager['running_tasks'][account_id] = executor

        # 使用线程池执行
        if not task_manager['thread_pool']:
            task_manager['thread_pool'] = ThreadPoolExecutor(max_workers=task_manager['max_threads'])

        task_manager['thread_pool'].submit(executor.execute)
        return True

    def stop_account_tasks(self, account_id):
        """停止账号任务"""
        if account_id in task_manager['running_tasks']:
            executor = task_manager['running_tasks'][account_id]
            executor.running = False

            account = task_manager['accounts'].get(account_id)
            if account:
                account.running = False
                account.progress = 0

            del task_manager['running_tasks'][account_id]
            return True
        return False

    def task_completed_callback(self, account_id, result):
        """任务完成回调"""
        print(f"任务完成 - 账号 {account_id}: {result['success']}")

    def account_to_dict(self, account):
        """转换账号对象为字典"""
        return {
            'id': account.id,
            'name': account.name,
            'phone': account.phone,
            'status': account.status,
            'tasks': account.tasks,
            'completed': account.completed,
            'failed': account.failed,
            'progress': account.progress,
            'running': account.running,
            'last_error': account.last_error
        }

    def get_accounts_data(self):
        """获取所有账号数据"""
        return {
            'accounts': [
                self.account_to_dict(account)
                for account in task_manager['accounts'].values()
            ]
        }

    def get_stats(self):
        """获取统计信息"""
        accounts = task_manager['accounts'].values()
        total_tasks = sum(a.tasks for a in accounts)
        completed_tasks = sum(a.completed for a in accounts)
        failed_tasks = sum(a.failed for a in accounts)

        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        return {
            'total_accounts': len(accounts),
            'online_accounts': sum(1 for a in accounts if a.status == 'online'),
            'running_accounts': sum(1 for a in accounts if a.running),
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks,
            'success_rate': round(success_rate, 2),
            'max_threads': task_manager['max_threads'],
            'active_threads': len(task_manager['running_tasks'])
        }

    def get_system_status(self):
        """获取系统状态"""
        accounts = task_manager['accounts'].values()
        return {
            'online': sum(1 for a in accounts if a.status == 'online'),
            'running': sum(1 for a in accounts if a.running),
            'offline': sum(1 for a in accounts if a.status == 'offline'),
            'total': len(accounts)
        }

    def get_task_command(self):
        """根据当前设置获取任务命令"""
        # 这里可以从前端获取任务类型和参数
        # 临时返回默认命令
        return "search 周杰伦"

    def run_search_command(self, keyword):
        """执行搜索命令"""
        cmd = [sys.executable, SCRIPT, 'search', keyword]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=SCRIPT_DIR
            )
            output = proc.stdout + proc.stderr
            lines = output.strip().split('\n')

            # 解析搜索结果
            songs = []
            for line in lines:
                # 简单的解析逻辑，实际可能需要更复杂的解析
                if line.strip() and not line.startswith('[') and line.count('-') > 0:
                    parts = line.split('-')
                    if len(parts) >= 2:
                        name_part = parts[0].strip().strip('[]').strip()
                        info_part = parts[1].strip()

                        # 提取歌曲信息
                        song_id = abs(hash(name_part)) % 1000000  # 生成模拟ID
                        duration = 180 + (abs(hash(info_part)) % 300)  # 模拟时长

                        songs.append({
                            'id': song_id,
                            'name': name_part,
                            'artists': '网易云音乐',
                            'album': '专辑',
                            'duration': duration
                        })

            return {
                "success": proc.returncode == 0,
                "songs": songs,
                "output": output.strip()
            }
        except Exception as e:
            return {
                "success": False,
                "songs": [],
                "output": str(e)
            }

    def run_play_command(self, song_id):
        """执行播放命令"""
        cmd = [sys.executable, SCRIPT, 'play', '--id', str(song_id)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=SCRIPT_DIR
            )
            output = proc.stdout + proc.stderr
            return {
                "success": proc.returncode == 0,
                "output": output.strip()
            }
        except Exception as e:
            return {
                "success": False,
                "output": str(e)
            }

    def run_login_command(self, phone, password):
        """执行登录命令"""
        cmd = [sys.executable, SCRIPT, 'login', '-p', phone, '-P', password]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=SCRIPT_DIR
            )
            output = proc.stdout + proc.stderr
            return {
                "success": proc.returncode == 0,
                "output": output.strip()
            }
        except Exception as e:
            return {
                "success": False,
                "output": str(e)
            }


def init_demo_accounts():
    """初始化演示账号"""
    # 不再自动创建虚构账号
    pass


def main():
    port = int(os.environ.get("PORT", 8000))

    # 初始化线程池
    task_manager['thread_pool'] = ThreadPoolExecutor(max_workers=task_manager['max_threads'])

    # 初始化演示账号
    init_demo_accounts()

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🚀 多账号任务执行平台已启动")
    print(f"🌐 访问地址: http://0.0.0.0:{port}")
    print(f"⚡ 最大并发数: {task_manager['max_threads']}")
    print(f"📊 当前账号数: {len(task_manager['accounts'])}")
    print(f"📋 任务类型: 播放/统计/每日推荐/自定义")
    print(f"🔍 搜索功能: 独立页面")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器正在关闭...")
        if task_manager['thread_pool']:
            task_manager['thread_pool'].shutdown(wait=True)
        print("✅ 服务器已关闭")


if __name__ == "__main__":
    main()