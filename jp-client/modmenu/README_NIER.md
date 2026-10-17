# modmenu — NieR Reincarnation 专用菜单工程（LGL 4.0 改造）

本工程是从 `template/Android-Mod-Menu-cn-4.0.zip`（中文注释版）改造而来的
**本游戏专用版**，已内置全部功能钩子与偏移。

> **开发指南**：见 [`开发指南.md`](开发指南.md)（逐文件讲解 + 新增功能教程 + 调试 FAQ）。

## 已实现功能（Main.cpp）

| 功能 | 实现点（RVA） | 说明 |
|------|---------------|------|
| 伤害倍率 | `AttackDamage` setter `0x3B0C980` | 幂等缩放（防管线回读级联），上限 21 亿 |
| 防御倍率 | 同上（按目标阵营判定） | 我方受击 ÷ 倍率 |
| 角色技能无CD | `DynamicCurrentCooltime` setter `0x3B11F10` | 充能强制为 max |

完整偏移表与原理：`docs/MOD制作记录.md`【4. 偏移表】/【3. 战斗系统机制】

## 与原模板的差异

- `jni/Main.cpp`：改为本游戏的功能列表与钩子（中文注释）
- `jni/Menu/Setup.cpp`：菜单标题/副标题
- `jni/Android.mk` + `Main.java`：库名 `niermenu`
- `jni/Application.mk`、`app/build.gradle`：仅 arm64-v8a
- `jni/KittyMemory/.../libs-android/`：只保留 arm64 版 Keystone（减小体积）
- `Menu.java`：滑块默认显示最大值

## 构建

```bash
./gradlew assembleDebug        # 产物: app/build/outputs/apk/debug/app-debug.apk
```

然后按仓库根目录 `README.md` 的步骤注入目标 APK。
