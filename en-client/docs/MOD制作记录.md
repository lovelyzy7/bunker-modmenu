# NieR Reincarnation 私服客户端 · 内置 Mod 菜单 制作记录

> 最后更新: 2026-10-03 15:35 (CST) — Mod 菜单 v1.0 已构建并签名（output/）
> 编码说明: 所有文本文件（.md/.js/.py）统一为 UTF-8 with BOM；config.json 为纯 ASCII 无 BOM（兼容 JSON 解析器）
> 维护约定: 每完成一项验证 / 改动 / 新发现，同步更新本文件。
> 文件位置: `docs/MOD制作记录.md`

---

## 0. 总目标与功能状态

制作内置 Mod 菜单（LGL Mod Menu 4.0 模板，`Android-Mod-Menu-4.0.zip`），
最终打包进已 patched 的客户端 `patched-local-6.apk`。

| # | 功能 | Frida 日志验证 | 游戏内可见 | 备注 |
|---|------|----------------|------------|------|
| 1 | 伤害倍率 `dmgMul`（已合并原"攻击×伤害"） | ✅ | ✅ | 滑块；当前 ×256 |
| 2 | ~~多倍攻击~~ | — | — | 已合并进 #1（2026-10-03 15:08） |
| 3 | 多倍防御 `defMul` | ✅ | ✅ v4 生效 | 当前 ÷256（受击 0~1，v1 等效） |
| 4 | 角色技能(3个)无CD | ✅ | ✅ 已确认 | 每次使用后立即满充能 |
| 5 | 同伴技能无CD | — | — | ❌ 不做（v8 移除）；同伴攻击/伤害仍吃倍率（同字段路径） |
| 6 | COMBO 默认最大/不中断 | ❌ 已移除 | — | （功能弃用，偏移仅存档） |

**当前倍率**: `dmgMul=256, defMul=256`（攻击/伤害已合并；滑块可调，见【9】）。

---

## 1. 环境与工具（通用描述）

| 项 | 值 |
|----|----|
| 主机 | Windows（含 WSL2 / Git Bash）或 Linux 均可；仓库路径自定 |
| Python | 3.x（开发阶段用于运行 `archive/scripts/` 下的调试脚本） |
| adb | Android platform-tools 中的 adb（加入 PATH 或用绝对路径） |
| 手机 | 已 root，USB 调试已授权（设备名以本机为准） |
| 游戏 | 包名 `com.square_enix.android_googleplay.nierspww`（Global）；进程名 `NieR` |

> 说明：开发阶段用于定位函数 / 验证数值的脚本存档在 `archive/scripts/`；
> **构建与日常使用只需按 `docs/一键构建说明.md` 运行一键脚本**，不需要这些脚本。
> 本机工具路径可通过 `tools/toolpaths.json`（本地覆盖，不入库）配置，
> 留空项会自动探测；模板见 `tools/toolpaths.example.json`。

---

## 2. 资产与版本核对

| 项 | 值 |
|----|----|
| 目标 APK | `patched-local-6.apk`（265,744,853 B） |
| 解包目录 | `mod-menu/patched/`（apktool 产物） |
| libil2cpp.so | `patched/lib/arm64-v8a/libil2cpp.so`，size=127,359,872 B |
| libil2cpp.so md5 | `39eb293e50318f15dabfce9ba61e5998` |
| 手机安装版 | md5 相同 ✅（dump 偏移对线上版本有效） |
| Il2CppDumper 输出 | `mod-menu/dump/`：`dump.cs`(50MB) / `il2cpp.h` / `script.json` / `stringliteral.json` / `DummyDll/` |

运行时代码地址 = `libil2cpp.so` 基址(ASLR 随机) + RVA：
`Process.findModuleByName('libil2cpp.so').base.add(rva)`

---

## 3. 战斗系统机制（命名空间 `Dark.Game.TurnBattle`）

### 3.1 SoA 数据架构
运行时数据放在 `DataStructure`（类）里，通过静态扩展访问器读写：
`FieldTurnBattleXxx(DataStructure data[, value])`。访问器都是独立函数，可直接 Hook。

### 3.2 阵营判定（最重要）
- `FieldTurnBattleActorJoinParty(actor)` → `PartyId` 对象，`Id` 在对象 `+0x10`
  - **玩家 PartyId = 0，敌方 = 1**（两场战斗实测）
- `FieldTurnBattleTeamOwnTeamId(team)` → `TeamId` 对象，`Id` 在 `+0x10`
  - **玩家 TeamId = 1，敌方 = 2**（combo-add 实测：我方攻击同时 tid=1 +1）
- 敌我双方走相同伤害流程，**必须用 PartyId/TeamId 判阵营，不能用 src**

### 3.3 伤害管线（实测顺序）与倍率挂点
1. `ComputerTurnBattleSkillBehaviourAttackPower.OnCompute`（RVA `0x33675AC`）计算攻击力
2. `FieldTurnBattleComputerSkillBehaviourAttackDamage` setter（RVA `0x3B0C980`）
   写入"未减免伤害"字段。
   > ⚠️ **坑**: 单次攻击该 setter 被调用约 8 次，且是"读-改-写"级联。
   > v1 在此 ×2 实测变成 ×256（993→1986→…→254208）。**禁止在此做倍率**。
3. `CalculatorActorStatusDefault.CalculateDamageValue`（RVA `0x3247968`）
   ```
   void CalculateDamageValue(DataStructure target, int unclampedDamage,
                             out int resultUnclampedDamage, out int resultActualDamage)
   ```
   - `args[2]`=unclamped 输入；`args[3]`/`args[4]`=out 指针（o1/o2）
   - `o2` = 实际伤害（按目标剩余 HP 钳制：实测 217→158、336→0）
   - **敌我双方攻击都经过此函数**（我方受击 11 次也命中）
4. `CalculatorActorStatusDefault.ApplyDamage`（RVA `0x32478E4`）扣血

**倍率实现演进（重要结论）**：
- v1 挂在 `AttackDamage` 字段 setter：游戏内**明显生效**
  （防御÷256→受击 0~15；攻击×256→伤害极高），但 8 次读写级联导致 ×2^8。
- v2/v3/v3.1 改挂 `CalculateDamageValue`（输入/o1/o2）：日志数值正确，
  **游戏内完全不可见** ⇒ 该路径不是真实结算路径（或仅部分视觉/统计用）。
- **v4 结论：真正生效的是 `AttackDamage` 字段(setter)路径**，
  采用"幂等缩放"：只缩放每个新计算值的**第一次写入**，
  管线回读（值在最近 250ms 已写集合中）则跳过，避免级联。
  - 敌方目标: `v *= dmgMul`（原 atkMul×dmgMul 已合并为单值）
  - 我方目标: `v = floor(v / defMul)`
  - 另挂 `FieldTurnBattleActorDynamicCurrentHp` setter 日志用于验证真实扣血
  - **Q&A（2026-10-03）**：多倍攻击与多倍伤害挂在同一字段、同一乘法点，
    等效于单一系数 `atkMul × dmgMul`；两者无主次之分 ⇒
    **已于 2026-10-03 15:08 合并为单一 `dmgMul`（当前 ×256）**。
  - 覆盖范围：普攻 / 主动技能 / 同伴攻击等标准伤害均走此字段；
    DoT(Abnormal) / HP 比例伤害 / 固定伤害等特殊来源未逐一验证是否经过此字段。
  - **v4 实测 ✅**：`mod-atk-field` 429→1716（纯 ×4）、`mod-def-field` 294→147（纯 ÷2）、
    `hp-set` 我方 8759→8597（-162，与 ÷2 后字段值吻合）⇒ 字段路径确认，幂等防级联成功
  - 当前值：`dmgMul=256`、`defMul=256`；通过 `config.json` 可调，无需改脚本

### 3.4 DamageSourceType 枚举（`dump.cs` 1188706 行）
| 值 | 名称 |
|----|------|
| 0 | Unknown |
| 1 | Abnormal (DoT 等) |
| 2 | DefaultSkill (普攻) |
| 3 | CounterSkill (反击) |
| 4 | WeaponActiveSkill (角色武器技能) |
| 5 | CostumeActiveSkill (服装技能) |
| 6 | CompanionSkill (同伴技能) |
| 7 | PassiveSkill |

> 敌方也用 4/5 等值 ⇒ 只能辅助分类，不能定阵营。

### 3.5 角色技能冷却（充能式）
- 每个技能 `DataStructure` 字段：
  - `FieldTurnBattleSkillDynamicCurrentCooltime`（当前值，0→max 递增，满=可用）
  - `FieldTurnBattleSkillDynamicMaxCooltime`（上限，会被 buff 修改）
  - `FieldTurnBattleSkillStaticMaxCooltime`（静态上限）
  - 单位=帧；实测玩家技能 max：480 / 600 / 1500
- **无CD实现**：Hook CurrentCooltime setter（RVA `0x3B11F10`），
  技能归属 `FieldTurnBattleSkillFromActor` → `JoinParty==0` 时，
  把写入值替换为 `DynamicMaxCooltime`（RVA `0x3B11D5C`）。
  效果：开局满充能 + 用完后立刻再满（实测连发成功 ✅）
- 相关调度器 `SkillComponentCooltimeDispatcher`：
  `OnExecuteActiveSkill` / `OnExecuteCompanionSkill` / `CheckCoolTime`

### 3.6 同伴技能冷却（❌ 已取消，不做此功能；以下为技术记录）
- 队伍级：`CalculatorSkill.TryGetCompanionSkillCooltime(party, out max, out cur)`（RVA `0x2C8CFAC`）
- 开关判定：`HasUsableCompanionSkill(party)`（`0x2C8D350`）、
  `HasUsableCompanionSkillMine()`（`0x2C8D2C8`，内部调用前者）
- 当前实现：两个 `HasUsable*` onLeave 强制返回 true
- 备选：`TryGetCompanionSkillCooltime` 的 out 参数直接改写
- **Q: 多倍攻击/伤害是否包括同伴？** A: 同伴技能对敌伤害走同一 `AttackDamage` 字段路径，
  会被 `dmgMul`（当前 ×256）放大；已加日志验证。同伴治疗/增益不吃倍率。
- **实测（2026-10-03 14:2x）**：同伴伤害吃倍率 ✅（用户确认）。
  同伴无CD ❌：首放可用，之后按钮亮但内部技能灰色、不充能、无法再放。
  - `TryGetCompanionSkillCooltime` 高频轮询返回 `max=0/cur=0/false`
  - `exec-companion` 有事件；`src=6` 的 ApplyDamage 一个都没有（同伴伤害可能用其他 src）
  - v6 诊断（auto2.log）：同伴技能同属 `SkillComponentCooltimeDispatcher`，`DynamicMaxCooltime=1110`；
    我们已把其冷却强制满（`mod-cd comp:true` 0→1110），但 UI 仍灰色 ⇒
    灰色判定不在冷却字段，而在 `FieldTurnBattleSkillSkillState`（技能状态字段，get `0x3B122FC` / set `0x3B12390`）。
  - v7：自学习角色技能的"就绪"状态值（cur>=max 时写入的 state），
    对同伴技能强制该状态；`TryGetCompanionSkillCooltime` 强制返回 true + 满值。
  - **最终决定（2026-10-03 14:40）**：不做同伴无CD，v8 已移除全部同伴相关钩子。
    注意：仅移除"无CD"，同伴的攻击/伤害倍率不受影响——
    倍率挂在 `AttackDamage` 字段（按目标阵营判定），同伴攻击敌方同样经过该字段，自动吃到 ×256。
    技术结论备查：同伴技能与角色技能共用 `SkillComponentCooltimeDispatcher`，
    但 UI 灰色判定在 `FieldTurnBattleSkillSkillState`（另有 `TryGetCompanionSkillCooltime` 队伍级查询）。

### 3.7 COMBO（最大 + 不中断）【功能已弃用，仅存档】
- 核心类 `CalculatorTurnBattleCombo`：
  - `AddComboCount(team, additive)` `0x2C880F4`
  - `ResetComboCount(team)` `0x2C8818C` ← "中断"元凶
  - `GetCurrentComboCount(team)` `0x2C881F8`
  - `CalculateComboDamageCoefficient(n)` `0x2C880BC`（加成系数, permil）
- 队伍字段：`FieldTurnBattleTeamComboCount` get/set（`0x3B166CC` / `0x3B16760`）
- 加成表：主数据 `EntityMComboCalculationSetting { ComboCountLowerLimit, DamageCoefficientPermil }`（1000 permil = 1.0×）
- **显示是事件驱动的**（不轮询字段）：`BattleComboView.PlayComboAnimation(comboCount, addComboCount)`（`0x3149B94`）、
  `PlayBaseIdleCombo(count)`（`0x314A764`）
- 当前实现：
  1. 玩家 TeamId=1 的 `TeamComboCount` getter/setter 强制 100
  2. `GetCurrentComboCount` 对玩家强制返回 100
  3. `ResetComboCount` 用 `Interceptor.replace`：玩家队伍直接跳过（不断）
  4. **新增**：`PlayComboAnimation` / `PlayBaseIdleCombo` 强制显示 100
- 用户反馈：计数非最大但"持续时间挺长"（说明 1-3 起到了"不断"的效果，但 UI 显示未覆盖）

### 3.8 伤害飘字 / 伤害数字 UI 路径（新增定位）
- `BattleDamageView`：
  - `SetStandard(int damage, Vector3 pos, bool isCritical, bool isActiveSkill)` `0x314E6E0`
  - `SetWeak(...)` `0x314E804`、`SetResist(...)` `0x314E928`
  - `SetRecovery(...)` `0x314EA4C`、`SetAbnormal(...)` `0x314EC5C`、`SetHpRatioDamage(...)` `0x314EB68`
- `DamageLabelBase.SetEffectDamageText(int damage)` `0x2F85BE4`（文本最终落地）
- 若 v3.1 缩放 o1 后飘字仍不变 ⇒ 下一步直接挂 `BattleDamageView.SetStandard` 等，
  用 ApplyDamage 的阵营标记在 100ms 窗口内判定敌我后缩放置。

---

## 4. 偏移表（RVA，相对 libil2cpp.so 基址）

> **说明**
> - 表中 RVA 全部取自 `dump/dump.cs` 中方法定义上一行的 `// RVA: 0x...`
>   （本 dump 里 RVA = Offset = VA，都是相对 libil2cpp.so 基址的偏移）。
> - 运行时地址 = `Process.findModuleByName('libil2cpp.so').base + RVA`
>   （基址每次启动随机，ASLR；同一进程内不变）。
> - 自查方法：在 dump.cs 搜方法名，取上方 `// RVA:` 行即可。
> - 版本绑定：换 APK / 游戏版本后 libil2cpp.so 会变，RVA 必须重新 dump。

### 4.1 v8 正式功能实际使用

| 函数 | RVA | 签名 / 用途 |
|------|-----|-------------|
| FieldTurnBattleComputerSkillBehaviourAttackDamage setter | 0x3B0C980 | `void(data, int)` 写入结算伤害；**倍率挂点**（幂等防级联） |
| CalculatorActorStatusDefault.CalculateDamageValue | 0x3247968 | `void(this, target, unc, out unc2, out act)` 实际伤害计算（验证） |
| CalculatorActorStatusDefault.ApplyDamage | 0x32478E4 | `void(this, actor, dmg, unc, src, hits)` 扣血 |
| FieldTurnBattleActorJoinParty getter | 0x3E6E3CC | `PartyId*(actor)` → 读 +0x10（玩家=0 / 敌=1） |
| FieldTurnBattleComputer...AttackTargetParameterActor getter | 0x3B0CD6C | `DataStructure*(behaviour)` 取目标（判阵营） |
| FieldTurnBattleActorDynamicCurrentHp setter | 0x3E761B8 | `void(actor, hp)` HP 变化（验证扣血） |
| FieldTurnBattleSkillFromActor getter | 0x3B119BC | `DataStructure*(skill)` 技能归属角色（判阵营） |
| FieldTurnBattleSkillDynamicCurrentCooltime setter | 0x3B11F10 | `void(skill, v)` 充能值；**角色技能无CD挂点** |
| FieldTurnBattleSkillDynamicMaxCooltime getter | 0x3B11D5C | `int(skill)` 充能上限（强制满用） |
| FieldTurnBattleTeamOwnTeamId getter | 0x3B162A0 | `TeamId*(team)` → 读 +0x10（玩家队=1 / 敌=2） |
| FieldTurnBattleTeamComboCount getter / setter | 0x3B166CC / 0x3B16760 | `int(team)` / `void(team,int)` COMBO 计数 |
| CalculatorTurnBattleCombo.GetCurrentComboCount | 0x2C881F8 | `int(this, team)` 当前 COMBO |
| CalculatorTurnBattleCombo.ResetComboCount | 0x2C8818C | 重置（用 replace 跳过 → 不断） |
| BattleComboView.PlayComboAnimation | 0x3149B94 | `void(this, combo, add)` UI 显示编号（强制 100） |
| BattleComboView.PlayBaseIdleCombo | 0x314A764 | `void(this, count)` UI 待机计数 |

### 4.2 验证 / 测试辅助

| 函数 | RVA | 说明 |
|------|-----|------|
| FieldTurnBattleActorDynamicHp getter / setter | 0x3E75C74 / 0x3E75DA0 | `int(actor)` / `void(actor,int)` |
| FieldTurnBattleActorDynamicCurrentHp getter | 0x3E7608C | `int(actor)` |
| FieldTurnBattleActorDynamicVitality getter / setter | 0x3E768BC / 0x3E769E8 | `int(actor)` 防御(活力)值 |
| FieldTurnBattleActorParameterParty getter / setter | 0x3E6EE90 / 0x3E6EF64 | `DataStructure*(actor)` 所属队伍 |
| FieldTurnBattleComputer...AttackOwnParameterActor getter | 0x3B0CECC | `DataStructure*(behaviour)` 攻击者 |
| FieldTurnBattleSkillSkillHash getter | 0x3B1175C | `SkillHash(skill)` 技能标识 |
| FieldTurnBattleComputerSkillBehaviourAttackDamage getter | 0x3B0C8EC | `int(data)` 读结算伤害字段 |
| CalculatorActorStatusBigHunt.CalculateDamageValue | 0x32474BC | BigHunt 模式的伤害计算（备用） |
| CalculatorActorStatusBigHunt.ApplyDamage | 0x3247374 | BigHunt 模式的扣血（备用） |
| CalculatorActorStatusDefault..ctor | 0x3247CAC | 战斗初始化标记（战斗开始） |
| CalculatorActorStatusBigHunt..ctor | 0x32478DC | BigHunt 初始化标记 |
| SetCalculatorActorStatus | 0x36F2D28 | 战斗初始化（注入 calculator） |

### 4.3 冷却系统内部（研究 / 备用）

| 函数 | RVA | 说明 |
|------|-----|------|
| SkillComponentCooltimeDispatcher.AddCalculateSkill | 0x32C5E94 | `void(this, skill)` 注册参与冷却计算的技能 |
| SkillComponentCooltimeDispatcher.RemoveCalculateSkill | 0x32C6BD4 | 移除 |
| SkillComponentCooltimeDispatcher.UpdateSkillState | 0x32C5FC8 | 根据冷却更新技能状态（灰/亮） |
| SkillComponentCooltimeDispatcher.OnFrameUpdate | 0x32C6880 | 每帧充能 |
| SkillComponentCooltimeDispatcher.OnTurnbaseUpdate | 0x32C6870 | 回合制更新 |
| SkillComponentCooltimeDispatcher.CheckCoolTime | 0x32C6A54 | 冷却检查 |
| SkillComponentCooltimeDispatcher.OnExecuteActiveSkill | 0x32C70A8 | 角色技能执行时回调 |
| SkillComponentCooltimeDispatcher.OnExecuteDefaultSkill | 0x32C7348 | 普攻执行时回调 |
| SkillComponentCooltimeDispatcher.OnExecuteCompanionSkill | 0x32C6E64 | 同伴技能执行时回调 |
| SkillComponentCooltimeDispatcher.OnSkillHit | 0x32C7604 | 命中回调 |
| SkillComponentCooltimeDispatcher.DispatchSkillCoolTimeFull | 0x32C6B40 | 冷却充满派发 |
| SkillComponentCooltimeDispatcher.PauseCooltimeCount / ResumeCooltimeCount | 0x32C6668 / 0x32C6674 | 暂停/恢复充能 |
| FieldTurnBattleSkillStaticMaxCooltime getter | 0x3B11C3C | 静态充能上限 |
| FieldTurnBattleSkillDynamicMaxCooltime setter | 0x3B11DF0 | 动态充能上限写入 |
| CalculatorActorStatusBase.CalculateAdvanceActiveSkillCooltime | 0x3244144 | 推进冷却（技能效果） |
| CalculatorActorStatusBase.CalculateShortenActiveSkillCooltime | 0x3244C7C | 缩短冷却 |
| CalculatorActorStatusBase.CalculateAttack | 0x32414E8 | 攻击技能入口 |
| CalculatorActorStatusBase.SequenceCalculateDamageValue | 0x3241BD4 | 逐段伤害计算 |
| CalculatorActorStatusBase.CalculateDamageMultiply | 0x3245190 | 伤害倍率类技能效果 |
| CalculatorActorStatusBase.CalculateHpRatioDamage | 0x324234C | HP 比例伤害 |
| ComputerTurnBattleSkillBehaviourAttackPower.OnCompute | 0x33675AC | 攻击力计算节点 |

### 4.4 COMBO / 伤害飘字 UI

| 函数 | RVA | 说明 |
|------|-----|------|
| FieldTurnBattleTeamComboDamageRatio getter / setter | 0x3B168F4 / 0x3B16868 | COMBO 伤害加成比例 |
| CalculatorTurnBattleCombo.AddComboCount | 0x2C880F4 | `void(this, team, add)` 累加 COMBO |
| CalculatorTurnBattleCombo.CalculateComboDamageCoefficient | 0x2C880BC | `int(this, count)` COMBO 加成系数(permil) |
| BattleDamageView.SetStandard | 0x314E6E0 | `void(damage, pos, crit, active)` 飘字(标准) |
| BattleDamageView.SetWeak | 0x314E804 | 飘字(弱点击破) |
| BattleDamageView.SetResist | 0x314E928 | 飘字(抗性) |
| BattleDamageView.SetRecovery | 0x314EA4C | 飘字(回复) |
| BattleDamageView.SetAbnormal | 0x314EC5C | 飘字(异常) |
| BattleDamageView.SetHpRatioDamage | 0x314EB68 | 飘字(HP 比例) |
| DamageLabelBase.SetEffectDamageText | 0x2F85BE4 | `void(damage)` 飘字文本最终落地 |

### 4.5 同伴研究（❌ 已弃用，仅留档）

| 函数 | RVA | 说明 |
|------|-----|------|
| CalculatorSkill.TryGetCompanionSkillCooltime | 0x2C8CFAC | `bool(party, out max, out cur)` 队伍级同伴冷却 |
| CalculatorSkill.HasUsableCompanionSkill | 0x2C8D350 | `bool(party)` 同伴技能可用性 |
| CalculatorSkill.HasUsableCompanionSkillMine | 0x2C8D2C8 | 玩家侧可用性（内部调前者） |
| CalculatorSkill.GetCompanionSkillSkillState | 0x2C8D48C | 同伴技能状态 |
| CalculatorSkill.GetAllCompanionSkillList | 0x2C8D7A4 | 队伍同伴技能列表 |
| FieldTurnBattleSkillSkillState getter / setter | 0x3B122FC / 0x3B12390 | 技能状态字段（灰/亮） |

---

## 5. 实测记录（logs/）

| 日志 | 内容 |
|------|------|
| `recon3.log` | 伤害管线全流程，src=2/3/4/5，unclamped→actual |
| `probe4.log` | 阵营判定（ownPid 44×0 / tgtPid 44×1；受击 11 次 pid0）；技能冷却充能序列 0→1→2…；技能归属 fromPid 0/1 |
| `mods.log` | v1 级联 bug 证据（atk ×2^8、def ÷2^8） |
| `mods2.log` | v2 修正后单点倍率（121→242→484），无级联 |
| `mods3.log` / `mods3b.log` | v3 = v2 + combo；实测确认 玩家 TeamId=1 / 敌方=2；combo-set 1→2→3→4 正常；reset-block 生效 |
| `mods3c.log` | v3.1（o1 缩放 + COMBO UI 强制） |
| `mods4.log` | v4 首测：幂等缩放成功无级联，HP 日志验证字段路径 ✅ |
| `mods4b.log` | v4 + config.json（×256 / ÷256，v1 等效），待复测 |

**用户游戏内反馈**：
- 13:5x（v3.1）：只有"技能无CD"明显可见；COMBO 非最大但持续长；伤害/防御不可见
- 14:0x（v3.1 后）：**COMBO 最大值已生效** ✅；倍率仍不可见 ❌
- 用户回忆 v1（字段路径）时：我方受击 0~15（防御÷256），对敌伤害极高（攻击×256）
  ⇒ 证实字段路径才是真实结算路径

---

## 6. 脚本清单（`mod-menu/scripts/`）

| 脚本 | 说明 |
|------|------|
| `recon.js/py` | 初次侦察：5 个伤害钩子 |
| `probe3.js/py` | 阵营 / 冷却探针 |
| `mods.js/py` | v1（有级联 bug，保留作记录） |
| `mods2.js/py` | v2（伤害管线单点倍率，正确） |
| `mods3.js/py` | v3.1（CalculateDamageValue 路径 + combo UI；倍率游戏内不可见） |
| `mods4.js/py` | v4（AttackDamage 字段幂等倍率 + HP 验证 + 全部功能） |
| `mods5.js` | v5 = v4 + 同伴验证日志 |
| `mods6.js` | v6 = v5 + 同伴冷却深挖（追踪/诊断） |
| `mods7.js` | v7 = v6 + 技能状态字段强制（自学习 READY_STATE） |
| `mods8.js` | v8 当前版（去除全部同伴功能；5 大功能定稿） |
| `auto_mods.py` | 守护进程（当前加载 mods8.js）：自动 attach / 断线重连 / frida-server 自启 |
| `config.json` | 可调配置（倍率/开关），启动时读取并注入脚本 |

启动方式：用 Python 以独立进程后台运行（命令路径按本机实际替换，详见 `archive/scripts/README.md`）。
说明：脚本会自动监测游戏进程，退出/重开后自动恢复；配置见 `archive/config/config.json`。

---

## 7. 已知坑与经验

1. **AttackDamage setter 级联**：不能在那里做倍率（指数叠加）。
   正确单点：`CalculateDamageValue`（输入/输出）。
2. **frida-server 会掉线**：重开命令见【1】；重启后需重新 attach。
3. **WSL 后台进程日志会卡死**：用 PowerShell Start-Process 从 Windows 侧启动。
4. **游戏重开/PID 变化**：脚本 attach 的 PID 失效，需重启脚本重挂。
5. **跳过/快速战斗不走客户端模拟**：抓不到战斗函数，必须手动战斗验证。
6. **COMBO 显示是事件驱动**：只改字段/访问器不改 UI 函数，界面不变。
7. 修改后先看日志 before/after 数值确认，再让用户体感确认。
8. 控制台出现 "检测到 localhost 代理配置..." 乱码：这是 **WSL 系统警告**
   （NAT 模式不支持 Windows localhost 代理，会话启动时输出），与本项目文件/日志无关。
   消除方法：`%UserProfile%\.wslconfig` 设置 `[wsl2] networkingMode=mirrored` 后
   `wsl --shutdown`（需重启 WSL，会短暂中断控制会话）；否则可忽略（仅控制台显示）。
   **2026-10-03 15:00 用户选择：忽略（B）。**

---

## 8. 待办清单

- [x] 倍率（×256 / ÷256）v4 验证生效 ✅，v8 定稿
- [x] 角色技能无CD ✅
- [x] COMBO 最大/不断 ✅
- [x] 同伴无CD：❌ 已取消（不做）
- [x] 全文件编码统一 UTF-8 BOM ✅
- [x] LGL Mod 菜单 v1.0 构建 + 注入 + 签名 ✅（见【10】）
- [ ] **装机实测**：安装 `output/nier-mod-menu-v1.0.apk`，验证悬浮菜单/倍率/无CD/COMBO
- [ ] 确认私服服务端是否校验战斗结果（客户端数值是否被接受）
- [ ] 后续：菜单美化 / 新功能扩展（速度、掉落等）
- [ ] 决定最终倍率/开关列表 → 设计 LGL 菜单 UI
- [ ] 移植 C++（Dobby inline hook，同一批 RVA）+ 独立 `libmodmenu.so`
- [ ] 打包 patched APK + 签名（v2/v3）+ 安装测试

## 9. Mod 菜单 UI 设计（规划）

| 功能 | 控件 | 范围 / 默认 | 说明 |
|------|------|-------------|------|
| 伤害倍率 `dmgMul` | 滑块 | 1 ~ 1000，默认 256 | 原攻击×伤害合并；代码内 clamp 10 亿防溢出 |
| 防御倍率 `defMul` | 滑块 | 1 ~ 1000，默认 256 | 1 = 关闭；受击 ÷ 该值（除法无溢出风险） |
| 角色技能无CD `skillNoCd` | 开关 | 开 | 三个角色技能充能恒满 |
| COMBO 最大/不断 `comboMax` | 开关 | 开 | 计数 100 + 不重置 + UI 显示 |

**上限与崩溃风险**：
- 游戏内"伤害上限"= 每击实际伤害被钳到目标剩余 HP（实测 336→0、217→158），
  超额部分不生效、也不会崩（敌人 HP 不会为负）。
- 真正的风险是 **int32 溢出**（> 2,147,483,647）：基础伤害 × 过大倍率会溢出成负数
  （表现为给敌人回血/异常）；Frida 写的是 32 位寄存器，超界会截断。
- 已加防护：伤害结果统一 `clamp 到 1,000,000,000`；建议滑块上限 1000（×256 已足够秒杀）。
- 防御是除法，只会把伤害变小（最低 0），无溢出/崩溃风险。

## 10. Mod 菜单构建与注入（v1.0 已产出）

### 10.1 工程与改造点（LGL 4.0 模板 → 我们的菜单）
| 文件 | 改动 |
|------|------|
| `jni/Main.cpp` | 全部重写：4 个功能列表 + Changes + C++ 钩子移植（幂等历史/阵营判定/COMBO） |
| `jni/Menu/Setup.cpp` | 标题/副标题/Toast 改为 NieR Lunar-Tear Mod Menu |
| `java/.../Main.java` | `System.loadLibrary("niermenu")` |
| `jni/Android.mk` | `LOCAL_MODULE := niermenu` |
| `jni/Application.mk` | `APP_ABI := arm64-v8a`（游戏仅 arm64） |
| `app/build.gradle` | `abiFilters 'arm64-v8a'` |
| `java/.../Menu.java` | SeekBar 默认值 min → max（默认 333） |

C++ 钩子（与 Frida v8 一一对应）：
- `0x3B0C980` AtkDamageSetter → 伤害倍率 × / 防御倍率 ÷（幂等历史 250ms/20 值, clamp 10 亿）
- `0x3B11F10` CurCoolSet → 角色技能充能强制 max
- COMBO: `0x3B166CC`/`0x3B16760`（计数）、`0x2C881F8`（当前）、`0x2C8818C`（重置跳过）、
  `0x3149B94`/`0x314A764`（UI 显示 100）
- 辅助函数指针: JoinParty `0x3E6E3CC`、FromActor `0x3B119BC`、TargetActor `0x3B0CD6C`、
  TeamId `0x3B162A0`、MaxCool `0x3B11D5C`

### 10.2 构建流程（可复现）
```
1. gradle 构建菜单 APK:
   <仓库根>\build\gradle_build.bat（旧工作区脚本；现已被一键脚本 build_patched 取代，见 docs/一键构建说明.md）
   (Gradle 8.7 + JDK17 + NDK 26.1.10909125, assembleDebug)
   → build/Android-Mod-Menu-4.0/app/build/outputs/apk/debug/app-debug.apk

2. apktool 解包菜单 APK → 取 smali + libniermenu.so

3. 注入游戏解包目录 patched/:
   - smali_classes3/com/android/support/*.smali   (44 个文件)
   - lib/arm64-v8a/libniermenu.so
   - AndroidManifest.xml: +SYSTEM_ALERT_WINDOW 权限 + Launcher service
   - MessagingUnityPlayerActivity.smali onCreate 注入:
     invoke-static {p0}, Lcom/android/support/Main;->Start(Landroid/content/Context;)V

4. 重建: java -jar apktool.jar b patched -o niermenu-unsigned.apk

5. 对齐+签名:
   zipalign -p -f 4 unsigned.apk aligned.apk
   apksigner sign --ks output/nier.keystore --ks-pass pass:nier123456 --out nier-mod-menu-v1.0.apk aligned.apk
   (密钥 alias=nier, 密码 nier123456)
```

### 10.3 产物（output/）
| 文件 | 说明 |
|------|------|
| `nier-mod-menu-v1.0.apk` | 266,924,577 B，已签名（v1+v2+v3）+ zipalign |
| `nier-mod-menu-v1.0.apk.idsig` | v4 签名文件（可选） |
| `nier.keystore` | 签名密钥（alias nier / 密码 nier123456） |
| `操作指南.md` | 安装/使用/排障指南（UTF-8 BOM） |

### 10.4 待实测项目
- [ ] 装机（先卸载旧版）：悬浮图标出现 + 权限流程
- [ ] 伤害倍率/防御倍率生效（对照 Frida 日志数值）
- [ ] 角色技能无CD（连放 3 个技能）
- [ ] COMBO 显示 100 且不断
- [ ] 菜单设置-保存偏好（重启游戏后保留）

## 11. v1.0.1 修复与线上排查（2026-10-03 15:4x）

### 11.1 用户报告 bug
"滑块值为 1 时，打出/受到的伤害仍不是正常值；游戏伤害上限是 15 亿"

### 11.2 排查过程（手机在线，直接用 adb + logcat）
1. 给 Main.cpp 的 `Changes()` 增加日志（featNum/value），伤害钩子增加修改日志（前 60 次）
2. 重建 v1.0.1（gradle → apktool 注入 → apktool b → zipalign → 签名）
3. `adb install` 安装、`appops` 授权悬浮窗、启动游戏、抓 `logcat -s Mod_Menu`
4. 日志证明 **滑块回调完全正常**：`Changes[1] dmgMul=288…54,29,6,1`、`Changes[2] defMul=…,1`
5. **根因：电脑上的 Frida 采集器 (auto_mods.py, config dmgMul=256/defMul=256) 仍在运行并自动 attach 游戏进程**
   —— 两个 mod 叠加：LGL 滑块=1，但 Frida 仍在 ×256 / ÷256
   ⇒ "滑块无效" 假象。停止采集器后仅 LGL 生效。

### 11.3 v1.0.1 改动
| 改动 | 说明 |
|------|------|
| 伤害 clamp | 1,000,000,000 → **1,500,000,000**（与游戏上限 15 亿一致） |
| 滑块默认标签 | 未保存偏好时显示 max（333）而不是 min（误导） |
| 诊断日志 | Changes 全量 + 前 60 次伤害修改（`adb logcat -s Mod_Menu`） |

### 11.4 教训（写入规则）
- **测试内置 Mod 菜单时，必须停掉 Frida 采集器**（两个 mod 会叠加）
- 现场排查三件套：logcat + appops 授权 + adb install；改动量小时（仅 .so）无需重新注入 smali

## 12. 原版 APK 注入 + 流程标准化（2026-10-03 16:0x）

### 12.1 原版 vs patched 的 libil2cpp.so 对比（关键结论）
- 原版 `NieR Re[in]carnation 3.7.1_EN.apk` 的 libil2cpp.so:
  size 与 patched 完全相同 (127,359,872)，md5 不同 (0f9ffe… vs 39eb29…)
- 逐 4KB 块对比：31094 块中仅 **11 块不同（≈45KB）**，为私服补丁的网络/校验改动
- **全部 14 个钩子点的前 16 字节完全一致** ⇒ 同一套菜单与偏移通用于原版与私服版

### 12.2 标准化注入脚本 tools/inject_modmenu.py
一键完成: apktool d → 复制 smali+so → 清单权限/service → 启动 Activity 注入
→ apktool b → zipalign → apksigner 签名 + 校验
- 自动识别 Launcher Activity 与其 smali
- 幂等: 已注入过的内容会跳过
- `--reuse` 复用解码目录，加速重复注入
- 原版注入产物: `output/nier-mod-menu-original.apk`

### 12.3 新增文档
| 文件 | 内容 |
|------|------|
| `output/制作流程标准化.md` | 三步流程、环境、升级改偏移方法、FAQ |
| `output/美化指南.md` | 标题/图标/颜色/尺寸/排版/设置页的美化点与示例 |

### 12.4 Q&A：菜单 APK 能否用于打 lunar-tear 私服补丁？
可以。菜单注入与私服补丁作用于不同代码区域（实测钩子点与补丁区域不重叠），
对菜单 APK 执行同样的私服补丁步骤即可；先打补丁后注入菜单同样可行。
注意最终签名（任一顺序都需要重签名）。

## 13. 中文注释版模板 Android-Mod-Menu-cn-4.0（2026-10-03 16:1x）

### 13.1 内容
- 基于原始 `Android-Mod-Menu-4.0.zip`，核心文件注释全部中文化：
  - 全文中文化（重写）: `Main.cpp`（示例功能+教学注释）、`Setup.cpp`、`Jni.cpp`、
    `Menu.hpp/Jni.hpp`、`Main.java`、`MainActivity.java`、`Launcher.java`、
    `CrashHandler.java`、`Android.mk`、`Application.mk`
  - 横幅+关键注释中文化: `Menu.java`、`Preferences.java`、`Menu.cpp`
    （由 `tools/cn_localize.py` 批量精确替换，29 处）
  - Gradle 文件: `build.gradle` / `app/build.gradle` / `settings.gradle` / `gradle.properties`
  - 第三方库（KittyMemory/Substrate/And64InlineHook/Includes）保留原注释（作者版权）
- 新增 `README_CN.md`：三步上手、功能列表语法表、MOD 编写流程、FAQ
- **补全了原 zip 缺失的 `gradle/wrapper/gradle-wrapper.jar`**（用本地 Gradle 8.7 生成）
- 已验证可编译：`assembleDebug` BUILD SUCCESSFUL（app-debug.apk 448KB）

### 13.2 产物
- `output/Android-Mod-Menu-cn-4.0.zip`（18.4 MB / 213 个文件，已排除构建产物与本地配置）
- 本地化脚本: `tools/cn_localize.py`（可重复执行，幂等）

### 13.3 注意
- 中文版模板仍使用原版示例功能（无敌/分数/金币）作为教学；
  NiER 专用工程在 `build/Android-Mod-Menu-4.0/`（含本游戏全部钩子与偏移）

## 14. 一键构建系统（2026-10-04）

### 14.1 设计
两个入口替代手工流程（改完 modmenu/ 直接跑）：
- ~~`build_original.bat` / `.sh` → 原版 APK + 菜单~~（已移除：只支持「先打私服补丁 → 再注入菜单」）
- `build_patched.bat` / `.sh` → 私服补丁版 + 菜单

内部由 4 个 Python 协作：
`build_all.py`（总流程）→ `build_menu.py`（Gradle 编译 + apktool 提取）
→ `inject_modmenu.py`（解包缓存/注入/重建/签名/校验/安装）+ `_common.py`（配置/探测/交互/日志）

### 14.2 特性
- **零输入日常使用**：工具自动探测（java / build-tools / apktool 常见位置）、
  输入 APK 读 `tools/targets.json` 或自动扫描 `../resources/`、输出自动命名到 `dist/`
- **交互问答（回车=推荐值）**：是否跳过编译、是否复用解包缓存、输出 tag、是否装机
- **无人值守**：`--yes` / `--no-input`；另有 `--no-build`、`--menu-apk`、`--fresh`（脚本只编辑/导出 APK，不做安装）
- **解包缓存**：按 目标 APK 路径+大小+mtime 指纹复用（省约 3 分钟）
- **幂等注入**：smali/so/清单/启动 Activity 重复执行安全
- **日志留档**：`build/logs/<时间戳>-<目标>.log`；成品在 `dist/`（已 gitignore）
- 补齐了 `modmenu/gradle/wrapper/gradle-wrapper.jar`（此前缺失，一键脚本依赖它）

### 14.3 实测（原版端到端）
命令：`bash build.sh --yes --no-input --tag e2e`
结果：**约 6 分钟** 完成 → `dist/nier-mod-menu-original-e2e.apk`（253.1 MB）
- 自动探测到 build-tools **37.0.0**；菜单编译+提取 ~40s；解包 250MB APK 约 1 分钟；
  `apktool b` 约 4 分 40 秒；对齐+签名+校验约 13 秒
- 产物校验：`classes3.dex` 含菜单类、`lib/arm64-v8a/libniermenu.so` 就位、`apksigner verify` 通过
- SHA256: `a03cc2fa19d89a0ac6d3db8fb6f1f427647e8ad2744911e0b2a4dbc0e3846e26`

---

## 服务器热切换（connect 层实现，EN/JP 各自独立）

| 项 | 说明 |
|---|---|
| 挂钩点 | **libc `connect()`**（`dlsym(RTLD_DEFAULT,"connect")` + `A64HookFunction`） |
| 改写规则 | 目标端口 ∈ {8003, 8080, 80} 时替换目标 IP；条目带端口则同时改端口（如 `example.com:80`） |
| 端口过滤 | 只碰这三个端口，443/其它端口完全不动（不影响 Unity/Firebase 等） |
| 域名支持 | `inet_pton` 判 IP，否则 `getaddrinfo(AF_INET)` 解析；缓存 60s，失败会重解析 |
| 失败回退 | `connect` 失败累计 2 次 → 切下一条（地址簿 ≥2 条且开关开启） |
| 持久化 | `<files>/modmenu_servers.txt`（应用私有目录；路径由 `Init` 里 `Context.getFilesDir()` 取得） |
| 启动应用 | 载入时若 `remember=1 && enabled=1` 自动应用（对应「记住上次选择」） |
| 与打包补丁关系 | 打包期补丁改 APK 内地址；本功能只在运行期改写连接目标，互不冲突 |
| auth/引継ぎ（3000） | **已支持**（2026-10-13）：走 `<files>/auth_host.txt` + 注入的 `com/niersp/AuthHost`（WebView 可能不在本进程，connect 钩子覆盖不到；见 [`EN-auth动态化说明.md`](EN-auth动态化说明.md)） |
| 不在范围 | TLS（沿用私服补丁 SSL bypass） |

菜单控件：`7 InputText` / `8 保存` / `9 临时应用` / `10 Spinner（地址簿）` / `11 应用选中` / `12 删除选中` / `13 停止` / `14 失败自动切换` / `15 记住上次选择` / `16 状态显示`。

> 2026-10-14 修复：地址簿条目减少（如删除地址）后，Spinner 仍按旧索引恢复选中
> → `ArrayAdapter.getItem` 越界，Spinner 布局时崩掉整个游戏。已把保存的选中索引
> clamp 到 `[0, size-1]`，并给 `getChildAt(0)` 加了类型保护（EN/JP 两份 `Menu.java` 同步）。

---

## 非 root / Android 15 兼容修复（2026-10-11）

### 问题
在非 root 手机上运行时，6 个战斗功能（伤害/防御/无CD/God/强命/上限）**全部失效**，
而服务器热切换（挂 libc `connect`）正常。

### 根因（回归）
`findLibrary()` 取 `/proc/self/maps` 里**第一条**匹配行。Android 10+ 同一个 .so 会被映射两份：
```
r-- 数据视图（地址通常更小，旧实现取到它）→ 所有 hook/补丁写到无效页，且不报错
r-x 代码视图（真正执行的那份）
```
任何依赖 libil2cpp 基址的功能都会随"映射顺序"时好时坏 —— root 机上恰好顺序对，非 root 机就全失效。
（该修复曾在 `8bc2da8` 存在，仓库重构时被误删）

### 修复
| 项 | 内容 |
|---|---|
| P0 基址解析 | 改用 **`dl_iterate_phdr()`**（linker 权威基址，与 maps 顺序无关）；回退顺序：`maps(r-x)` → `maps(off0)` → `maps(first)`；来源写入菜单"自检基址" |
| P1 挂钩可靠性 | 装钩前记录原字节 → 装完立即校验 → 失败重试；**看门狗每 2 秒复查 6 个挂钩点 + 上限补丁**，丢失自动重装；日志 `[hook] xxx OK/FAIL`、`[hook] summary`、`[watch] lost -> reinstall` |
| A 修复 | `hack_thread` 等 libil2cpp 就绪后调用 `isLibraryLoaded()` 置位 `libLoaded` |
| B 修复 | `isGameLibLoaded()` 变实时（未置位时兜底查一次 maps） |
| C 改进 | 「保存偏好等待提示」改中文 + 前 ~10 秒静默重试（正常 1 秒内就通过，不再每次开菜单弹提示） |
| 自检行 | 菜单新增 `自检基址: linker` / `自检挂钩: 6/6 上限ON` 两行 + 「刷新自检」按钮（排障一眼可见） |

### 非 root 真机验证（OPPO PKR110 · Android 15）
```
自检基址: linker       ← dl_iterate_phdr 生效
自检挂钩: 6/6 上限ON    ← 6 个挂钩全部装进代码段
菜单打开即列出功能，无等待提示
```
> 结论：Android 15 非 root 设备上 A64InlineHook 工作正常，**不需要**改用"静态跳转"方案。
