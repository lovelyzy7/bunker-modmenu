#!/usr/bin/env bash
# NieR Mod Menu 一键构建（自动识别 resources/ 里的 APK）
set -e
cd "$(dirname "$0")"
python3 tools/build_all.py --auto --yes "$@"
echo
echo "[完成] 成品在 dist/ 目录"
