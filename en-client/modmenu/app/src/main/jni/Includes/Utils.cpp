#include "Utils.hpp"
#include "obfuscate.h"
#include <link.h>
#include <cstdio>
#include <cstring>

static uintptr_t libBase;

bool libLoaded = false;

// 基址来源（自检日志用）：dl_iterate_phdr / maps(r-x) / maps(off0) / maps(first)
static char g_libBaseSource[32] = {0};
const char *libBaseSource() { return g_libBaseSource; }

// ---- dl_iterate_phdr：linker 给的权威基址（与 /proc/self/maps 顺序无关）----
struct PhdrSearch { const char *name; uintptr_t base; int found; };

static int phdrCb(struct dl_phdr_info *info, size_t size, void *data) {
    (void) size;
    PhdrSearch *s = (PhdrSearch *) data;
    if (!info->dlpi_name || !info->dlpi_name[0]) return 0;
    const char *p = strrchr(info->dlpi_name, '/');
    p = p ? p + 1 : info->dlpi_name;
    if (strcmp(p, s->name) != 0) return 0;
    uintptr_t vaddr = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        if (info->dlpi_phdr[i].p_type == PT_LOAD && info->dlpi_phdr[i].p_offset == 0) {
            vaddr = (uintptr_t) info->dlpi_phdr[i].p_vaddr;
            break;
        }
    }
    s->base = (uintptr_t) info->dlpi_addr + vaddr;
    s->found = 1;
    return 1;
}

// ============================================================
//  取 libil2cpp.so 基址
//  背景：Android 10+ 同一个 .so 可能被映射两份——
//     r-- 数据视图（地址往往更小，旧实现取到它 → 所有 hook/补丁都写到无效页，且不报错）
//     r-x 代码视图（真正执行的那份）
//  优先级：linker(dl_iterate_phdr) → maps 里 offset==0 且带 x 的段 → offset==0 → 第一条
// ============================================================
DWORD findLibrary(const char *library) {
    // 0) 首选：linker 权威基址
    {
        const char *b = strrchr(library, '/');
        b = b ? b + 1 : library;
        PhdrSearch s;
        s.name = b; s.base = 0; s.found = 0;
        dl_iterate_phdr(phdrCb, &s);
        if (s.found && s.base) {
            snprintf(g_libBaseSource, sizeof(g_libBaseSource), "linker");
            return (DWORD) s.base;
        }
    }

    char filename[0xFF] = {0}, buffer[1024] = {0};
    FILE *fp = NULL;
    DWORD address = 0;
    unsigned long long start = 0, off = 0;
    char perms[8] = {0};

    sprintf(filename, OBFUSCATE("/proc/self/maps"));
    fp = fopen(filename, OBFUSCATE("rt"));
    if (fp == NULL) { perror(OBFUSCATE("fopen")); goto done; }

    // 1) maps：offset==0 且可执行 = 代码视图
    while (fgets(buffer, sizeof(buffer), fp)) {
        if (!strstr(buffer, library)) continue;
        if (sscanf(buffer, "%llx-%*x %7s %llx", &start, perms, &off) != 3) continue;
        if (off == 0 && strchr(perms, 'x')) {
            address = (DWORD) start;
            snprintf(g_libBaseSource, sizeof(g_libBaseSource), "maps-rx");
            goto done;
        }
    }
    // 2) maps：offset==0
    rewind(fp);
    while (fgets(buffer, sizeof(buffer), fp)) {
        if (!strstr(buffer, library)) continue;
        if (sscanf(buffer, "%llx-%*x %7s %llx", &start, perms, &off) == 3 && off == 0) {
            address = (DWORD) start;
            snprintf(g_libBaseSource, sizeof(g_libBaseSource), "maps-0");
            goto done;
        }
    }
    // 3) 兜底：第一条匹配（旧行为）
    rewind(fp);
    while (fgets(buffer, sizeof(buffer), fp)) {
        if (strstr(buffer, library)) {
            address = (DWORD) strtoul(buffer, NULL, 16);
            snprintf(g_libBaseSource, sizeof(g_libBaseSource), "maps-first");
            goto done;
        }
    }

    done:
    if (fp) fclose(fp);
    return address;
}

DWORD getAbsoluteAddress(const char *libraryName, DWORD relativeAddr) {
    libBase = findLibrary(libraryName);
    if (libBase == 0)
        return 0;
    return (reinterpret_cast<DWORD>(libBase + relativeAddr));
}


jboolean isGameLibLoaded(JNIEnv *env, jobject thiz) {
    if (!libLoaded) isLibraryLoaded(OBFUSCATE("libil2cpp.so"));   // 兜底：实时查一次（修复"保存偏好"每次开菜单都提示等待）
    return libLoaded;
}

bool isLibraryLoaded(const char *libraryName) {
    //libLoaded = true;
    char line[512] = {0};
    FILE *fp = fopen(OBFUSCATE("/proc/self/maps"), OBFUSCATE("rt"));
    if (fp != NULL) {
        while (fgets(line, sizeof(line), fp)) {
            std::string a = line;
            if (strstr(line, libraryName)) {
                libLoaded = true;
                return true;
            }
        }
        fclose(fp);
    }
    return false;
}

uintptr_t str2Offset(const char *c) {
    int base = 16;
    // See if this function catches all possibilities.
    // If it doesn't, the function would have to be amended
    // whenever you add a combination of architecture and
    // compiler that is not yet addressed.
    static_assert(sizeof(uintptr_t) == sizeof(unsigned long)
                  || sizeof(uintptr_t) == sizeof(unsigned long long),
                  "Please add string to handle conversion for this architecture.");

    // Now choose the correct function ...
    if (sizeof(uintptr_t) == sizeof(unsigned long)) {
        return strtoul(c, nullptr, base);
    }

    // All other options exhausted, sizeof(uintptr_t) == sizeof(unsigned long long))
    return strtoull(c, nullptr, base);
}
