#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_all.py — 一键总流程：编译菜单 → 解包目标 APK → 注入 → 打包 → 签名

由 build.bat / build.sh（或 build_patched.bat/.sh）调用，也可单独运行:
  python3 tools/build_all.py --auto --yes              # 自动识别私服补丁版 APK
  python3 tools/build_all.py --target patched --tag v1.0.2
"""
import argparse
import os

import _common as C
import build_menu
import inject_modmenu


def main():
    ap = argparse.ArgumentParser(description='一键构建 菜单版 APK')
    ap.add_argument('--target', choices=['patched'],
                    help='固定为 patched（私服补丁版 + 菜单）；本脚本只负责编辑/导出 APK，不做安装')
    ap.add_argument('--auto', action='store_true',
                    help='自动扫描 resources/ 等目录里的 APK 并判断类型（不给 --target 时默认启用）')
    ap.add_argument('--apk', help='直接指定输入 APK（默认读 tools/targets.json）')
    ap.add_argument('--out', help='输出 APK 路径（默认 dist/nier-mod-menu-<target>[-tag].apk）')
    ap.add_argument('--tag', default='', help='输出文件名后缀，如 v1.0.2')
    ap.add_argument('--work', help='解包工作目录（默认 build/work_<target>）')
    ap.add_argument('--fresh', action='store_true', help='强制重新解包目标 APK')
    ap.add_argument('--no-build', action='store_true', help='跳过菜单编译（用已有 app-debug.apk）')
    ap.add_argument('--menu-apk', help='直接指定菜单 APK')
    ap.add_argument('--yes', action='store_true', help='所有提问取默认值')
    ap.add_argument('--no-input', action='store_true', help='非交互模式')
    args = ap.parse_args()

    C.init_log('build_%s' % (args.target or 'auto'))
    cfg = C.load_toolpaths()
    targets = C.load_json(C.TARGETS, {})
    tools = C.detect_tools(cfg)

    # ---- 输入 APK（未指定 --target 时自动识别）----
    target = args.target
    if (not target) or args.auto:
        if args.apk and not target:
            target = C.guess_target_kind(os.path.basename(args.apk))
        else:
            auto_apk, auto_kind = C.auto_detect_apk(args.yes, args.no_input)
            if not auto_apk:
                C.die('未找到输入 APK：把原版 / 私服补丁版 APK 放到 resources/ 目录，'
                      '或在 tools/targets.json 里配置路径')
            args.apk = auto_apk
            target = auto_kind
        C.log('自动识别: %s → 目标=%s' % (os.path.basename(args.apk), target))

    # ---- 输入 APK ----
    if args.apk:
        apk = C.local_path(args.apk)
        if not os.path.isfile(apk):
            C.die('输入 APK 不存在: ' + args.apk)
    else:
        apk = C.resolve_apk(target, targets, args.yes, args.no_input)
        if not apk:
            C.die('未找到 %s 输入 APK。\n'
                  '  请把你的 APK 放到 ../resources/，或在 tools/targets.json 里配置 "%s" 路径。'
                  % (target, target))

    tag = args.tag or C.ask_text('输出文件名后缀 tag（可留空，如 v1.0.2）', '', args.yes, args.no_input)
    work = args.work or os.path.join(C.BUILD_DIR, 'work_' + target)
    _ctag = 'en' if os.path.basename(C.ROOT).lower().startswith('en') else (
            'jp' if os.path.basename(C.ROOT).lower().startswith('jp') else '')
    out = args.out or os.path.join(C.DIST_DIR, 'nier-mod-menu-%s%s%s.apk' % (
        (_ctag + '-') if _ctag else '', target, ('-' + tag) if tag else ''))

    C.log('目标: %s | 输入: %s (%.1f MB)' % (target, apk, os.path.getsize(apk) / 1024 / 1024))
    C.log('输出: %s' % out)

    # ---- 1. 编译菜单 + 提取 ----
    C.log('=== 1/4 编译菜单 APK 并提取 smali/so ===')
    menu_apk = build_menu.build_apk(cfg, tools, args.yes, args.no_input, args.no_build, args.menu_apk)
    build_menu.extract(cfg, tools, menu_apk)

    # ---- 2. 解包目标 APK ----
    C.log('=== 2/4 解包/复用目标 APK ===')
    inject_modmenu.ensure_work(apk, work, tools, args.fresh, args.yes, args.no_input)

    # ---- 3. 注入 + 打包签名 ----
    C.log('=== 3/4 注入菜单 ===')
    inject_modmenu.inject_smali(work)
    inject_modmenu.inject_manifest(work)
    inject_modmenu.inject_start_call(work)
    C.log('=== 4/4 重建 + 对齐 + 签名 ===')
    inject_modmenu.build_and_sign(tools, work, out)

    # ---- 结果 ----
    C.log('========================================')
    C.log('完成: %s (%.1f MB)' % (out, os.path.getsize(out) / 1024 / 1024))
    C.log('SHA256: ' + C.sha256_file(out))
    cert = C.cert_sha256(out, tools)
    if cert:
        C.log('签名证书SHA256: ' + cert)
    C.log('========================================')


if __name__ == '__main__':
    main()
