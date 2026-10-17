@echo off
setlocal
chcp 65001 >nul 2>nul
set PYTHONUTF8=1
cd /d %~dp0
echo ============================================
echo  一键构建：私服补丁版 APK + Mod 菜单
echo ============================================
python tools\build_all.py --target patched --yes %*
if errorlevel 1 (
  echo.
  echo [失败] 请查看上方错误信息（日志在 build\logs\ 目录）
  echo 提示：请确认已把私服补丁版 APK 放到 ..\resources\ 或修改 tools\targets.json
  pause
  exit /b 1
)
echo.
echo [完成] 成品在 dist\ 目录
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
exit /b 0
