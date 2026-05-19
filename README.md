# 校园网自动登录 🎓

哈哈😄 各位电教委员是否因为总是忘记登录校园网而被老师骂呢？这里是我们的救星：
Windows 开机自动登录校园网认证系统，无需手动打开浏览器输入账号密码。

## 适用场景

- 学校/公司机房每天需要手动登录校园网
- Windows 7 及以上系统
- 基于 Web 表单认证的校园网系统（深澜、锐捷、华为、Dr.COM 等）

## 快速开始

### 1. 配置账号

编辑 `config.ini`，填入你的账号密码：

```ini
[account]
username = 你的学号
password = 你的密码
save_password = 1

[server]
login_url = http://10.26.13.2
```

### 2. 设置开机启动

1. 按 `Win + R`，输入 `shell:startup`，回车
2. 将 `校园网登录.exe` 的**快捷方式**放入该文件夹
3. 下次开机即自动运行

### 3. 运行效果

- 登录成功 → 弹窗提示"校园网已连接 ✅"
- 登录失败 → 弹窗提示错误原因
- 所有运行记录保存在 `login.log`

## 工作原理

```
开机启动 → 等待网络就绪 → 分析登录表单 → POST账号密码 → 弹窗提示结果
```

首次运行时会自动分析校园网页面的表单结构，写入 `config.ini` 的 `[form]` 段，后续直接读取，秒级完成登录。

## 文件说明

| 文件 | 说明 |
|------|------|
| `校园网登录.exe` | 主程序 |
| `config.ini` | 配置文件，记事本可编辑 |
| `login.log` | 运行日志 |
| `使用说明.txt` | 详细使用指南 |

## 自行打包

```bash
pip install requests beautifulsoup4 pyinstaller
pyinstaller --onefile --noconsole --name 校园网登录 main.py
```

输出文件在 `dist/` 目录下。

## 许可证

MIT License
