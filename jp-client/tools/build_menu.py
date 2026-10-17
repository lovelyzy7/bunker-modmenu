#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_menu.py — 编译菜单 APK 并解包提取注入所需文件

流程:
  1) Gradle + NDK 编译 modmenu/ → app-debug.apk（已是最新则询问是否跳过）
  2) apktool 解包该 APK → build/menu_apktool/（smali + libniermenu.so）

可用参数:
  --yes        所有提问直接取默认（无人值守）
  --no-input   非交互（等价 --yes，且错误即退出）
  --no-build   跳过 Gradle 编译，直接使用已有 app-debug.apk
  --menu-apk   直接指定菜单 APK 文件（跳过编译）
"""
import argparse
import os
import shutil

import _common as C


def newest_mtime(path):
    if os.path.isfile(path):
        return os.path.getmtime(path)
    newest = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            newest = max(newest, os.path.getmtime(os.path.join(root, f)))
    return newest


def menu_source_mtime():
    t = newest_mtime(os.path.join(C.MODMENU, 'app', 'src'))
    for f in ('app/build.gradle', 'build.gradle', 'settings.gradle', 'gradle.properties'):
        p = os.path.join(C.MODMENU, f)
        if os.path.isfile(p):
            t = max(t, os.path.getmtime(p))
    return t


def gen_build_bat(cfg, tools=None):
    """生成 gradle 构建批处理（自动带好 JAVA_HOME / ANDROID_HOME）"""
    os.makedirs(C.BUILD_DIR, exist_ok=True)
    bat = os.path.join(C.BUILD_DIR, '_menu_build.bat')
    tools = tools or {}
    java_home = C.to_windows_style(cfg.get('java_home') or tools.get('java_home') or '')
    android_home = C.to_windows_style(cfg.get('android_home') or tools.get('android_home') or '')
    gradle_home = C.to_windows_style(cfg.get('gradle_user_home') or '')
    lines = ['@echo off', 'chcp 65001 >nul 2>nul', 'set PYTHONUTF8=1']
    if java_home:
        lines.append('set JAVA_HOME=' + java_home)
    if android_home:
        lines.append('set ANDROID_HOME=' + android_home)
        lines.append('set ANDROID_SDK_ROOT=' + android_home)
    if gradle_home:
        lines.append('set GRADLE_USER_HOME=' + gradle_home)
    lines.append('cd /d ' + C.win_path(C.MODMENU))
    lines.append('call gradlew.bat assembleDebug --no-daemon --console=plain')
    with open(bat, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')
    C.log('构建脚本: ' + bat)
    return bat


def build_apk(cfg, tools=None, auto_yes=False, no_input=False, no_build=False, menu_apk=None):
    if menu_apk:
        p = C.local_path(menu_apk)
        if not os.path.isfile(p):
            C.die('指定的菜单 APK 不存在: ' + menu_apk)
        C.log('使用指定菜单 APK: ' + p)
        return p
    if no_build:
        if not os.path.isfile(C.MENU_APK):
            C.die('--no-build 但未找到已有菜单 APK: ' + C.MENU_APK)
        C.log('跳过编译（--no-build），使用已有菜单 APK')
        return C.MENU_APK
    if os.path.isfile(C.MENU_APK) and menu_source_mtime() <= os.path.getmtime(C.MENU_APK):
        if C.ask_yes_no('modmenu/ 没有新改动，跳过编译？（可省约 30 秒）', True, auto_yes, no_input):
            C.log('跳过编译（菜单无改动）')
            return C.MENU_APK
    bat = gen_build_bat(cfg, tools)
    C.log('开始编译菜单（Gradle + NDK，约 30~60 秒）...')
    if C.IS_WSL:
        C.run(['cmd.exe', '/c', C.win_path(bat)])
    else:
        C.run(['cmd.exe', '/c', bat])
    if not os.path.isfile(C.MENU_APK):
        C.die('未生成菜单 APK: ' + C.MENU_APK)
    C.log('菜单 APK: %s (%.1f KB)' % (C.MENU_APK, os.path.getsize(C.MENU_APK) / 1024))
    return C.MENU_APK


def extract(cfg, tools, menu_apk):
    """apktool 解包菜单 APK（每次重建，保证是最新 smali/so）"""
    if os.path.isdir(C.MENU_APKTOOL):
        shutil.rmtree(C.MENU_APKTOOL)
    C.run([tools['java'], '-jar', C.local_path(tools['apktool_jar']),
           'd', menu_apk, '-o', C.MENU_APKTOOL, '-f'])
    so = os.path.join(C.MENU_APKTOOL, 'lib', 'arm64-v8a', 'libniermenu.so')
    if not os.path.isfile(so):
        C.die('解包结果缺少 libniermenu.so: ' + so)
    C.log('已提取 smali + libniermenu.so (%.1f KB)' % (os.path.getsize(so) / 1024))


def main():
    ap = argparse.ArgumentParser(description='编译菜单 APK 并提取注入文件')
    ap.add_argument('--yes', action='store_true', help='所有提问取默认值')
    ap.add_argument('--no-input', action='store_true', help='非交互模式')
    ap.add_argument('--no-build', action='store_true', help='跳过 Gradle 编译')
    ap.add_argument('--menu-apk', help='直接指定菜单 APK 文件')
    args = ap.parse_args()

    C.init_log('build_menu')
    cfg = C.load_toolpaths()
    tools = C.detect_tools(cfg)

    C.log('=== 1/2 编译菜单 APK ===')
    menu_apk = build_apk(cfg, tools, args.yes, args.no_input, args.no_build, args.menu_apk)
    C.log('=== 2/2 解包提取 smali + so ===')
    extract(cfg, tools, menu_apk)
    C.log('完成: build/menu_apktool 已就绪')


if __name__ == '__main__':
    main()
