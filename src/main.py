# -*- coding: utf-8 -*-
"""
校园网自动登录工具 - 北京朝阳校园网 专用版
Dr.COM（城市热点）认证系统，固定表单字段，无自适应分析
"""

import configparser
import logging
import os
import socket
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import requests


# ============================================================
#  配置读写
# ============================================================

def get_config_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'config.ini')
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config():
    config = configparser.ConfigParser()
    config_path = get_config_path()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在：{config_path}")
    config.read(config_path, encoding='utf-8')
    return config


# ============================================================
#  HTTP 会话
# ============================================================

def create_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    return session


# ============================================================
#  网络检测
# ============================================================

def get_local_ip():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith('127.') or ip.startswith('169.254.'):
            return None
        return ip
    except Exception:
        return None


def tcp_check(host, port=80, timeout=3):
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def wait_for_network(host, port, timeout, interval):
    elapsed = 0
    while elapsed < timeout:
        local_ip = get_local_ip()
        if local_ip and tcp_check(host, port):
            logging.info(f"网络就绪 (本机IP: {local_ip}, 耗时: {elapsed}秒)")
            return True
        elapsed += interval
        time.sleep(interval)
    return False


# ============================================================
#  Dr.COM 认证登录
# ============================================================

def drcom_login(config):
    """Dr.COM 用户登录 - POST 到登录页面自身（80端口表单提交）"""
    login_url = config.get('server', 'login_url')
    username = config.get('account', 'username')
    password = config.get('account', 'password')
    save_password = config.get('account', 'save_password') == '1'

    session = create_session()

    # 1. GET 登录页获取 cookie 和隐藏字段
    logging.info(f"GET {login_url}")
    resp = session.get(login_url, timeout=15, allow_redirects=True)
    logging.info(f"登录页状态码: {resp.status_code}, 内容长度: {len(resp.text)} 字符")

    # 2. 构造表单提交参数（模拟浏览器表单 POST）
    post_data = {
        'DDDDD': username,         # Dr.COM 账号字段
        'upass': password,         # Dr.COM 密码字段
        '0MKKey': 'Login',         # 登录按钮
        'R1': '0',
        'R2': '0',
        'R3': '0',
        'R6': '0',
        'para': '00',
    }
    if save_password:
        post_data['savePassword'] = '1'

    # 3. POST 到登录页面（80端口，模拟表单提交）
    logging.info(f"POST {login_url}")
    resp = session.post(login_url, data=post_data, timeout=15, allow_redirects=True)
    logging.info(f"登录响应状态码: {resp.status_code}, 内容长度: {len(resp.text)} 字符")
    logging.info(f"响应URL: {resp.url}")

    # 诊断：输出响应前 500 字符到日志
    snippet = resp.text[:500].replace('\n', ' ').replace('\r', '')
    logging.info(f"响应内容(前500字符): {snippet}")

    # 也保存完整响应用于排查
    debug_path = os.path.join(os.path.dirname(get_config_path()), 'response_debug.html')
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(resp.text)
    logging.info(f"完整响应已保存至: {debug_path}")

    success = check_drcom_success(resp.text)
    return success, resp.text


def check_drcom_success(html):
    """检查 Dr.COM 认证是否成功"""
    html_lower = html.lower()

    # Dr.COM 特定成功标志
    drcom_markers = [
        'Dr.COMWebLoginID_3.htm',     # 内部成功页跳转
        '认证成功',
        '登录成功',
        '上线成功',
        'already online',
        'keepalive',
        '您已在线',
        '注销',                        # 出现注销链接说明已登录
    ]

    for kw in drcom_markers:
        if kw.lower() in html_lower:
            logging.info(f"检测到成功标志: {kw}")
            return True

    # 如果响应内容很短且状态码200，可能是重定向后的成功
    if len(html.strip()) < 200:
        logging.info(f"响应内容很短({len(html.strip())}字符)，可能是成功重定向")
        return True

    return False


# ============================================================
#  弹窗提示
# ============================================================

def show_popup(title, message, auto_close=0):
    import tkinter as tk
    from tkinter import messagebox

    def _show():
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        if auto_close > 0:
            root.after(auto_close * 1000, root.destroy)
        messagebox.showinfo(title, message)
        try:
            root.destroy()
        except Exception:
            pass

    t = threading.Thread(target=_show, daemon=True)
    t.start()
    if auto_close > 0:
        t.join(timeout=auto_close + 5)


# ============================================================
#  日志配置
# ============================================================

def setup_logging():
    log_dir = os.path.dirname(get_config_path())
    log_path = os.path.join(log_dir, 'login.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
        ]
    )


# ============================================================
#  主入口
# ============================================================

def main():
    setup_logging()
    logging.info("=" * 40)
    logging.info("校园网自动登录程序启动 (北京朝阳校园网 Dr.COM版)")

    # 1. 加载配置
    try:
        config = load_config()
    except FileNotFoundError as e:
        show_popup("错误", f"配置文件缺失\n\n{get_config_path()}\n\n请确保 config.ini 与本程序在同一目录")
        logging.error(str(e))
        sys.exit(1)

    # 2. 解析网络目标
    login_url = config.get('server', 'login_url')
    parsed = urlparse(login_url)
    host = parsed.hostname

    timeout = config.getint('settings', 'wait_network_timeout')
    interval = config.getint('settings', 'retry_interval')

    # 3. 等待网络就绪
    logging.info(f"等待网络就绪：{host}:80（最长{timeout}秒）...")
    if not wait_for_network(host, 80, timeout, interval):
        msg = f"网络连接超时\n\n{host} 不可达\n已等待 {timeout} 秒"
        show_popup("网络超时 ⏰", msg)
        logging.error(msg)
        sys.exit(1)

    # 4. 执行 Dr.COM 认证登录
    try:
        success, html = drcom_login(config)
    except requests.exceptions.SSLError as e:
        msg = f"SSL证书验证失败\n\n详情: {e}"
        show_popup("登录失败 ❌", msg)
        logging.error(f"SSL错误: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        msg = f"无法连接到认证服务器\n\n{host} 连接失败\n详情: {e}"
        show_popup("登录失败 ❌", msg)
        logging.error(f"连接错误: {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        msg = "请求超时\n\n认证服务器响应时间过长"
        show_popup("登录失败 ❌", msg)
        logging.error("请求超时")
        sys.exit(1)
    except Exception as e:
        msg = f"登录请求异常\n\n{str(e)}"
        show_popup("登录失败 ❌", msg)
        logging.error(msg)
        sys.exit(1)

    # 5. 提示结果
    if success:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = f"校园网已连接 ✅\n\n当前时间：{now}"
        show_popup("登录成功", msg, auto_close=10)
        logging.info("登录成功")
    else:
        msg = "校园网登录失败 ❌\n\n请检查账号密码是否正确\n详情见 login.log"
        show_popup("登录失败 ❌", msg)
        logging.error("登录失败：未检测到成功标志")


if __name__ == '__main__':
    main()
