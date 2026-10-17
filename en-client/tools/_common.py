#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_common.py — 一键构建脚本公共模块

提供：配置读取、工具自动探测、输入 APK 定位、交互问答、日志、路径转换。
被 build_menu.py / inject_modmenu.py / build_all.py 复用。
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(ROOT, 'build')
LOG_DIR = os.path.join(BUILD_DIR, 'logs')
TMP_DIR = os.path.join(BUILD_DIR, 'tmp')
DIST_DIR = os.path.join(ROOT, 'dist')
MODMENU = os.path.join(ROOT, 'modmenu')
MENU_APK = os.path.join(MODMENU, 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk')
MENU_APKTOOL = os.path.join(BUILD_DIR, 'menu_apktool')
TOOLPATHS = os.path.join(ROOT, 'tools', 'toolpaths.json')
TOOLPATHS_EXAMPLE = os.path.join(ROOT, 'tools', 'toolpaths.example.json')
TARGETS = os.path.join(ROOT, 'tools', 'targets.json')

APP_PACKAGE = 'com.square_enix.android_googleplay.nierspww'

_LOG_FILE = None


def is_wsl():
    try:
        with open('/proc/version') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False


IS_WSL = is_wsl()


def log(msg):
    line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    if _LOG_FILE:
        try:
            _LOG_FILE.write(line + '\n')
            _LOG_FILE.flush()
        except Exception:
            pass



def _init_console_utf8():
    """Windows: 控制台切 UTF-8(65001)，并把 stdout/stderr 固定为 UTF-8，
    保证 控制台 / 日志文件 / 管道重定向 三处编码一致（避免中文乱码）。"""
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


_init_console_utf8()

def die(msg):
    log('[错误] ' + msg)
    sys.exit(1)


def init_log(tag):
    global _LOG_FILE
    os.makedirs(LOG_DIR, exist_ok=True)
    name = time.strftime('%Y%m%d-%H%M%S') + '-' + re.sub(r'[^\w\-]+', '_', tag) + '.log'
    _LOG_FILE = open(os.path.join(LOG_DIR, name), 'w', encoding='utf-8')
    log('日志: build/logs/' + name)


def run(cmd, cwd=None, env=None):
    log('$ ' + ' '.join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=cwd, env=env)
    if r.returncode != 0:
        die('命令失败(exit %d): %s' % (r.returncode, ' '.join(str(c) for c in cmd)))


def win_path(p):
    """当前系统路径 → Windows 路径（WSL 下用 wslpath；Windows 下直接绝对路径）"""
    p = os.path.abspath(p)
    if IS_WSL:
        try:
            return subprocess.check_output(['wslpath', '-w', p], text=True).strip()
        except Exception:
            return p
    return p


def local_path(p):
    """Windows 绝对路径 → 当前系统路径（WSL: C:\\x → /mnt/c/x）"""
    if not p:
        return p
    if IS_WSL and re.match(r'^[A-Za-z]:[\\/]', p):
        return '/mnt/' + p[0].lower() + p[2:].replace('\\', '/')
    return p


def to_windows_style(p):
    """路径 → Windows 风格（WSL 的 /mnt/c/... 转为 C:\\...），供 gradle 批处理使用"""
    if not p:
        return p
    if IS_WSL and p.startswith('/mnt/') and len(p) > 6:
        return p[5].upper() + ':' + '\\' + p[6:].replace('/', '\\')
    return p


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        if default is not None:
            log('读取 %s 失败，使用默认值: %s' % (path, e))
            return default
        die('读取配置失败: %s (%s)' % (path, e))


def load_toolpaths():
    """读取本地 toolpaths.json；不存在时用 example（自动探测模式）"""
    if os.path.isfile(TOOLPATHS):
        return load_json(TOOLPATHS, {})
    if os.path.isfile(TOOLPATHS_EXAMPLE):
        log('未找到 tools/toolpaths.json，使用 toolpaths.example.json（自动探测模式）')
        return load_json(TOOLPATHS_EXAMPLE, {})
    return {}


# --------------------------------------------------------------------------
#  自动识别输入 APK（--auto / 未指定 --target 时使用）
# --------------------------------------------------------------------------
_EXCLUDE_APK = ('mod-menu', 'modmenu', 'mod_menu', 'gamedva', 'signed_modded', 'backup', 'menu-')
_OTHER_CLIENT = ('_jp', 'jp.apk', 'nierspjp')


def guess_target_kind(name):
    """按文件名猜测是「私服补丁版」还是「原版」"""
    n = name.lower()
    if 'patched' in n or 'private' in n or 'lunar' in n:
        return 'patched'
    return 'original'


def auto_detect_apk(auto_yes=False, no_input=False):
    """扫描 resources/ 等目录，返回 (apk 路径, 类型)；优先私服补丁版"""
    dirs = [os.path.join(ROOT, 'resources'), ROOT,
            os.path.join(ROOT, '..', 'resources'),
            os.path.join(ROOT, '..', '..', 'resources')]
    cands, seen = [], set()
    for d in dirs:
        d = os.path.abspath(d)
        if d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        for fn in sorted(os.listdir(d)):
            low = fn.lower()
            if not low.endswith('.apk'):
                continue
            if any(x in low for x in _EXCLUDE_APK):
                continue
            if any(x in low for x in _OTHER_CLIENT):   # 跳过另一个客户端的 APK
                continue
            cands.append((os.path.join(d, fn), guess_target_kind(fn)))
    if not cands:
        return None, None
    if len(cands) == 1:
        log('自动识别输入 APK: %s' % cands[0][0])
        return cands[0]
    patched = [c for c in cands if c[1] == 'patched']
    if not patched:
        log('只找到原版 APK（本项目只支持「先打私服补丁 → 再注入菜单」）：')
        for p, k in cands:
            log('    [%s] %s' % (k, p))
        log('  请先用 lunar-scripts 给原版打私服补丁，再把补丁版 APK 放进 resources/')
        return None, None
    pick = patched[0]
    log('扫描到 %d 个候选 APK，自动选择: %s' % (len(cands), os.path.basename(pick[0])))
    for p, k in cands:
        log('    [%s] %s%s' % (k, p, '   <== 使用' if p == pick[0] else ''))
    return pick


def cert_sha256(apk, tools):
    """读取 APK 的签名证书 SHA-256（用于确认每次构建签名恒定）"""
    try:
        out = subprocess.check_output(
            [tools['java'], '-jar', local_path(tools['apksigner_jar']),
             'verify', '--print-certs', apk],
            text=True, stderr=subprocess.STDOUT)
        for line in out.splitlines():
            if 'SHA-256 digest' in line:
                return line.split(':')[-1].strip()
    except Exception:
        pass
    return ''


def ask_yes_no(question, default=True, auto_yes=False, no_input=False):
    """交互确认；非交互/--yes 时直接返回 default"""
    if auto_yes or no_input or not sys.stdin.isatty():
        return default
    tip = 'Y/n' if default else 'y/N'
    while True:
        try:
            ans = input('%s [%s] ' % (question, tip)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if ans == '':
            return default
        if ans in ('y', 'yes', '是'):
            return True
        if ans in ('n', 'no', '否'):
            return False


def ask_text(question, default='', auto_yes=False, no_input=False):
    if auto_yes or no_input or not sys.stdin.isatty():
        return default
    try:
        ans = input('%s [%s] ' % (question, default)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans or default


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------
#  工具探测
# --------------------------------------------------------------------------
def _latest_build_tools(android_home):
    base = os.path.join(local_path(android_home), 'build-tools') if android_home else ''
    if not base or not os.path.isdir(base):
        return None
    def key(name):
        m = re.match(r'(\d+)(?:\.(\d+))?(?:\.(\d+))?', name)
        return tuple(int(x or 0) for x in (m.groups() if m else ('0', '0', '0')))
    cands = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    for d in sorted(cands, key=key, reverse=True):
        if os.path.isfile(os.path.join(base, d, 'zipalign')) or os.path.isfile(os.path.join(base, d, 'zipalign.exe')):
            return os.path.join(base, d)
    return None


def _detect_android_home(cfg):
    """Android SDK 位置：配置 → 环境变量 → 常见安装目录"""
    for c in (cfg.get('android_home'), os.environ.get('ANDROID_HOME'), os.environ.get('ANDROID_SDK_ROOT')):
        if c and os.path.isdir(local_path(c)):
            return c
    import glob as _glob
    home = os.path.expanduser('~')
    cands = [os.path.join(home, 'AppData', 'Local', 'Android', 'Sdk'),
             os.path.join(home, 'Android', 'Sdk')]
    if IS_WSL:
        cands += _glob.glob('/mnt/c/Users/*/AppData/Local/Android/Sdk')
    if os.name == 'nt':
        cands += _glob.glob(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk'))
    for c in cands:
        if c and os.path.isdir(local_path(c)):
            return c
    return ''


def detect_tools(cfg=None):
    cfg = cfg or {}
    tools = {}

    # java
    tools['java'] = cfg.get('java') or 'java'

    # apktool.jar
    apktool = cfg.get('apktool_jar') or os.environ.get('APKTOOL_JAR') or ''
    if not apktool or not os.path.isfile(local_path(apktool)):
        for c in (os.path.join(ROOT, 'tools', 'apktool.jar'),):
            if os.path.isfile(local_path(c)):
                apktool = c
                break
    if not apktool or not os.path.isfile(local_path(apktool)):
        die('未找到 apktool.jar：请把 apktool.jar 放到 tools/ 下，'
            '或在 tools/toolpaths.json（模板 tools/toolpaths.example.json）配置 apktool_jar')
    tools['apktool_jar'] = apktool

    # android sdk（配置 → 环境变量 → 常见安装位置）
    android_home = _detect_android_home(cfg)
    tools['android_home'] = android_home
    tools['java_home'] = cfg.get('java_home') or os.environ.get('JAVA_HOME') or ''
    tools['gradle_user_home'] = cfg.get('gradle_user_home') or ''

    bt = _latest_build_tools(android_home)
    if not bt:
        die('未找到 Android build-tools（SDK: %s）。请在 tools/toolpaths.json 配置 android_home'
            % (android_home or '未检测到'))

    # zipalign（Windows exe 或 Linux 可执行）
    zipalign = cfg.get('zipalign') or ''
    if not zipalign or not os.path.isfile(local_path(zipalign)):
        for name in ('zipalign.exe', 'zipalign'):
            p = os.path.join(bt, name)
            if os.path.isfile(p):
                zipalign = p
                break
    if not zipalign or not os.path.isfile(local_path(zipalign)):
        die('未找到 zipalign（build-tools: %s）' % bt)
    tools['zipalign'] = zipalign

    # apksigner.jar
    apksigner = cfg.get('apksigner_jar') or ''
    if not apksigner or not os.path.isfile(local_path(apksigner)):
        for p in (os.path.join(bt, 'lib', 'apksigner.jar'), os.path.join(bt, 'apksigner.jar')):
            if os.path.isfile(p):
                apksigner = p
                break
    if not apksigner or not os.path.isfile(local_path(apksigner)):
        die('未找到 apksigner.jar（build-tools: %s）' % bt)
    tools['apksigner_jar'] = apksigner

    # keystore
    ks = cfg.get('keystore') or 'archive/keys/nier.keystore'
    ks_path = ks if os.path.isabs(ks) else os.path.join(ROOT, ks)
    ks_path = local_path(ks_path)
    if not os.path.isfile(ks_path):
        die('未找到签名密钥: ' + ks_path)
    tools['keystore'] = ks_path
    tools['ks_pass'] = cfg.get('ks_pass') or 'nier123456'
    tools['ks_alias'] = cfg.get('ks_alias') or 'nier'

    log('工具: java=%s' % tools['java'])
    log('工具: build-tools=%s' % local_path(bt))
    return tools



# --------------------------------------------------------------------------
#  输入 APK 定位
# --------------------------------------------------------------------------
_PATTERNS = {
    'original': [r'.*3\.7\.1.*EN.*\.apk$', r'.*nierspww.*\.apk$'],
    'patched': [r'.*patched.*\.apk$', r'.*patch.*\.apk$'],
}
_SKIP = re.compile(r'patched|mod|menu', re.I)


def resolve_apk(kind, targets, auto_yes=False, no_input=False):
    """定位输入 APK：配置 → 扫描 → 交互选择；返回路径或 None"""
    p = targets.get(kind)
    if p:
        cand = p if os.path.isabs(p) else os.path.join(ROOT, p)
        cand = local_path(cand)
        if os.path.isfile(cand):
            return cand
        log('配置的 %s APK 不存在: %s' % (kind, cand))
    dirs = targets.get('search_dirs') or ['../resources', '.']
    found = []
    for d in dirs:
        dd = d if os.path.isabs(d) else os.path.join(ROOT, d)
        dd = local_path(dd)
        if not os.path.isdir(dd):
            continue
        for fn in sorted(os.listdir(dd)):
            if not fn.lower().endswith('.apk'):
                continue
            if kind == 'original' and _SKIP.search(fn):
                continue
            for pat in _PATTERNS.get(kind, []):
                if re.match(pat, fn, re.I):
                    found.append(os.path.join(dd, fn))
                    break
    # 去重
    seen, uniq = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    if not uniq:
        return None
    if len(uniq) == 1:
        log('自动找到 %s APK: %s' % (kind, uniq[0]))
        return uniq[0]
    log('找到多个 %s APK:' % kind)
    for i, f in enumerate(uniq):
        log('  [%d] %s' % (i + 1, f))
    if auto_yes or no_input or not sys.stdin.isatty():
        return uniq[0]
    ans = ask_text('请选择序号', '1', auto_yes, no_input)
    try:
        idx = int(ans) - 1
        return uniq[idx] if 0 <= idx < len(uniq) else uniq[0]
    except Exception:
        return uniq[0]
