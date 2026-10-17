#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cn_localize.py — 把 Android-Mod-Menu 模板里主要文件的注释本地化为中文（批处理）

用法:
  python3 tools/cn_localize.py <工程根目录>
例如:
  python3 tools/cn_localize.py build/Android-Mod-Menu-cn-4.0

说明:
  - 对 Menu.java / Preferences.java / Menu.cpp 等大文件，做"行级精确替换 + 文件头中文横幅"
  - 第三方库 (KittyMemory / Substrate / And64InlineHook / Includes) 保持原样
  - 已替换过的内容不会重复替换（幂等）
"""
import os
import sys

# (相对路径, 旧的精确文本, 新文本)
REPLACEMENTS = [
    # ---------- Menu.java ----------
    ("app/src/main/java/com/android/support/Menu.java",
     "    //********** Here you can easly change the menu appearance **********//",
     "    //********** 菜单外观配置区（改这里就能美化菜单）**********//"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    //region Variable",
     "    // region 配置变量"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    public static final String TAG = \"Mod_Menu\"; //Tag for logcat",
     "    public static final String TAG = \"Mod_Menu\"; // logcat 日志标签"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    int ICON_SIZE = 45; //Change both width and height of image",
     "    int ICON_SIZE = 45; // 悬浮图标宽高（同时修改宽和高）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    float ICON_ALPHA = 0.7f; //Transparent",
     "    float ICON_ALPHA = 0.7f; // 透明度（0~1）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    int MENU_BG_COLOR = Color.parseColor(\"#EE1C2A35\"); //#AARRGGBB",
     "    int MENU_BG_COLOR = Color.parseColor(\"#EE1C2A35\"); // #AARRGGBB（前两位是透明 Alpha）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    int MENU_FEATURE_BG_COLOR = Color.parseColor(\"#DD141C22\"); //#AARRGGBB",
     "    int MENU_FEATURE_BG_COLOR = Color.parseColor(\"#DD141C22\"); // #AARRGGBB（功能项背景）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    //initialize methods from the native library",
     "    // 来自原生库的方法"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    //Here we write the code for our Menu",
     "    // ---- 菜单主体代码 ----"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    // Reference: https://www.androidhive.info/2016/11/android-floating-widget-like-facebook-chat-head/",
     "    // 参考: https://www.androidhive.info/2016/11/android-floating-widget-like-facebook-chat-head/"),
    ("app/src/main/java/com/android/support/Menu.java",
     "        //Currently looks messy right now. Let me know if you have improvements",
     "        // 功能列表解析（代码略显凌乱，可自行优化）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "            //Assign feature number",
     "            // 分配功能号"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                //Subtract feature number. We don't want to count ButtonLink, Category, RichTextView and RichWebView",
     "                // 不显式编号时自动编号；ButtonLink/Category/RichTextView/RichWebView 不计数"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                //if progress is greater than minimum, don't go below. Else, set progress",
     "                // 拖动值不能小于最小值"),
    ("app/src/main/java/com/android/support/Menu.java",
     "            seekBar.setMin(min); //setMin for Oreo and above",
     "            seekBar.setMin(min); // Android 8.0+ 才支持 setMin"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                        //The check for Xdiff <10 && YDiff< 10 because sometime elements moves a little while clicking.",
     "                        // 位移小于 10px 视为点击（拖动悬浮球时会有微小位移）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                        //So that is click event.",
     "                        // 判定为点击事件"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                            //When user clicks on the image view of the collapsed layout,",
     "                            // 点击收起状态的悬浮图标时，"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                            //visibility of the collapsed layout will be changed to \"View.GONE\"",
     "                            // 隐藏收起布局、显示展开布局"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                            //and expanded view will become visible.",
     "                            // （即展开菜单面板）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                            //Calculate the X and Y coordinates of the view.",
     "                            // 计算拖动后的 X/Y 坐标"),
    ("app/src/main/java/com/android/support/Menu.java",
     "                            //Update the layout with new X & Y coordinate",
     "                            // 按新坐标更新悬浮窗位置"),
    # ---------- Preferences.java ----------
    ("app/src/main/java/com/android/support/Preferences.java",
     "    private static final int DEFAULT_INT_VALUE = 0; //-1",
     "    private static final int DEFAULT_INT_VALUE = 0; // 默认值 0（-1 为特殊功能号）"),
    ("app/src/main/java/com/android/support/Preferences.java",
     "    private static final int DEFAULT_DOUBLE_VALUE = 0d; //-1d",
     "    private static final int DEFAULT_DOUBLE_VALUE = 0d; // 默认值 0d"),
    ("app/src/main/java/com/android/support/Preferences.java",
     "    private static final float DEFAULT_FLOAT_VALUE = 0f; //-1f",
     "    private static final float DEFAULT_FLOAT_VALUE = 0f; // 默认值 0f"),
    ("app/src/main/java/com/android/support/Preferences.java",
     "    private static final long DEFAULT_LONG_VALUE = 0L; //-1L",
     "    private static final long DEFAULT_LONG_VALUE = 0L; // 默认值 0L"),
    # ---------- Menu.cpp ----------
    ("app/src/main/jni/Menu/Menu.cpp",
     "//Big letter cause crash",
     "// 大写字幕可能闪退（原版注意事项）"),
    ("app/src/main/jni/Menu/Menu.cpp",
     "    //Use https://www.base64encode.org/ to encode your image to base64",
     "    // 用 https://www.base64encode.org/ 把图片转成 base64 后粘贴到这里"),
    ("app/src/main/jni/Menu/Menu.cpp",
     "    //WebView support GIF animation. Upload your image or GIF on imgur.com or other sites",
     "    // WebView 支持 GIF 动图：把图片/GIF 上传到图床（如 imgur）后填 URL"),
    ("app/src/main/jni/Menu/Menu.cpp",
     "    // From internet (Requires android.permission.INTERNET)",
     "    // 来自网络（需要 android.permission.INTERNET 权限）"),
    ("app/src/main/jni/Menu/Menu.cpp",
     "    // Base64 html:",
     "    // base64 HTML:"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    // From internet: (Requires android.permission.INTERNET)",
     "    // 来自网络:（需要 android.permission.INTERNET 权限）"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    // Base64 html:",
     "    // base64 HTML:"),
    ("app/src/main/java/com/android/support/Menu.java",
     "    // To disable it, return nullptr. It will use normal image above:",
     "    // 想关闭 WebView 图标就返回 nullptr（会改用上面的普通图标）:"),
    ("app/src/main/jni/Menu/Menu.cpp",
     "    // To disable it, return nullptr. It will use normal image above:",
     "    // 想关闭 WebView 图标就返回 nullptr（会改用普通图标）:"),
]

# 各文件的中文横幅（插入到文件最顶部；.java 会放在 package 之前也是合法的）
BANNERS = {
    "app/src/main/java/com/android/support/Menu.java":
        "// ============================================================================\n"
        "//  Menu.java — 悬浮菜单 UI（中文注释版）\n"
        "//  主要内容：\n"
        "//    1) 顶部「菜单外观配置区」：颜色/尺寸/位置（美化必改）\n"
        "//    2) featureList()：解析原生返回的功能列表（开关/滑块/按钮...）\n"
        "//    3) 各控件实现：Toggle / SeekBar / Button / Spinner / InputValue...\n"
        "//  注意：改完后需要重新编译菜单并重新注入（见 README_CN.md）。\n"
        "// ============================================================================\n",
    "app/src/main/java/com/android/support/Preferences.java":
        "// ============================================================================\n"
        "//  Preferences.java — 功能偏好保存/读取（中文注释版）\n"
        "//  作用：把菜单里的开关/数值保存到 SharedPreferences，重启游戏后恢复；\n"
        "//        并通过 native Changes() 把状态同步给 C++ 层。\n"
        "//  说明：负数功能号是菜单内置设置项（-1 保存偏好 / -3 自动高度 等）。\n"
        "// ============================================================================\n",
    "app/src/main/jni/Menu/Menu.cpp":
        "// ============================================================================\n"
        "//  Menu.cpp — 菜单核心实现（中文注释版）\n"
        "//    1) setText()      设置文本（支持 HTML）\n"
        "//    2) Icon()         悬浮图标（base64 PNG）\n"
        "//    3) IconWebViewData() WebView 图标（支持 GIF）\n"
        "//    4) SettingsList() 设置页(齿轮)条目\n"
        "//  修改外观：标题/图标；修改设置项：SettingsList()。\n"
        "// ============================================================================\n",
}


def main():
    if len(sys.argv) < 2:
        print("用法: python3 tools/cn_localize.py <工程根目录>")
        sys.exit(1)
    root = sys.argv[1]
    replaced = 0
    missed = 0
    for rel, old, new in REPLACEMENTS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            print("[跳过] 文件不存在: " + rel)
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if new in text:
            continue  # 已替换过
        if old in text:
            text = text.replace(old, new)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            replaced += 1
        else:
            missed += 1
    for rel, banner in BANNERS.items():
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if text.startswith(banner):
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(banner + text)
    print("替换完成: %d 处; 未匹配: %d 处; 横幅: %d 个文件" % (replaced, missed, len(BANNERS)))


if __name__ == "__main__":
    main()
