# NieR Reincarnation · 内置 Mod 菜单 — **EN 客户端**

国际服（west）`com.square_enix.android_googleplay.nierspww` 3.7.1 的完整 Mod 菜单工程。

> 本目录只服务 EN。JP 客户端见 [`../jp-client/`](../jp-client/)。
> **禁止**把本目录的 libil2cpp 偏移/产物用于 JP（两个构建的 RVA 完全不同）。

---

## 目录结构

| 目录 | 内容 |
|------|------|
| `modmenu/` | 菜单工程源码（LGL 4.0 改造版，EN 专用偏移）；开发指南见 `modmenu/开发指南.md` |
| `tools/` | 构建/注入/本地化工具（Python） |
| `docs/` | EN 全部文档（技术档案 / 操作指南 / 流程 / 美化 / 上传说明） |
| `archive/` | 归档：`keys/`（签名密钥）、`template/`（菜单模板）、`scripts/`（Frida 研究脚本）、`config/`（运行配置示例）、`releases/`（成品说明）——顶层保持与 `jp-client/` 一致 |
| `resources/` | 输入 APK（原版 / 私服补丁版，**不入库**） |
| `dist/` | 成品 APK 输出（**不入库**，用 Release 分发） |

## 功能一览

| # | 功能 | 控件 | 范围/默认 | 实现位置 |
|---|------|------|-----------|----------|
| 1 | 伤害倍率 | 滑块 | 1~333，默认 333 | AttackDamage 字段 setter（幂等缩放） |
| 2 | 防御倍率 | 滑块 | 1~333，默认 333 | HP 写入点（**讨伐战内自动跳过**） |
| 3 | 角色技能无CD | 开关 | 默认开 | 技能充能 setter |
| 4 | God模式免伤 | 开关 | 默认开 | HP 写入点（**讨伐战内自动跳过**） |
| 5 | 强制命中 | 开关 | 默认开 | IsEvaded get/set + IsSkillHit |
| 6 | 讨伐战上限解除 | 开关 | 默认开 | 静态指令补丁 `movz/movk w2` 45,000,000 → 2,147,483,647 |
| 7 | 服务器热切换 | 输入框/按钮/下拉 | 地址簿多条，支持 IP/域名、失败自动切换、记住选择 | connect() 改写 8003/8080/80 目标 + `auth_host.txt`（auth/3000，需 `--auth-dynamic` 打包） |

> 讨伐战（BigHunt）内 God/防御自动停用：实测修改我方 HP 会导致波次结束时角色不播「消失动画」，波次切换永久等待 → 卡死。
> 判定用 `KernelTurnBattleBigHunt.IsInBigHunt()`。

## 快速开始

### A. 只想要成品 APK
见 [`archive/releases/README.md`](archive/releases/README.md)。APK 体积大（>250MB），请用 GitHub **Releases（附件）** 下载或自行构建。

### B. 一键构建（推荐）

```bat
build.bat                 :: 自动识别 resources\ 里的 APK（优先私服补丁版）
```
（WSL / Git Bash 用 `bash build.sh`）
脚本会打印成品路径 + SHA256 + **签名证书 SHA-256**（应与 `keys/README.md` 记录的一致）。

#### 说明


| 目标 | Windows | WSL / Git Bash |
|------|---------|----------------|
| 私服补丁版 + 菜单 | 双击 `build_patched.bat` | `bash build_patched.sh` |

脚本自动完成：编译菜单 → 提取 smali/so → 解包目标 APK（带缓存）→ 注入 → 打包 → 对齐 → 签名，成品在 `dist/`。
输入 APK 在 `tools/targets.json` 配置。交互问答直接回车即最佳路径；无人值守加 `--yes`。

签名：默认使用本机 debug 钥匙库（与已安装的私服客户端一致，可直接覆盖安装），
配置见 `tools/toolpaths.json`（模板：`tools/toolpaths.example.json`）。

### C. 从模板学起
解压 `template/Android-Mod-Menu-cn-4.0.zip`，阅读其中的 `README_CN.md`。

---

## auth 地址动态化（引継ぎ/登录页，2026-10-13）

打包时加 `--auth-dynamic`（推荐同时给 `--auth-host`）：

```bat
build.bat --auth-dynamic --auth-host 192.168.2.6:3000
```

会在 APK 里注入 `com/niersp/AuthHost`，运行时读取引継ぎ/登录页地址：

```
/data/data/com.square_enix.android_googleplay.nierspww/files/auth_host.txt   # 单行 host[:port]
   ↓ 不存在 / 空 / 非法 / 异常 → 回退到打包期 --auth-host 写入的默认值
```

菜单这边已联动：应用地址 → **写入** `<host>:3000`；停止热切换 / 地址簿清空 → **删除**。
→ 切服务器时 **API(8003) / CDN(8080) 走 connect 改写、auth(3000) 走本文件**，三者一起切。

> ⚠ EN 的 `AuthHost.get()` 返回**裸 host:port**（与 JP 不同）；详见 [`docs/EN-auth动态化说明.md`](docs/EN-auth动态化说明.md)。

## 文档导航

- [`docs/MOD制作记录.md`](docs/MOD制作记录.md) — **完整技术档案**（偏移表、原理、踩坑、排查记录）
- [`docs/操作指南.md`](docs/操作指南.md) — 安装与使用指南（给玩家）
- [`docs/制作流程标准化.md`](docs/制作流程标准化.md) — 构建/注入标准流程（给开发者）
- [`docs/EN-auth动态化说明.md`](docs/EN-auth动态化说明.md) — auth 地址动态化（引継ぎ/登录页热切换）
- [`modmenu/开发指南.md`](modmenu/开发指南.md) — **菜单工程开发指南**（逐文件讲解、新增功能教程、调试 FAQ）
- [`docs/美化指南.md`](docs/美化指南.md) — 菜单 UI 美化
- [`docs/上传GitHub说明.md`](docs/上传GitHub说明.md) — 仓库推送步骤

## 版本与偏移

- 目标客户端：nierspww **3.7.1**
- 偏移表见 `docs/MOD制作记录.md`【4. 偏移表】
- 换版本后需重新 dump 并更新 `modmenu/app/src/main/jni/Main.cpp` 的 RVA
