# bunker-modmenu

Bunker 的 **Mod 菜单**工程:注入到已打私服补丁的 `NieR Re[in]carnation` 3.7.1 APK 里的
内存菜单。日服与全球服各一份,**源码、RVA 偏移与构建产物严格独立**。

本仓库是 [Bunker](https://github.com/lovelyzy7/bunker-jp-en) 的可选依赖:
Bunker 用 `--mod-menu` 在打完客户端补丁后调用这里的注入脚本。

> 仅供学习研究 / 私服单机自用,请勿用于联网游戏作弊或商业用途。

## 与原工程的差异

本仓库来自 `NieR-Re-In-Carnation-Mod_Menu` 的 `en-client` / `jp-client`,并做了裁剪:

| 移除 | 保留 |
| --- | --- |
| **服务器热切换**:地址簿文件、`connect()` 钩子改写目标 IP、失败自动切换、"记住上次选择"、`auth_host.txt` 写入、菜单项 7–16 与对应 `Changes()` 分支 | 伤害倍率、防御倍率、技能无 CD、God 免伤、强制命中、讨伐战上限解除、自检显示 |

**为什么移除**:Bunker 把游戏与服务器跑在同一台设备上,服务器地址恒为 `127.0.0.1`,
热切换只会带来"误切地址导致连不上"的故障面。移除后菜单更简单,也与打包期的端口偏移
逻辑无冲突(偏移由 Bunker 在构建时统一处理)。

讨伐战(BigHunt)内自动停用"防御倍率/God 免伤"的保护逻辑**保留**:修改我方 HP 会让波次
结束时角色不播消失动画而卡死,已实测定位。

## 目录

| 路径 | 说明 |
| --- | --- |
| `jp-client/` | 日服(`com.square_enix.android_googleplay.nierspjp`)菜单与注入脚本 |
| `en-client/` | 全球服(`com.square_enix.android_googleplay.nierspww`)菜单与注入脚本 |
| `*/modmenu/` | 菜单本体:Java UI + JNI(KittyMemory / And64InlineHook / Substrate) |
| `*/tools/` | 构建与注入:`build_all.py`(总流程)、`build_menu.py`、`inject_modmenu.py` |
| `*/docs/` | 制作记录、RVA 对照表、操作指南 |

## 构建与注入

```bat
cd jp-client
build_patched.bat          :: 私服补丁版 APK + 菜单
```

或分步:

```bash
python tools/build_all.py --apk <已打私服补丁的.apk> --out <输出.apk> --no-input --yes
python tools/build_all.py --apk <...> --out <...> --no-build --menu-apk <已有菜单.apk>
```

`tools/targets.json` 配置输入 APK,`tools/toolpaths.json` 配置 apktool/签名库
(参考 `toolpaths.example.json`,不入库)。

构建需要 JDK 17+、Android SDK(platform 34、build-tools)、NDK(ndk-build)。
已在 Gradle 8.7 / AGP 8.6.1 / JDK 21 / NDK 27 上验证 `assembleDebug` 通过。

## 验证

- `jp-client` 与 `en-client` 的 `libniermenu.so` 已确认不再包含 `服务器热切换`、`地址簿`
  字符串,同时保留 `伤害倍率`、`God模式`、`讨伐战上限解除`。
- 注入到真实 3.7.1 APK 后的整体验证见 Bunker 仓库的 `docs/VALIDATION.md`。

## 免责声明

仅用于 Android 逆向 / Mod 开发学习,以及个人私服的单机体验。
请勿用于任何联网游戏的作弊、牟利或侵犯版权行为。NieR Re[in]carnation © SQUARE ENIX。
