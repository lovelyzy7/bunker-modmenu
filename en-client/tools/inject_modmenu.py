#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_modmenu.py — 把菜单注入目标 APK（引擎）

输入：目标 APK（原版 / 私服版）
输出：已注入 + 已签名的最终 APK

流程:
  1) apktool d 目标 APK（带缓存：APK 路径+大小+mtime 指纹，未变则复用）
  2) 复制菜单 smali + libniermenu.so
  3) AndroidManifest: 加悬浮窗权限 + Launcher service（幂等）
  4) 启动 Activity 的 onCreate 注入 Main->Start（幂等）
  5) apktool b → zipalign → apksigner 签名 → 校验

可用参数:
  --target original|patched   按 tools/targets.json 定位输入 APK
  --apk <路径>                直接指定输入 APK（优先于 --target）
  --out <路径>                输出 APK（默认 dist/nier-mod-menu-<target>[-tag].apk）
  --tag vX.Y                  输出文件名后缀
  --work <目录>               解包工作目录（默认 build/work_<target>）
  --fresh                     强制重新解包（不用缓存）
  --yes / --no-input          无人值守
"""
import argparse
import os
import re
import shutil
import time

import _common as C

PERMISSION_LINE = '    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>\n'
SERVICE_LINE = ('    <service android:name="com.android.support.Launcher" android:enabled="true" '
                'android:exported="false" android:stopWithTask="true" />\n')
START_CALL = "    invoke-static {p0}, Lcom/android/support/Main;->Start(Landroid/content/Context;)V\n"
START_MARK = "Lcom/android/support/Main;->Start(Landroid/content/Context;)V"


# --------------------------------------------------------------------------
#  注入步骤
# --------------------------------------------------------------------------
def pick_smali_dir(work):
    best, best_idx = None, -1
    for name in os.listdir(work):
        m = re.fullmatch(r'smali(?:_classes(\d+))?', name)
        if m and os.path.isdir(os.path.join(work, name)):
            idx = int(m.group(1)) if m.group(1) else 1
            if idx > best_idx:
                best, best_idx = name, idx
    if not best:
        C.die('目标 APK 未找到 smali 目录')
    return os.path.join(work, best), best


def inject_smali(work):
    target_root, name = pick_smali_dir(work)
    dst = os.path.join(target_root, 'com', 'android', 'support')
    os.makedirs(dst, exist_ok=True)
    n = 0
    for sub in ('smali_classes2', 'smali'):
        src = os.path.join(C.MENU_APKTOOL, sub, 'com', 'android', 'support')
        if os.path.isdir(src):
            for fn in os.listdir(src):
                if fn.endswith('.smali'):
                    shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
                    n += 1
    if n == 0:
        C.die('未找到菜单 smali，请先运行 build_menu.py')
    C.log('菜单 smali 已注入 %s/com/android/support（%d 个文件）' % (name, n))

    so_src = os.path.join(C.MENU_APKTOOL, 'lib', 'arm64-v8a', 'libniermenu.so')
    if not os.path.isfile(so_src):
        C.die('缺少 libniermenu.so，请先运行 build_menu.py')
    lib_dst = os.path.join(work, 'lib', 'arm64-v8a')
    os.makedirs(lib_dst, exist_ok=True)
    shutil.copy2(so_src, os.path.join(lib_dst, 'libniermenu.so'))
    C.log('libniermenu.so 已注入 lib/arm64-v8a/')


def inject_manifest(work):
    path = os.path.join(work, 'AndroidManifest.xml')
    text = open(path, encoding='utf-8', errors='ignore').read()
    changed = False
    if 'SYSTEM_ALERT_WINDOW' not in text:
        i = text.find('<application')
        if i < 0:
            C.die('清单中未找到 <application>')
        ls = text.rfind('\n', 0, i) + 1
        text = text[:ls] + PERMISSION_LINE + text[ls:]
        changed = True
        C.log('已加入悬浮窗权限')
    if 'com.android.support.Launcher' not in text:
        i = text.rfind('</application>')
        if i < 0:
            C.die('清单中未找到 </application>')
        ls = text.rfind('\n', 0, i) + 1
        text = text[:ls] + SERVICE_LINE + text[ls:]
        changed = True
        C.log('已加入 Launcher service')
    if changed:
        open(path, 'w', encoding='utf-8').write(text)


def find_launcher_activity(work):
    xml = open(os.path.join(work, 'AndroidManifest.xml'), encoding='utf-8', errors='ignore').read()
    pkg = re.search(r'package="([^"]+)"', xml)
    pkg = pkg.group(1) if pkg else ''
    for m in re.finditer(r'<activity\b[^>]*?android:name="([^"]+)"[^>]*>(.*?)</activity>', xml, re.S):
        name, body = m.group(1), m.group(2)
        if 'android.intent.action.MAIN' in body and 'LAUNCHER' in body:
            return pkg + name if name.startswith('.') else name
    for m in re.finditer(r'<activity\b[^>]*?android:name="([^"]+)"[^>]*>(.*?)</activity>', xml, re.S):
        if 'android.intent.action.MAIN' in m.group(2):
            name = m.group(1)
            return pkg + name if name.startswith('.') else name
    C.die('未找到 Launcher Activity')


def inject_start_call(work):
    activity = find_launcher_activity(work)
    rel = activity.replace('.', '/') + '.smali'
    target = None
    for d in os.listdir(work):
        if re.fullmatch(r'smali(?:_classes\d+)?', d):
            p = os.path.join(work, d, rel)
            if os.path.isfile(p):
                target = p
                break
    if not target:
        C.die('未找到启动 Activity 的 smali: ' + rel)
    text = open(target, encoding='utf-8', errors='ignore').read()
    if START_MARK in text:
        C.log('启动注入已存在，跳过（%s）' % activity)
        return
    m = re.search(r'(\.method\s+[^\n]*?\bonCreate\(Landroid/os/Bundle;\)V\n)', text)
    if not m:
        C.die('该 Activity 没有 onCreate(Bundle)，需要手动注入')
    body_start = m.end()
    sup = re.search(r'[ \t]*invoke-super\s+\{p0, p1\},\s+[^\n]*->onCreate\(Landroid/os/Bundle;\)V\n',
                    text[body_start:])
    if not sup:
        C.die('onCreate 内未找到 invoke-super ...->onCreate，需要手动注入')
    pos = body_start + sup.end()
    text = text[:pos] + '\n' + START_CALL + text[pos:]
    open(target, 'w', encoding='utf-8').write(text)
    C.log('已注入 Main->Start 到 %s' % activity)


# --------------------------------------------------------------------------
#  解包缓存
# --------------------------------------------------------------------------
def stamp_of(apk):
    return '%s|%d|%d' % (os.path.abspath(apk), os.path.getsize(apk), int(os.path.getmtime(apk)))


def ensure_work(apk, work, tools, fresh=False, auto_yes=False, no_input=False):
    stamp = stamp_of(apk)
    stamp_file = os.path.join(work, '.source_stamp')
    valid = (os.path.isdir(work)
             and os.path.isfile(os.path.join(work, 'apktool.yml'))
             and os.path.isfile(stamp_file)
             and open(stamp_file).read().strip() == stamp)
    if fresh:
        C.log('--fresh：强制重新解包')
        valid = False
    elif valid:
        if not C.ask_yes_no('检测到目标 APK 的解包缓存（复用可省约 3 分钟），复用？', True, auto_yes, no_input):
            valid = False
    if not valid:
        if os.path.isdir(work):
            shutil.rmtree(work)
        C.log('解包目标 APK（约 250MB，需要几分钟）...')
        C.run([tools['java'], '-jar', C.local_path(tools['apktool_jar']), 'd', apk, '-o', work, '-f'])
        open(stamp_file, 'w', encoding='utf-8').write(stamp)
    else:
        C.log('复用解包缓存: ' + work)
    return work


# --------------------------------------------------------------------------
#  重建 + 签名
# --------------------------------------------------------------------------
def build_and_sign(tools, work, out):
    os.makedirs(C.TMP_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    base = os.path.basename(out)
    unsigned = os.path.join(C.TMP_DIR, '_unsigned_' + base)
    aligned = os.path.join(C.TMP_DIR, '_aligned_' + base)

    C.log('重建 APK（apktool b）...')
    C.run([tools['java'], '-jar', C.local_path(tools['apktool_jar']), 'b', work, '-o', unsigned])

    C.log('对齐（zipalign）...')
    if C.IS_WSL:
        C.run([C.local_path(tools['zipalign']), '-p', '-f', '4', C.win_path(unsigned), C.win_path(aligned)])
    else:
        C.run([tools['zipalign'], '-p', '-f', '4', unsigned, aligned])

    C.log('签名（apksigner）...')
    C.run([tools['java'], '-jar', C.local_path(tools['apksigner_jar']), 'sign',
           '--ks', tools['keystore'], '--ks-pass', 'pass:' + tools['ks_pass'],
           '--out', out, aligned])
    C.run([tools['java'], '-jar', C.local_path(tools['apksigner_jar']), 'verify', out])

    for f in (unsigned, aligned):
        try:
            os.remove(f)
        except OSError:
            pass



# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='把菜单注入目标 APK 并签名')
    ap.add_argument('--target', choices=['patched'], help='固定 patched（输入必须是已打私服补丁的 APK）')
    ap.add_argument('--apk', help='直接指定输入 APK 路径')
    ap.add_argument('--out', help='输出 APK 路径')
    ap.add_argument('--tag', default='', help='输出文件名后缀（如 v1.0.2）')
    ap.add_argument('--work', help='解包工作目录')
    ap.add_argument('--fresh', action='store_true', help='强制重新解包')
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--no-input', action='store_true')
    args = ap.parse_args()

    if not args.target and not args.apk:
        C.die('需要 --target original|patched 或 --apk <路径>')

    C.init_log('inject_' + (args.target or 'custom'))
    cfg = C.load_toolpaths()
    targets = C.load_json(C.TARGETS, {})
    tools = C.detect_tools(cfg)

    label = args.target or 'custom'
    if args.apk:
        apk = C.local_path(args.apk)
        if not os.path.isfile(apk):
            C.die('输入 APK 不存在: ' + args.apk)
    else:
        apk = C.resolve_apk(args.target, targets, args.yes, args.no_input)
        if not apk:
            C.die('未找到 %s 输入 APK：请在 tools/targets.json 中配置路径，'
                  '或把 APK 放到 ../resources/ 后重试' % args.target)

    work = args.work or os.path.join(C.BUILD_DIR, 'work_' + label)
    out = args.out or os.path.join(C.DIST_DIR, 'nier-mod-menu-%s%s.apk' % (
        label, ('-' + args.tag) if args.tag else ''))

    C.log('输入 APK: %s (%.1f MB)' % (apk, os.path.getsize(apk) / 1024 / 1024))
    C.log('输出 APK: %s' % out)

    C.log('=== 1/4 解包目标 APK ===')
    ensure_work(apk, work, tools, args.fresh, args.yes, args.no_input)
    C.log('=== 2/4 注入菜单（smali / so / 清单 / 启动）===')
    inject_smali(work)
    inject_manifest(work)
    inject_start_call(work)
    C.log('=== 3/4 重建 + 对齐 + 签名 ===')
    build_and_sign(tools, work, out)
    C.log('=== 4/4 结果 ===')
    size = os.path.getsize(out)
    C.log('成品: %s (%.1f MB)' % (out, size / 1024 / 1024))
    C.log('SHA256: ' + C.sha256_file(out))


if __name__ == '__main__':
    main()
