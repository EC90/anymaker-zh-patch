@echo off
chcp 65001 >nul
title Anymaker 简中汉化 - 卸载
where python >nul 2>nul
if errorlevel 1 (
  echo [!] 未检测到 Python。可改用 Release 里的 anymaker-zh-installer.exe uninstall，
  echo     或用 Steam：库 → 右键 Anymaker → 属性 → 已安装文件 → 验证文件完整性。
  pause
  exit /b 1
)
python "%~dp0安装汉化.py" uninstall
echo.
pause
