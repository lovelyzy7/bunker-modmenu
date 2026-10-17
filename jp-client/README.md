# NieR Reincarnation · 内置 Mod 菜单 — **JP 客户端**

日服 `com.square_enix.android_googleplay.nierspjp` 3.7.1 的完整 Mod 菜单工程。

> 本目录只服务 JP。EN 客户端见 [`../en-client/`](../en-client/)。
> **JP 与 EN 的 libil2cpp.so 构建不同**（RVA 完全不同），本目录的源码/偏移/产物
> **禁止**与 EN 混用；JP 的每个 RVA 都是按 JP 3.7.1 dump 单独核对过的。

---

## 目录结构

| 目录 | 内容 |
|------|------|
| `modmenu/` | 菜单工程源码（LGL 4.0 改造版，**JP 专用偏移**，与 EN 功能一致但地址独立） |
| `tools/` | 构建/注入工具（本目录独立副本） |
| `docs/` | `JPRVA记录.md`（JP↔EN 对照表）、JP 私服搭建记录 / 更新方案 |
| `resources/` | 输入 APK（JP 原版 / 私服补丁版，**不入库**） |
| `dist/` | 构建产物（**不入库**） |

## 功能一览（与 EN 对齐）

| # | 功能 | 控件 | 范围/默认 | JP 挂钩点（RVA） |
|---|------|------|-----------|------------------|
| 1 | 伤害倍率 | 滑块 | 1~333，默认 333 | `0x3A795AC` AttackDamage setter |
| 2 | 防御倍率 | 滑块 | 1~333，默认 333 | `0x3DB3158` HP setter（**讨伐战内自动跳过**） |
| 3 | 角色技能无CD | 开关 | 默认开 | `0x3A7EB3C` CurrentCooltime setter |
| 4 | God模式免伤 | 开关 | 默认开 | `0x3DB3158` HP setter（**讨伐战内自动跳过**） |
| 5 | 强制命中 | 开关 | 默认开 | `0x3A79638` / `0x3A796CC` IsEvaded、`0x2CE4A10` IsSkillHit |
| 6 | 讨伐战上限解除 | 开关 | 默认开 | 静态补丁 `0x32BCFF0` 45,000,000 → 2,147,483,647 |
| 7 | 服务器热切换 | 输入框/按钮/下拉 | 地址簿多条，支持 IP/域名、失败自动切换、记住选择 | connect() 改写 8003/8080/80 目标 |

辅助函数：`0x3DAB36C` JoinParty、`0x3A7E5E8` FromActor、`0x3A79998` TargetActor、
`0x3A7E988` MaxCooltime、`0x3DB302C` HP getter、`0x360C730` `IsInBigHunt()`。

> 讨伐战（BigHunt）内 God/防御自动停用：修改我方 HP 会导致波次结束时角色不播「消失动画」而卡死（EN 上已实测定位，JP 同步实现）。

完整 JP↔EN 对照（71 条）见 [`docs/JPRVA记录.md`](docs/JPRVA记录.md)。
注意：自动生成的对照表在 **getter/setter 同名方法**处会重复取到同一个 RVA，
本工程的 Main.cpp 已按「方法签名」逐条核对（见 `docs/JPRVA记录.md` 说明）。

## 快速开始

```bat
:: Windows
build_patched.bat

:: WSL / Git Bash
bash build_patched.sh
```

流程：编译菜单（Gradle + NDK）→ 提取 smali/`libniermenu.so` → 解包 JP 私服 APK（带缓存）
→ 注入 → 打包 → zipalign → 签名，成品在 `dist/`。

- 输入 APK：`tools/targets.json`（默认 `resources/patched-jp.apk`）
- 签名钥匙库：`tools/toolpaths.json`（本地文件，不入库；模板 `tools/toolpaths.example.json`）

## 注意

- 手动构建示例：
  ```bat
  python tools\build_all.py --target patched --yes ^
    --apk resources\patched-jp.apk ^
    --out dist\nier-mod-menu-jp-patched.apk
  ```
- 若手机已装的 JP 客户端用**其他钥匙库**签名，则需先卸载（或 `pm uninstall -k` 保留数据）才能安装本工程的产物。

## 编码 / 乱码说明

- `build_*.bat` 内置 `chcp 65001` + `set PYTHONUTF8=1`；`tools/_common.py` 在 Windows 上也会自动切控制台为 UTF-8
  → 控制台、`build/logs/*.log`、重定向输出**统一 UTF-8**，中文不会乱码。
- 仓库文本文件统一 UTF-8（无 BOM）；`.bat` 为 CRLF，其余为 LF。

---

## 服务器热切换（IP / 域名）

菜单内 `服务器热切换` 分类：输入 `IP` 或 `域名[:端口]` → `保存到地址簿` → 下拉选择 → `应用选中地址`。

- 只改写 **8003（API）/ 8080（CDN）/ 80** 端口的连接目标（443 等不受影响）
- 支持域名（菜单自行 DNS 解析，缓存 60s）；`example.com:80` 表示 API/CDN 都走 80
- `失败自动切换`（失败 2 次换下一条）、`记住上次选择`（重启自动应用）、`停止热切换`
- 生效时机：**回标题重新登录 / 重启游戏**（旧连接不会自动断开）
- 地址簿：`/data/data/com.square_enix.android_googleplay.nierspjp/files/modmenu_servers.txt`
- **auth/引継ぎ（3000）不在范围内**（JP 是打包期 smali 补丁 + WebView 流程）

---

## 签名（JP 统一）

JP 客户端产物**统一使用 lunar-scripts-jp 的密钥**（与已安装的 JP 私服客户端一致，可直接覆盖安装）：

| 项 | 值 |
|---|---|
| 钥匙库 | `E:/NieRReincarnation/lunar-scripts-jp/keys/nier-jp.keystore`（JKS） |
| alias | `nier` |
| 密码 | `lunar-jp` |
| 证书 SHA-256 | `eec23be0cb205c401791be3d4b82e8851560f5c2aed3ec644166093d3d98a2fe`（CN=lunar-scripts-jp） |

- `tools/toolpaths.json` 已指向该钥匙库 → `build.bat` 构建出的 APK 自动用它签名
- 手工重签：`apksigner sign --ks <ks> --ks-pass pass:lunar-jp --ks-key-alias nier --out out.apk in.apk`
- EN 客户端**不用**这把 key（EN 仍用系统 debug 钥匙库），两边互不影响

---

## 菜单自检（P0/P1 修复后新增）

菜单底部两行：`自检基址: linker`（libil2cpp 基址来源）、`自检挂钩: 6/6 上限ON`。
`6/6` 表示 6 个功能挂钩全部就位；看门狗每 2 秒复查，丢失会自动重装。另有「刷新自检」按钮。

> 背景：Android 10+ 上 libil2cpp.so 会映射两份（`r--` 数据视图 / `r-x` 代码视图），
> 取错那份会导致 6 个战斗功能**全部静默失效**（而在非 root 机上尤其容易触发）。
> 现基址改用 `dl_iterate_phdr()`（linker 权威地址），已验证 Android 15 非 root 设备 6/6 正常。

---

## auth 地址动态化（引継ぎ/登录页，2026-10-13）

JP 客户端打私服补丁时会注入 `com/niersp/AuthHost`，**运行时读取**引継ぎ/登录页的地址：

```
/data/data/com.square_enix.android_googleplay.nierspjp/files/auth_host.txt   # 单行 host[:port]
   ↓ 不存在 / 空 / 非法 / 异常 → 回退到打包期 --auth-host 写入的默认值
http://<值>/ntv/{gameId}/reg|update/top?...
```

菜单这边已联动：

| 菜单动作 | 对 `auth_host.txt` |
|---|---|
| 应用选中地址 / 应用输入框地址（临时）/ 启动自动应用 | **写入** `<host>:3000` |
| 停止热切换 / 地址簿清空 | **删除**（回退默认） |

→ 因此菜单切服务器后：**API(8003) / CDN(8080) 走 connect 层改写，auth(3000) 走本文件**，三者一起切。
（WebView 在哪个进程都不影响 ✓）

> 注意：auth 端口固定取 3000（打包期 `--auth-host` 的口径）；地址条目里带的端口只用于 API/CDN。
