@echo off
chcp 65001 >nul
title Anymaker 简中汉化 - 安装
where python >nul 2>nul
if errorlevel 1 (
  echo [!] 未检测到 Python。两种解决办法：
  echo     1. 安装 Python 3.8+（https://www.python.org/downloads/ 勾选 Add to PATH^)后重试
  echo     2. 改用 Release 里的 anymaker-zh-installer.exe（免 Python，双击运行^)
  pause
  exit /b 1
)
python "%~dp0安装汉化.py" install
echo.
pause
