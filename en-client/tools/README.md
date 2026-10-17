# tools — 构建 / 注入工具

> 日常使用请直接跑仓库根目录的两个一键脚本：
> `build.bat`（Windows）/ `build.sh`（WSL）—— 自动识别私服补丁版 APK，只负责编辑与导出，不做安装。
> 详细说明见 [`docs/一键构建说明.md`](../docs/一键构建说明.md)。

| 文件 | 用途 |
|------|------|
| `build_all.py` | **一键总流程**：编译菜单 → 解包目标 APK → 注入 → 打包 → 签名（入口脚本调用它） |
| `build_menu.py` | 编译菜单 APK（Gradle+NDK）并解包提取 smali / libniermenu.so |
| `inject_modmenu.py` | 注入引擎：解包缓存、注入 smali/so/清单/启动、重建、对齐、签名、校验、可选安装 |
| `patch_auth_dynamic_en.py` | auth 地址动态化：注入 `com/niersp/AuthHost.smali` + 把 Facebook smali 里的静态地址换成运行时读取（`build_all.py --auth-dynamic` 调用；见 [`EN-auth动态化说明.md`](../docs/EN-auth动态化说明.md)） |
| `_common.py` | 公共模块：配置读取、工具自动探测、输入 APK 定位、交互问答、日志 |
| `cn_localize.py` | 把菜单模板注释批量本地化为中文（幂等） |
| `toolpaths.example.json` | 工具路径模板：复制为 `toolpaths.json`（本地文件，不入库）按需填写；留空 = 自动探测 |
| `targets.json` | 输入 APK 路径配置（找不到会在 `../resources/` 自动扫描） |
| 研究脚本（存档） | 已统一放在`archive/scripts/`（开发阶段用，正常构建不需要；见 [`scripts/README.md`](../archive/scripts/README.md)） |

## 单独运行（调试用）

```bash
# 只编译菜单并提取 smali/so
python3 tools/build_menu.py --yes

# 只注入（复用解包缓存，跳过编译）
python3 tools/inject_modmenu.py --target original --yes --no-input

# 一键总流程
python3 tools/build_all.py --target patched --tag v1.0.2 --yes

# auth 地址动态化（引継ぎ/登录页热切换）
python3 tools/build_all.py --auto --yes --auth-dynamic --auth-host 192.168.2.6:3000
python3 tools/patch_auth_dynamic_en.py build/work_patched --auth-host 192.168.2.6:3000  # 单独跑
```

- `--yes` 所有提问取默认值；`--no-input` 非交互
- `--no-build` 跳过编译；`--menu-apk xxx.apk` 直接指定菜单 APK
- `--fresh` 强制重新解包目标 APK；`--install` 构建后安装到手机
- `--auth-dynamic` auth 地址动态化；`--auth-host host[:port]` 指定默认值（只写它也会自动开启动态化）
- 每次运行都会在 `build/logs/` 写日志；成品输出到 `dist/`
