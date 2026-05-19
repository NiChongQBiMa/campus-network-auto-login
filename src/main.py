# -*- coding: utf-8 -*-
"""
校园网自动登录工具
开机自动登录校园网认证系统，支持自动分析表单结构
"""

import configparser
import logging
import os
import re
import socket
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
#  配置读写
# ============================================================

def get_config_path():
    """获取 config.ini 路径，与 exe/脚本 同目录"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'config.ini')
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config():
    """读取配置文件，不存在则报错"""
    config = configparser.ConfigParser()
    config_path = get_config_path()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在：{config_path}")
    config.read(config_path, encoding='utf-8')
    return config


def save_form_config(fields):
    """首次分析表单后，将字段映射写入 config.ini 的 [form] 段"""
    config = load_config()
    if 'form' not in config:
        config.add_section('form')
    for key, value in fields.items():
        config.set('form', key, str(value))
    with open(get_config_path(), 'w', encoding='utf-8') as f:
        config.write(f)
    logging.info(f"表单配置已保存: {fields}")


def get_base_url(config):
    """从配置获取登录页面基础地址"""
    url = config.get('server', 'login_url')
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


# ============================================================
#  网络检测
# ============================================================

def get_local_ip():
    """检查本机是否有有效IP（排除127.x和169.254.x APIPA地址）"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith('127.') or ip.startswith('169.254.'):
            return None
        return ip
    except Exception:
        return None


def tcp_check(host, port=80, timeout=3):
    """TCP 连接检测，3 秒超时"""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def wait_for_network(host, port, timeout, interval):
    """
    循环等待网络就绪
    返回: True=就绪, False=超时
    """
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
#  表单分析与登录
# ============================================================

def analyze_login_form(html, config):
    """
    解析登录页面 HTML，提取表单字段
    返回: (fields_dict, post_data_dict, action_url)
    """
    username = config.get('account', 'username')
    password = config.get('account', 'password')
    save_password = config.get('account', 'save_password') == '1'
    base_url = get_base_url(config)

    soup = BeautifulSoup(html, 'html.parser')
    forms = soup.find_all('form')
    if not forms:
        raise Exception("页面中未找到登录表单，请确认登录地址是否正确")

    form = forms[0]
    action = form.get('action', '')

    # 拼接完整 action URL
    if action.startswith('http'):
        action_url = action
    elif action.startswith('/'):
        parsed = urlparse(base_url)
        action_url = f"{parsed.scheme}://{parsed.netloc}{action}"
    else:
        action_url = base_url.rstrip('/') + '/' + action.lstrip('/')

    form_fields = {}
    post_data = {}

    # 第一遍：收集隐藏字段 + 智能匹配
    for inp in form.find_all('input'):
        name = inp.get('name', '')
        input_type = inp.get('type', 'text').lower()
        value = inp.get('value', '')

        if not name:
            continue

        if input_type == 'hidden':
            post_data[name] = value
            continue

        if input_type == 'password':
            form_fields['password_field'] = name
            post_data[name] = password
        elif re.search(r'user|account|name|id|uname|uid|stu', name, re.I):
            form_fields['username_field'] = name
            post_data[name] = username
        elif input_type == 'checkbox' and re.search(r'save|remember|keep|auto', name, re.I):
            form_fields['save_field'] = name
            if save_password:
                post_data[name] = '1'
        elif input_type == 'submit' or input_type == 'button':
            form_fields['submit_field'] = name

    # 如果没匹配到用户名字段，兜底：取第一个 type=text 的 input
    if 'username_field' not in form_fields:
        for inp in form.find_all('input'):
            if inp.get('type', 'text').lower() == 'text' and inp.get('name'):
                form_fields['username_field'] = inp['name']
                post_data[inp['name']] = username
                break

    if 'username_field' not in form_fields or 'password_field' not in form_fields:
        raise Exception("无法识别用户名或密码输入框，请联系开发者")

    form_fields['action_url'] = action_url
    logging.info(f"表单分析完成: action={action_url}, fields={form_fields}")
    return form_fields, post_data, action_url


def perform_login(config):
    """
    执行登录（含 GET 获取隐藏字段）
    返回: (success_bool, html_text)
    """
    login_url = config.get('server', 'login_url')
    username = config.get('account', 'username')
    password = config.get('account', 'password')
    save_password = config.get('account', 'save_password') == '1'
    action_url = config.get('form', 'action_url')

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.112 Safari/537.36'
    })

    # ① GET 登录页面（获取可能的 CSRF token）
    logging.info(f"GET {login_url}")
    resp = session.get(login_url, timeout=15, allow_redirects=True)

    # ② 收集隐藏字段
    post_data = {
        config.get('form', 'username_field'): username,
        config.get('form', 'password_field'): password,
    }
    if save_password and config.has_option('form', 'save_field') and config.get('form', 'save_field'):
        post_data[config.get('form', 'save_field')] = '1'

    soup = BeautifulSoup(resp.text, 'html.parser')
    for inp in soup.find_all('input', type='hidden'):
        name = inp.get('name')
        value = inp.get('value', '')
        if name and name not in post_data:
            post_data[name] = value
            logging.info(f"携带隐藏字段: {name}={value[:50] if value else ''}")

    # ③ POST 登录
    logging.info(f"POST {action_url}")
    resp = session.post(action_url, data=post_data, timeout=15, allow_redirects=True)
    logging.info(f"响应状态码: {resp.status_code}")

    success = check_login_success(resp.text)
    return success, resp.text


def check_login_success(html):
    """检查返回页面是否包含登录成功标志"""
    keywords = [
        '登录成功', '认证成功', '上线成功',
        'success', 'already online', '在线',
        '注销', 'logout', '下线',  # 出现"注销"按钮说明已登录
    ]
    html_lower = html.lower()
    for kw in keywords:
        if kw.lower() in html_lower:
            logging.info(f"检测到成功关键词: {kw}")
            return True
    return False


# ============================================================
#  弹窗提示
# ============================================================

def show_popup(title, message, auto_close=0):
    """
    弹窗提示
    auto_close: 大于0时N秒后自动关闭
    """
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
    """配置日志到文件"""
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
    logging.info("校园网自动登录程序启动")

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
    port = parsed.port or 80

    timeout = config.getint('settings', 'wait_network_timeout')
    interval = config.getint('settings', 'retry_interval')

    # 3. 等待网络就绪
    logging.info(f"等待网络就绪：{host}:{port}（最长{timeout}秒）...")
    if not wait_for_network(host, port, timeout, interval):
        msg = f"网络连接超时\n\n{host} 不可达\n已等待 {timeout} 秒"
        show_popup("网络超时 ⏰", msg)
        logging.error(msg)
        sys.exit(1)

    # 4. 检查是否有缓存表单配置
    form_configured = (
        config.has_option('form', 'action_url') and
        config.get('form', 'action_url') and
        config.has_option('form', 'username_field') and
        config.get('form', 'username_field') and
        config.has_option('form', 'password_field') and
        config.get('form', 'password_field')
    )

    if not form_configured:
        # 首次运行：分析表单
        logging.info("首次运行，分析登录表单...")
        try:
            resp = requests.get(login_url, timeout=15)
            fields, post_data, action_url = analyze_login_form(resp.text, config)
            save_form_config(fields)

            # 重新加载含 [form] 段的配置
            config = load_config()
        except Exception as e:
            msg = f"无法分析登录表单\n\n{str(e)}"
            show_popup("登录失败 ❌", msg)
            logging.error(msg)
            sys.exit(1)

    # 5. 执行登录
    try:
        success, html = perform_login(config)
    except requests.exceptions.ConnectionError:
        msg = "无法连接到校园网服务器\n\n请检查网络是否正常"
        show_popup("登录失败 ❌", msg)
        logging.error(msg)
        sys.exit(1)
    except Exception as e:
        msg = f"登录请求异常\n\n{str(e)}"
        show_popup("登录失败 ❌", msg)
        logging.error(msg)
        sys.exit(1)

    # 6. 提示结果
    if success:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = f"校园网已连接 ✅\n\n当前时间：{now}"
        show_popup("登录成功", msg, auto_close=10)
        logging.info("登录成功")
    else:
        msg = "校园网登录失败 ❌\n\n请检查账号密码是否正确\n详情见 login.log"
        show_popup("登录失败 ❌", msg)
        logging.error("登录失败：返回页面未检测到成功标志")


if __name__ == '__main__':
    main()
