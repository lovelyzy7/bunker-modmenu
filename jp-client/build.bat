@echo off
setlocal
chcp 65001 >nul 2>nul
set PYTHONUTF8=1
cd /d %~dp0

echo ============================================
echo  NieR Mod Menu 一键构建（自动识别 APK）
echo ============================================
python tools\build_all.py --auto --yes %*
if errorlevel 1 (
  echo.
  echo [失败] 请查看上方错误信息（日志在 build\logs\ 目录）
  echo 提示：本脚本只做「私服补丁版 + 菜单」。请先用 lunar-scripts 给原版打私服补丁，
  pause
  exit /b 1
)
echo.
echo [完成] 成品在 dist\ 目录
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
exit /b 0
