#!/usr/bin/env bash
# 一键构建：私服补丁版 APK + Mod 菜单
set -e
cd "$(dirname "$0")"
echo "============================================"
echo " 一键构建：私服补丁版 APK + Mod 菜单"
echo "============================================"
python3 tools/build_all.py --target patched "$@"
echo
echo "[完成] 成品在 dist/ 目录"
