# Agent Rules — 校园网自动登录项目

## Git 使用规则

1. **仅使用 CLI 命令**：所有 Git 操作（add、commit、checkout、branch、merge 等）必须通过终端 `git` 命令行执行，禁止使用 VS Code GUI 或 `run_vscode_command` 进行 Git 操作。
2. **自动生成提交信息**：每次提交由 Agent 自动生成中文 commit message，格式为 `type: 简短描述`（如 `fix: 修复端口配置`、`feat: 新增xxx功能`），无需用户确认。
3. **提交粒度**：每个独立改动完成后立即提交，保持原子性。
4. **分支命名**：使用中文描述性名称（如 `北京朝阳校园网1`），便于识别。
5. **禁止 force push**：不得对 `main` 或共享分支执行 `--force` 操作。

## 代码规范

- Python 3.8 兼容（保证 Win7 可运行）
- 配置文件使用 `configparser` + INI 格式，UTF-8 编码
- 日志使用标准 `logging` 模块，输出到文件
- 弹窗使用 `tkinter.messagebox`

## 打包规范

- 使用 Python 3.8 的 PyInstaller 打包
- 命令：`pyinstaller --onefile --noconsole --name 校园网登录 src/main.py`
- 输出到 `dist/`，工作目录 `build38/`

## 项目结构约定

```
src/main.py          — 主程序（单文件）
config.example.ini   — 配置模板（不含真实密码）
CHANGELOG.md         — 迭代记录
AGENT.md             — 本文件
```
