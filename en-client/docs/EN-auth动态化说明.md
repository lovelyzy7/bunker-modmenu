# EN 客户端 auth 地址动态化（引継ぎ / 登录页）

> 一句话：把「引継ぎ/登录页」的私服 auth 地址从**编译期写死**改成**运行时可改**，
> 由菜单的「服务器热切换」在切 API/CDN 的同时把它一起切掉。

---

## 背景

EN 客户端的引継ぎ / 账号登录走 Facebook SDK 的 OAuth 流程。lunar-scripts 打私服补丁时
（`android/patch_apk.py` 的 `patch_facebook_smali()`），把 `smali*/com/facebook/**` 里的
**字面量常量**替换成了私服 auth 地址：

| 原字面量 | 打补丁后 |
|---|---|
| `"facebook.com"`（`FacebookSdk.facebookDomain`） | `"192.168.2.6:3000"` |
| `"www.facebook.com"` / `"graph.facebook.com"` | `"192.168.2.6:3000"` |
| `"m.%s"` / `"https://graph.%s"` 格式串 | `"%s"` / `"http://%s"`（scheme 由格式串提供） |

于是 auth 地址是**打包期固定**的 —— 换服务器就要重新打补丁、重装 APK。

而 auth 走 WebView，其网络可能不在游戏主进程，菜单的 `connect()` 改写覆盖不到它
（详见 `MOD制作记录.md`【服务器热切换】）。

## 方案：注入 `com/niersp/AuthHost` + 运行时读文件

```
/data/user/<userId>/com.square_enix.android_googleplay.nierspww/files/auth_host.txt
   单行 host[:port]，例：192.168.2.6:3000（写 http:// 前缀会被剥掉）
   userId = Process.myUid()/100000（单用户=0，即传统的 /data/data 路径；双开/多用户也能定位）
   ↓ 不存在 / 空 / 非法 / 读取异常
   回退打包期写入的默认值（= 打补丁时的 --auth-host）
```

`tools/patch_auth_dynamic_en.py` 对**已打完私服补丁的解包目录**做两件事：

1. 注入 `smali/com/niersp/AuthHost.smali`（`AuthHost.get()` 读上面那个文件，读不到回退默认值）
2. 把 `smali*/com/facebook/**` 里 `const-string vX, "<auth-host>"` 的**使用点**换成：

   ```smali
   invoke-static {}, Lcom/niersp/AuthHost;->get()Ljava/lang/String;
   move-result-object vX
   ```

**语义：动态化是「覆写」而不是「替代」** —— 不写文件时行为与打补丁前完全一致。

### ⚠ 与 JP 的关键差异（务必看，改错会拼出 `http://http://…`）

| | 被替换的字面量 | `AuthHost.get()` 返回 |
|---|---|---|
| **EN** | 裸 `host:port`（如 `"192.168.2.6:3000"`） | **裸 `host:port`**（scheme 由 `"http://%s"` 格式串提供） |
| JP | 完整 URL（如 `"http://psg.sqex-bridge.jp"`） | 带 `http://` 的完整地址（lunar-scripts-jp 注入） |

EN 的使用点有三类，全都期望裸值：

- `FacebookSdk.<clinit>` → `facebookDomain = <值>`，随后被 `GRAPH_URL_FORMAT = "http://%s"` 拼成完整 URL
- `DIALOG_AUTHORITY_FORMAT = "%s"` → 用作 URI **authority**（`host:port`）
- `Utility.clearCookiesForDomain()` / 域名比较（`areEqual`）→ 纯域名字符串

### ③ 让 `FacebookSdk.getFacebookDomain()` 每次读取（2026-10-16 修复）

只在 `FacebookSdk.<clinit>` 里赋值会让 SDK 把地址缓存到**进程结束**：菜单热切换写
`auth_host.txt` 后，Facebook 登录页 / Graph 仍走**旧地址**（token 由旧服务器签发），
而游戏 API/CDN 已被 `connect()` 钩子切到新服务器 → **第二次「Transfer Data」失败**
（登录页能打开、账密也对，但不会出现 Transfer complete）。

`patch_usage_sites()` 之后追加 `patch_facebook_domain_live()`：把
`FacebookSdk.getFacebookDomain()` 里的 `sget-object …->facebookDomain` 换成
`AuthHost.get()`，于是所有调用方（`getGraphApiVersion` 等）每次读取都是当前值。

真机验证（OPPO PKR110 / Android 15）：进程运行中把 `auth_host.txt` 从 VPS 改成
`192.168.2.6:3000`，点「Sign in with Facebook」后新连接全部指向 `192.168.2.6:3000` ✓
（旧连接仍留在 VPS = 原 bug 的残留，重启进程即消失）。

### ④ 放开 FB SDK 的 different-user 保护（2026-10-16 修复）

切服务器 / 换账号再登录时，FB SDK 会拿新 token 的 `userId` 与已缓存 token 对比，
不同则直接报错 **`User logged in as different Facebook user.`**（**不返回 token**）→
引继拿不到 token → 不弹 Transfer complete。真机日志：

```
sending to Unity OnLoginComplete({"callback_id":"3", "error":"User logged in as different Facebook user."})
```

`patch_fb_allow_user_switch()` 把 `LoginClient.completeLogin()` 里 `:cond_0` 分支的
`createErrorResult("User logged in as different Facebook user.")` 换成与成功分支相同的
`createCompositeTokenResult(pendingRequest, result.token, result.authenticationToken)`
→ 换账号/换服务器直接登录成功（旧 token 被新 token 覆盖，正是热切换所需）。
顺带修好「全新设备首次登录（无 current token）」也会走该错误分支的情况。

## 用法

### A. 一键构建（推荐）

```bat
build.bat --auth-dynamic --auth-host 192.168.2.6:3000
```

（不填 `--auth-host` 会从 smali 自动探测；探测不到会报错要求显式指定。
`--auth-host` 只写不加 `--auth-dynamic` 也会自动开启动态化。）

### B. 单独跑脚本（调试用）

```bash
python3 tools/patch_auth_dynamic_en.py build/work_patched --auth-host 192.168.2.6:3000
python3 tools/patch_auth_dynamic_en.py build/work_patched            # 自动探测
python3 tools/patch_auth_dynamic_en.py build/work_patched --no-auth-dynamic   # 只注入类，不改使用点
```

### 推荐流程

```
lunar-scripts 打私服补丁 → 本脚本 →（注入菜单）→ apktool b + 签名
```

## 幂等 / 可重复执行

| 操作 | 重复执行时 |
|---|---|
| 注入 `AuthHost.smali` | 内容一致则跳过；`--auth-host` 变了会重写默认值 |
| 替换使用点 | 文件内带 `authhost-dynamic` 标记即整体跳过（不会叠加） |

替换范围**只有** `smali*/com/facebook/**`（与 lunar-scripts 的作用域一致），不会误伤
ExoPlayer / 广告 SDK 等含「尾段像端口」字面量（如 `urn:scte:dash:cc:cea-608:2015`）的文件。

## 与菜单「服务器热切换」的联动

| 菜单动作 | 对 `auth_host.txt` |
|---|---|
| 应用选中地址 / 应用输入框地址(临时) / 启动自动应用 | **写入** `<host>:3000` |
| 停止热切换 / 地址簿清空 | **删除**（回退打包默认值） |

→ 切服务器时：**API(8003) / CDN(8080) 走 connect 层改写，auth(3000) 走本文件**，三者一起切。
（WebView 在哪个进程都不影响 ✓）

> 注意：auth 端口固定取 **3000**（与打包期 `--auth-host` 的口径一致）；地址簿条目里带的端口只用于 API/CDN。

## 排障

| 现象 | 排查 |
|---|---|
| 切了服务器但登录页还是旧地址 | 看 `files/auth_host.txt` 是否被写入（owner 应为 app uid）；重启客户端再试 |
| 想回退打包默认值 | 删掉 `files/auth_host.txt`，或菜单里点「停止热切换」 |
| 自动探测报「未能确定 auth 地址」 | 显式 `--auth-host`；或先确认解包目录里 smali/com/facebook 是否存在 |
| 打包后 `smali` 编译报错 | 多半是把 JP 的带 `http://` 版 AuthHost 抄到了 EN；用本脚本重新生成 |

## 真机验证记录（2026-10-14，Redmi 2308CPXD0C / Android 16 / root）

| 验证项 | 方法 | 结果 |
|---|---|---|
| `AuthHost.get()` 读文件 | 用 `dalvikvm` 直接加载 APK 的 `classes.dex` 调用（同进程用 Java 读同一文件做对照） | 文件 `127.0.0.1:3000` → 返回该值；`http://…` 前缀被剥掉；文件缺失/为空 → 回退默认 ✓ |
| 菜单写入 | `logcat -s Mod_Menu` 看菜单「应用选中地址/启动自动应用」 | `srv: auth_host.txt -> <host>:3000` ✓ |
| 客户端实际使用 | 菜单写入 `127.0.0.1:3000` + `adb reverse tcp:3000` 转到 PC 上的回显服务 | FB SDK 启动请求 `Host=127.0.0.1:3000`；引継ぎ WebView 显示回显页 ✓ |
| 回退默认 | 删除 `auth_host.txt` 后冷启动 | FB SDK 请求回到烧录默认 `192.168.2.6:3000` ✓ |

> ⚠ 行为说明：FB SDK 在**进程启动时**读一次 `facebookDomain`（缓存在静态字段），
> 改地址后必须**重启客户端**才生效（菜单「应用 / 停止」后按提示重登即可）。

> ⚠ 改模板务必注意（踩过的坑）：判空分支要用 `if-eqz`。
> smali 的 `if-nez` / `if-gtz` 是「**非 0 / 大于 0 就跳转**」——若写反成
> `if-gtz v3, :use_default`，则「文件非空」会直接落到默认值，表现为**文件永远不生效**
> （JP 模板 `lunar-scripts-jp` 目前也有同样问题，需要同步修正）。

## 相关文件

| 文件 | 说明 |
|---|---|
| `tools/patch_auth_dynamic_en.py` | 本功能的注入脚本（`build_all.py --auth-dynamic` 会调它） |
| `modmenu/app/src/main/jni/Main.cpp` | `srvSyncAuthLocked()`：写/删 `auth_host.txt` |
| [`MOD制作记录.md`](MOD制作记录.md) | 服务器热切换原理、根因记录 |
| [`操作指南.md`](操作指南.md) | 给玩家的使用步骤 |
