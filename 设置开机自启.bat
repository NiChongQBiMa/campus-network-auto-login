@echo off
chcp 65001 >nul
title 校园网自动登录 - 开机自启设置

echo ========================================
echo     校园网自动登录 - 开机自启动设置
echo ========================================
echo.

:: 获取启动文件夹路径
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

:: 当前 exe 所在目录
set "EXE_DIR=%~dp0"
set "EXE_PATH=%EXE_DIR%校园网登录.exe"

:: 检查 exe 是否存在
if not exist "%EXE_PATH%" (
    echo [错误] 未找到 校园网登录.exe
    echo 请将此脚本放在与 exe 相同的目录下运行
    pause
    exit /b 1
)

:: 创建快捷方式
set "SHORTCUT=%STARTUP%\校园网登录.lnk"

:: 使用 PowerShell 创建快捷方式
powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $s = $ws.CreateShortcut('%SHORTCUT%'); ^
     $s.TargetPath = '%EXE_PATH%'; ^
     $s.WorkingDirectory = '%EXE_DIR%'; ^
     $s.WindowStyle = 7; ^
     $s.Save(); ^
     Write-Host '快捷方式已创建'"

if exist "%SHORTCUT%" (
    echo ✅ 设置成功！
    echo.
    echo 快捷方式位置：%SHORTCUT%
    echo 程序位置：%EXE_PATH%
    echo.
    echo 下次开机时将自动运行校园网登录程序。
) else (
    echo ❌ 设置失败，请以管理员身份运行此脚本
)

echo.
echo 按任意键退出...
pause >nul
