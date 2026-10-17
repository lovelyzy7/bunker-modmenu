#include <list>
#include <vector>
#include <cstring>
#include <pthread.h>
#include <thread>
#include <string>
#include <algorithm>
#include <chrono>
#include <mutex>
#include <unordered_map>
#include <jni.h>
#include <unistd.h>
#include <fstream>
#include <iostream>
#include <dlfcn.h>
#include "Includes/Logger.h"
#include "Includes/obfuscate.h"
#include "Includes/Utils.hpp"
#include "Menu/Menu.hpp"
#include "Menu/Jni.hpp"
#include "Includes/Macros.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <cerrno>

// ============================================================
//  NieR Reincarnation (nierspww) Mod Menu -- Lunar-Tear  v2
//  功能:
//    1. 伤害倍率    (SeekBar 1-333)  [我方对敌方伤害 x 倍率]
//    2. 防御倍率    (SeekBar 1-333)  [我方受击损失 / 倍率, HP 写入点; 讨伐战内自动跳过]
//    3. 角色技能无CD (Toggle, 默认开)
//    4. God模式免伤  (Toggle, 默认开) [HP 写入点写回当前值; 讨伐战内自动跳过]
//    5. 强制命中     (Toggle, 默认开) [IsEvaded / IsSkillHit]
//    6. 讨伐战上限解除(Toggle, 默认开) [静态指令补丁 45,000,000 -> 2,147,483,647]
// ============================================================

// ---- 运行时配置 (菜单回调会更新) ----
static int  g_dmgMul   = 333;   // 伤害倍率
static int  g_defMul   = 333;   // 防御倍率
static bool g_skillNoCd = true; // 角色技能无CD
static bool g_godMode   = true; // God 模式免伤
static bool g_forceHit  = true; // 强制命中
static bool g_capLift   = true; // 讨伐战上限解除

// ---- 游戏常量 ----
static const int PLAYER_PID  = 0;     // 玩家阵营 PartyId
static const long long DMG_CLAMP = 2100000000LL; // 自设伤害上限（防 int32 溢出）

#define targetLibName OBFUSCATE("libil2cpp.so")
static void applyBhCapPatch(bool enable);

// ---- 游戏函数指针 (运行时解析) ----
typedef void* (*Fn_P1)(void*);
typedef int   (*Fn_I1)(void*);
typedef int   (*Fn_V0)();
static Fn_P1  f_JoinParty   = nullptr; // 0x3E6E3CC  (actor) -> PartyId*
static Fn_P1  f_FromActor   = nullptr; // 0x3B119BC  (skill) -> actor
static Fn_P1  f_TargetActor = nullptr; // 0x3B0CD6C  (behaviour) -> actor
static Fn_I1  f_MaxCool     = nullptr; // 0x3B11D5C  (skill) -> max
static Fn_I1  f_HpGet       = nullptr; // 0x3E7608C  (actor) -> current hp
static Fn_V0  f_IsInBigHunt = nullptr; // 0x34F3C70  () -> bool (是否在讨伐战内, 防卡死)

// 对象 +0x10 处的 int Id (PartyId / TeamId)
static inline int ptrId(void* obj) {
    if (!obj) return -999;
    return *(int *) ((uintptr_t) obj + 0x10);
}
static inline int pidOf(void* actor) {
    if (!f_JoinParty || !actor) return -999;
    return ptrId(f_JoinParty(actor));
}

// ---- 幂等历史: 只缩放每个新计算值的第一次写入, 管线回读跳过 ----
static int g_logCount = 0;
static char g_diagBase[32] = {0}, g_diagHook[64] = {0};   // 启动自检：基址来源/挂钩数/上限补丁状态（显示在菜单里）
static int g_bhSkipLog = 0;

struct HistEntry { uint64_t t; std::vector<int> vals; };
static std::mutex g_histMutex;
static std::unordered_map<uintptr_t, HistEntry> g_hist;

static inline uint64_t nowMs() {
    using namespace std::chrono;
    return (uint64_t) duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}
static bool isReadBack(uintptr_t key, int v) {
    std::lock_guard<std::mutex> lk(g_histMutex);
    auto it = g_hist.find(key);
    if (it == g_hist.end()) return false;
    if (nowMs() - it->second.t > 250) return false;
    return std::find(it->second.vals.begin(), it->second.vals.end(), v) != it->second.vals.end();
}
static void markWrite(uintptr_t key, int v) {
    std::lock_guard<std::mutex> lk(g_histMutex);
    auto &h = g_hist[key];
    if (nowMs() - h.t > 250) h.vals.clear();
    h.t = nowMs();
    if (std::find(h.vals.begin(), h.vals.end(), v) == h.vals.end()) h.vals.push_back(v);
    if (h.vals.size() > 20) h.vals.erase(h.vals.begin());
}

// ---- 请求对象辅助 ----
static bool isPlayerTargetBehaviour(void* data) {
    void *tgt = (f_TargetActor && data) ? f_TargetActor(data) : nullptr;
    return pidOf(tgt) == PLAYER_PID;
}

// ============================================================
//  菜单功能列表 / 回调
// ============================================================
static void refreshDiag();   // 定义在 g_hooks 之后

jobjectArray GetFeatureList(JNIEnv *env, jobject context) {
    jobjectArray ret;

    std::vector<std::string> feats;
    feats.push_back("Category_战斗功能");
    feats.push_back("1_SeekBar_伤害倍率_1_333");
    feats.push_back("2_SeekBar_防御倍率(讨伐战禁用)_1_333");
    feats.push_back("3_True_Toggle_角色技能无CD");
    feats.push_back("4_True_Toggle_God模式免伤(讨伐战禁用)");
    feats.push_back("5_True_Toggle_强制命中");
    feats.push_back("6_True_Toggle_讨伐战上限解除");
    feats.push_back("19_Button_刷新自检");
    feats.push_back(std::string("17_RichTextView_自检基址: ") + (g_diagBase[0] ? g_diagBase : "等待游戏库…"));
    feats.push_back(std::string("18_RichTextView_自检挂钩: ") + (g_diagHook[0] ? g_diagHook : "等待游戏库…"));

    int Total_Feature = (int) feats.size();
    ret = (jobjectArray)
            env->NewObjectArray(Total_Feature, env->FindClass(OBFUSCATE("java/lang/String")),
                                env->NewStringUTF(""));

    for (int i = 0; i < Total_Feature; i++)
        env->SetObjectArrayElement(ret, i, env->NewStringUTF(feats[i].c_str()));

    return (ret);
}

void Changes(JNIEnv *env, jclass clazz, jobject obj, jint featNum, jstring featName, jint value,
             jlong Lvalue, jboolean boolean, jstring text) {
    switch (featNum) {
        case 1:
            g_dmgMul = (value >= 1) ? value : g_dmgMul;
            LOGI(OBFUSCATE("Changes[1] dmgMul=%d"), g_dmgMul);
            break;
        case 2:
            g_defMul = (value >= 1) ? value : g_defMul;
            LOGI(OBFUSCATE("Changes[2] defMul=%d"), g_defMul);
            break;
        case 3:
            g_skillNoCd = boolean;
            LOGI(OBFUSCATE("Changes[3] skillNoCd=%d"), (int) g_skillNoCd);
            break;
        case 4:
            g_godMode = boolean;
            LOGI(OBFUSCATE("Changes[4] godMode=%d"), (int) g_godMode);
            break;
        case 5:
            g_forceHit = boolean;
            LOGI(OBFUSCATE("Changes[5] forceHit=%d"), (int) g_forceHit);
            break;
        case 6:
            g_capLift = boolean;
            if (f_JoinParty) applyBhCapPatch(boolean);   // 运行时补丁 / 还原
            LOGI(OBFUSCATE("Changes[6] capLift=%d"), (int) g_capLift);
            break;
        case 19:
            refreshDiag();   // Java 侧随后重建列表显示新值
            break;
        default:
            LOGI(OBFUSCATE("Changes[?] featNum=%d value=%d bool=%d"), (int) featNum, (int) value, (int) boolean);
            break;
    }
}

// ============================================================
//  钩子 1: AttackDamage 字段 setter -> 伤害倍率 (仅敌方目标)
// ============================================================
void (*old_AtkDamageSetter)(void *data, int value);

void AtkDamageSetter(void *data, int value) {
    int v = value;
    if (v > 0 && data && g_dmgMul > 1) {
        uintptr_t key = (uintptr_t) data;
        if (!isReadBack(key, v)) {
            if (!isPlayerTargetBehaviour(data)) {
                long long x = (long long) v * (long long) g_dmgMul;
                int nv = (int) (x > DMG_CLAMP ? DMG_CLAMP : x);
                if (nv != v) {
                    value = nv;
                    markWrite(key, nv);
                    if (g_logCount < 40 || (g_logCount % 500) == 0) {
                        g_logCount++;
                        LOGI(OBFUSCATE("dmg v=%d -> %d (x%d)"), v, nv, g_dmgMul);
                    }
                }
            }
        }
    }
    old_AtkDamageSetter(data, value);
}

// ============================================================
//  钩子 2: HP 写入点 -> God 模式 / 防御倍率
//     我方 HP 即将下降时:
//       god  : 写回当前 HP（不受伤）
//       防御 : 损失量 / 防御倍率
// ============================================================
void (*old_HpSet)(void *actor, int hp);

void HpSet(void *actor, int hp) {
    if (actor && f_HpGet) {
        if (pidOf(actor) == PLAYER_PID) {
            int cur = f_HpGet(actor);
            if (cur > 0 && hp < cur) {
                // 讨伐战内不改 HP：修改 HP 会导致波次结束时角色不播消失动画 -> 卡死
                if (f_IsInBigHunt && f_IsInBigHunt()) {
                    if (g_bhSkipLog < 3) { g_bhSkipLog++; LOGI(OBFUSCATE("BigHunt: HP mod skipped (anti-freeze)")); }
                } else if (g_godMode) {
                    hp = cur;
                } else if (g_defMul > 1) {
                    int delta = cur - hp;
                    hp = cur - delta / g_defMul;
                }
            }
        }
    }
    old_HpSet(actor, hp);
}

// ============================================================
//  钩子 3: 技能充能 setter -> 角色技能无CD (强制满)
// ============================================================
void (*old_CurCoolSet)(void *skill, int value);

void CurCoolSet(void *skill, int value) {
    if (g_skillNoCd && skill && f_FromActor && f_MaxCool) {
        void *from = f_FromActor(skill);
        if (from && pidOf(from) == PLAYER_PID) {
            int mx = f_MaxCool(skill);
            if (mx > 0 && value != mx) value = mx;
        }
    }
    old_CurCoolSet(skill, value);
}

// ============================================================
//  钩子 4-6: 强制命中 (只对我方攻击生效)
// ============================================================
bool (*old_IsEvadedGet)(void *data);
bool IsEvadedGet(void *data) {
    bool r = old_IsEvadedGet(data);
    if (g_forceHit && data && !isPlayerTargetBehaviour(data)) return false;
    return r;
}

void (*old_IsEvadedSet)(void *data, bool isEvaded);
void IsEvadedSet(void *data, bool isEvaded) {
    if (g_forceHit && data && !isPlayerTargetBehaviour(data)) isEvaded = false;
    old_IsEvadedSet(data, isEvaded);
}

bool (*old_IsSkillHit)(void *skill, void *fromActor);
bool IsSkillHit(void *skill, void *fromActor) {
    bool r = old_IsSkillHit(skill, fromActor);
    if (g_forceHit && fromActor && pidOf(fromActor) == PLAYER_PID) return true;
    return r;
}

// ============================================================
//  静态指令补丁: 讨伐战每击上限 45,000,000 -> 2,147,483,647
//    原: movz w2,#0xa540 ; movk w2,#0x2ae,lsl 16
//    新: movz w2,#0xffff ; movk w2,#0x7fff,lsl 16
// ============================================================
static void applyBhCapPatch(bool enable) {
    if (enable) {
        PATCH(targetLibName, str2Offset(OBFUSCATE("0x32475EC")), "E2 FF 9F 52 E2 FF AF 72");
        LOGI(OBFUSCATE("bh cap lift ON"));
    } else {
        PATCH(targetLibName, str2Offset(OBFUSCATE("0x32475EC")), "02 A8 94 52 C2 55 A0 72");
        LOGI(OBFUSCATE("bh cap lift OFF"));
    }
}

// ============================================================
//  挂钩可靠性层（P1）
//    - 装钩前记录原字节，装完立即校验，失败重试一次
//    - 后台看门狗每 2 秒复查 6 个挂钩点 + 上限补丁，丢失自动重装
//    - 日志：[hook] xxx OK/FAIL、[hook] summary、[watch] lost -> reinstall
// ============================================================
static const uint8_t BH_CAP_ORIG[8]  = {0x02,0xA8,0x94,0x52,0xC2,0x55,0xA0,0x72};
static const uint8_t BH_CAP_PATCH[8] = {0xE2,0xFF,0x9F,0x52,0xE2,0xFF,0xAF,0x72};

struct HookSlot {
    const char *name;
    const char *rva;
    void       *replace;
    void      **orig;
    uint8_t     origBytes[16];
    volatile int alive;
    volatile int fails;
};

#define PROC_HEAD16 {0xf5,0x0f,0x1d,0xf8,0xf4,0x4f,0x01,0xa9,0xfd,0x7b,0x02,0xa9,0xfd,0x83,0x00,0x91}

static HookSlot g_hooks[] = {
    {"AtkDamage",   "0x3B0C980", (void *) AtkDamageSetter, (void **) &old_AtkDamageSetter, PROC_HEAD16, 0, 0},
    {"HpSet",       "0x3E761B8",  (void *) HpSet,           (void **) &old_HpSet,           PROC_HEAD16, 0, 0},
    {"CurCoolSet",  "0x3B11F10",(void *) CurCoolSet,      (void **) &old_CurCoolSet,      PROC_HEAD16, 0, 0},
    {"IsEvadedGet", "0x3B0CA0C", (void *) IsEvadedGet,     (void **) &old_IsEvadedGet,     PROC_HEAD16, 0, 0},
    {"IsEvadedSet", "0x3B0CAA0", (void *) IsEvadedSet,     (void **) &old_IsEvadedSet,     PROC_HEAD16, 0, 0},
    {"IsSkillHit",  "0x2C8C88C", (void *) IsSkillHit,      (void **) &old_IsSkillHit,
     {0xfc,0x6f,0xba,0xa9,0xfa,0x67,0x01,0xa9,0xf8,0x5f,0x02,0xa9,0xf6,0x57,0x03,0xa9}, 0, 0},
};
static const int g_hookCount = (int) (sizeof(g_hooks) / sizeof(g_hooks[0]));

// 自检用：已经成功挂钩的方法数（old_ 指针非空即成功）。
static int countHooksInstalled() {
    int ok = 0;
    for (int i = 0; i < g_hookCount; i++) {
        if (g_hooks[i].orig && *g_hooks[i].orig) ok++;
    }
    return ok;
}

// 刷新自检：重算基址来源、已挂钩数与上限补丁状态（菜单 17/18 行显示）。
static void refreshDiag() {
    snprintf(g_diagBase, sizeof(g_diagBase), "%s", libBaseSource());
    snprintf(g_diagHook, sizeof(g_diagHook), "%d/%d 上限%s", countHooksInstalled(), g_hookCount,
             g_capLift ? "ON" : "OFF");
    LOGI(OBFUSCATE("diag refreshed: %s %s"), g_diagBase, g_diagHook);
}

static inline void *hookAddr(const char *rva) {
    return (void *) getAbsoluteAddress(targetLibName, str2Offset(rva));
}

static bool hookAlive(const HookSlot &h) {
    void *addr = hookAddr(h.rva);
    if (!addr) return false;
    return memcmp(addr, h.origBytes, 16) != 0;      // 已被改写 = 挂钩在位
}

static bool installHook(HookSlot &h) {
    void *addr = hookAddr(h.rva);
    if (!addr) { LOGI(OBFUSCATE("[hook] %s addr=NULL"), h.name); h.alive = 0; return false; }
    hook(addr, h.replace, h.orig);
    bool ok = hookAlive(h);
    if (!ok) {                                       // 瞬时失败（mprotect/池竞争）→ 稍后重试
        usleep(150 * 1000);
        hook(addr, h.replace, h.orig);
        ok = hookAlive(h);
    }
    h.alive = ok ? 1 : 0;
    LOGI(OBFUSCATE("[hook] %s %s"), h.name, ok ? OBFUSCATE("OK") : OBFUSCATE("FAIL"));
    return ok;
}

static void *watch_thread(void *) {
    LOGI(OBFUSCATE("[watch] watchdog started"));
    for (;;) {
        sleep(2);
        for (int i = 0; i < g_hookCount; i++) {
            HookSlot &h = g_hooks[i];
            if (hookAlive(h)) { h.alive = 1; continue; }
            h.alive = 0;
            h.fails++;
            bool ok = installHook(h);
            LOGI(OBFUSCATE("[watch] %s lost -> reinstall %s (n=%d)"),
                 h.name, ok ? OBFUSCATE("OK") : OBFUSCATE("FAIL"), (int) h.fails);
        }
        void *site = hookAddr("0x32475EC");
        if (site && g_capLift && memcmp(site, BH_CAP_PATCH, 8) != 0) {
            applyBhCapPatch(true);
            LOGI(OBFUSCATE("[watch] cap patch lost -> reapplied"));
        }
    }
    return nullptr;
}

// ============================================================
void *hack_thread(void *) {
    LOGI(OBFUSCATE("pthread created"));

    ElfScanner g_il2cppELF;
    do {
        sleep(1);
        g_il2cppELF = ElfScanner::createWithPath(targetLibName);
    } while (!g_il2cppELF.isValid());

    LOGI(OBFUSCATE("%s has been loaded"), (const char *) targetLibName);
    isLibraryLoaded(targetLibName);   // A：置位 libLoaded（修复"保存偏好"每次开菜单提示等待）
    LOGI(OBFUSCATE("[boot] libLoaded=1 base=0x%lx source=%s"),
         (unsigned long) getAbsoluteAddress(targetLibName, 0), libBaseSource());
    snprintf(g_diagBase, sizeof(g_diagBase), "%s", libBaseSource());

#if defined(__aarch64__)
    (void) g_il2cppELF;

    // ---- 解析辅助函数指针 ----
    f_JoinParty   = (Fn_P1) getAbsoluteAddress(targetLibName, str2Offset(OBFUSCATE("0x3E6E3CC")));
    f_FromActor   = (Fn_P1) getAbsoluteAddress(targetLibName, str2Offset(OBFUSCATE("0x3B119BC")));
    f_TargetActor = (Fn_P1) getAbsoluteAddress(targetLibName, str2Offset(OBFUSCATE("0x3B0CD6C")));
    f_MaxCool     = (Fn_I1) getAbsoluteAddress(targetLibName, str2Offset(OBFUSCATE("0x3B11D5C")));
    f_HpGet       = (Fn_I1) getAbsoluteAddress(targetLibName, str2Offset(OBFUSCATE("0x3E7608C")));
    f_IsInBigHunt = (Fn_V0) getAbsoluteAddress(targetLibName, str2Offset(OBFUSCATE("0x34F3C70")));

    // ---- 挂载钩子 ----
    // ---- 挂载钩子（逐点校验 + 重试，P1 可靠性层）----
    sleep(1);                       // 等加载器稳定，降低 mprotect 竞争
    int okCount = 0, failCount = 0;
    for (int i = 0; i < g_hookCount; i++) {
        snprintf(g_diagHook, sizeof(g_diagHook), "安装中 %d/%d (%s)", i, g_hookCount, g_hooks[i].name);
        if (installHook(g_hooks[i])) okCount++; else failCount++;
    }
    LOGI(OBFUSCATE("[hook] summary %d OK / %d FAIL (total %d)"), okCount, failCount, g_hookCount);
    snprintf(g_diagBase, sizeof(g_diagBase), "%s", libBaseSource());
    snprintf(g_diagHook, sizeof(g_diagHook), "%d/%d 上限%s", okCount, g_hookCount, g_capLift ? "ON" : "OFF");

    // ---- 自愈看门狗 ----
    pthread_t wtid;
    pthread_create(&wtid, NULL, watch_thread, NULL);

    // ---- 静态补丁 ----
    if (g_capLift) applyBhCapPatch(true);
#elif defined(__arm__)
    // 本游戏只有 arm64-v8a, 不编译 32 位逻辑
#endif

    LOGI(OBFUSCATE("Done"));
    return nullptr;
}

__attribute__((constructor))
void lib_main() {
    pthread_t ptid;
    pthread_create(&ptid, NULL, hack_thread, NULL);
}
