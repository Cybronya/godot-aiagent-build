# End-to-End Generation Suite（Phase 1.9）

跨工具链的集成测试目录。**不是** Tool（没有 TOOL.md，不暴露 CLI），
只提供「整条生成链路是否真的串起来」的可重复证据。

## Phase 1.16：实体作用域绑定接入主生成链路

主链路（C→D→E 段）的显式绑定现在携带**实体身份**：

```
feature_discovery（payload.role）
  + gameplay 蓝图实体清单 → discovery_to_binding --resolve-entity-from
  → {entity, role, asset} 覆盖 → bind_assets --gameplay --binding（作用域路由）
  → scene_composer --bindings（绑定节点/资源路径落盘进生成的 .tscn）
  → 真实 Godot headless（G8/G9/G10a 行为探针）
```

覆盖（任务书场景 1–6）：

| 断言 | 场景 |
| --- | --- |
| C2a/C3：role 恰好对应一个实体 → 覆盖条目带 `{entity, role, asset}` | 身份可追溯 |
| C3b：缺省（无实体 flag）输出保持 `{role, asset}` | 场景 4 单实体旧格式兼容 |
| C6：角色零匹配 `no_entity_with_role` / 多匹配 `ambiguous_entity_role`（exit 1，含候选 id） | 场景 6 发现信息不足 |
| D3/D6/D6b：目标实体选中槽位 `resolved_from=binding` + entity-scoped 来源；另一实体零泄漏 | 场景 1 不互相覆盖 |
| D7：先跑无绑定推断，再用指向不同资源的实体作用域绑定 → 显式资源获胜 | 场景 2 显式 vs 推断 |
| D8：未知实体作用域 → exit 1 + `binding_scope_errors` 可定位，不伪造成功 | 场景 3 |
| I1/I1b：主链路玩家实体不受敌方作用域影响（idle 仍 index 推断） | 场景 1 终态 |
| I2：旧式 role-level 覆盖仍按既有契约工作，跨实体歧义由 compatibility 门禁标记 INCOMPATIBLE | 场景 5 |

## 为什么单独放一层

`.ai/tools/**/tests/` 是各工具自身的单元 / 契约测试（单模块边界）。
本目录测试的是**工具之间**的连接：一个阶段的产物是否满足下一阶段的 Schema、
下一个阶段是否真的被调用、失败时是否有可诊断输出。放在任一工具目录下都会
使「被测对象」与「测试归属」错位，因此独立成层。

## 当前套件

### `behavior_probe.py`（生成场景的真实玩法行为探针，Phase 1.10 / 1.11）

对**生成链路产出的实体场景**在真实 Godot 中执行玩法行为断言：观察的是运行时
状态变化（实体根位移 / 子节点是否自行移动 / 玩家生命值），不是节点、信号或脚本是否存在。

```bash
python .ai/tools/e2e/behavior_probe.py res://Scenes/E2eProbeEnemy.tscn
python .ai/tools/e2e/behavior_probe.py res://Scenes/SlimeEnemy.tscn --show-output
# 受控负向：去掉接触形状的变异体（接触下不应产生伤害）
python .ai/tools/e2e/behavior_probe.py res://Scenes/E2eProbeNoContact.tscn --expect none
# 退出码: 0 = 行为断言通过；1 = 断言失败（含前置条件不成立）；2 = 输入/环境错误
```

主行为 = 「敌人**实体根**追踪目标并实际移动 + 与玩家真实接触后按既有机制结算伤害」。
目标默认用项目真实玩家实体场景（`res://Features/player_movement/Player.tscn`，含
CharacterBody2D 碰撞 + Health），并按游戏约定加入 `players` 组（SurvivalArena 对
Player 实例所做的同一件事），不构造与游戏无关的人造探针。

断言与判定条件（模拟参数：初始距离 400 px、`speed=80`、物理帧 60 Hz、接触观察 90 帧）：

| 断言 | 判定 | 诊断输出 |
| --- | --- | --- |
| 前置条件：场景中存在追击组件 | 递归找到 `ChaseMovement`（根或子节点均可） | `FAIL: Precondition: ... 不存在 ChaseMovement 组件` |
| 前置条件：目标侧有 Health / 场景有 ContactDamage | 组 + `"Health"` 命名约定（`damage` 期望下必需） | `FAIL: Precondition: ... 缺少 Health 组件` |
| 前置条件：初始距离可观察 | 初始距离 ≥ 2×最小接近量（60 px） | `FAIL: Precondition: 初始距离 ... 过小` |
| 基线：未配置目标时静止 | 20 帧位移 ≤ 1.0 px（保证断言非恒真） | `baseline_drift=...` |
| 主行为 A：**实体根**接近目标 | 90 帧（≈1.5 s）内根节点位移 ≥ 30 px（理论 120 px） | `BEHAVIOR: ... root_approach=...` |
| 主行为 B：位移不是子节点自己跑 | 根的直接子节点本地位置漂移 ≤ 1.0 px | `child_max_drift=...` |
| 无接触不受伤 | 目标 400 px 远时生命值不变 | `no_contact_damage=0` |
| 接触伤害按既有机制结算 | 接触 90 帧内伤害 ≥ 1 点，且不超过 `ceil(窗口/tick_interval)+1` 拍的节拍上限 | `BEHAVIOR_CONTACT: ... damage_total=... damage_ceiling=...` |
| 目标释放后停止 | 再 20 帧位移 ≤ 1.0 px | `BEHAVIOR_STOP: post_free_drift=...` |

`--expect none` 用于**受控负向**：同一物理配置下（接触间距与正常场景一致、实体根同样移动），
若场景没有碰撞形状（去掉 ContactShape 的变异体），伤害必须是 0；同一变异体在
`--expect damage` 下必须失败 —— 证明「接触伤害」断言依赖真实碰撞，而不是恒真。

任一项失败 → `printerr("FAIL: ...")` + `quit(1)`（非零退出码），并带上实际数值。
调用方（Python）除退出码外还独立解析 `BEHAVIOR:` 行断言，避免「测试自己说了算」。

机制：渲染一段临时 GDScript 到 `Tests/e2e_behavior_probe.gd` → 用项目 Godot 以
`-s res://Tests/e2e_behavior_probe.gd` 运行 → 无论成败都在 `finally` 中删除。
**刻意不用 `test_` 前缀**：即使清理失败，统一运行器的 `Tests/test_*.gd` 发现规则
也不会把临时脚本当成长期套件执行。

### `death_victory_probe.py`（死亡与胜利闭环探针，Phase 1.12）

把**生成链路产出的实体场景**放进**项目真实游戏场景** `res://Scenes/TimedCombatArena.tscn`
（该场景承载既有胜负逻辑：全部必需敌人死亡 → 场景自身打开出口门 → 玩家进出口区 → 完成），
伤害只走**真实玩家攻击输入路径**（空格攻击 → `AttackTrigger` → `Health.take_damage`），
断言的是运行时状态：生命值 / 死亡事件次数 / 存活计数 / 出口门 / 胜负状态。

```bash
python .ai/tools/e2e/death_victory_probe.py res://Scenes/E2eProbeEnemy.tscn
python .ai/tools/e2e/death_victory_probe.py res://Scenes/Enemy.tscn        # 手写实体等价性
python .ai/tools/e2e/death_victory_probe.py <不死变异体> --expect survive  # 受控负向
# 退出码: 0 = 断言通过；1 = 断言失败（含前置条件不成立）；2 = 输入/环境错误
```

被测对象的**管理接口**（竞技场敌人生成链路的要求）：实体根可接收 `target_path`
（Phase 1.11：实体根即 motion 组件）、子节点含 `Health`（命名约定）。
宿主场景的 `AttackTrigger` 必须配置 `target_group`（否则空格攻击解析不到目标）。

断言与判定条件（模拟参数：物理帧 60 Hz、单波 2 个必需敌人、攻击预算 12 次）：

| 断言 | 判定 | 诊断输出 |
| --- | --- | --- |
| 前置条件：竞技场把被测实体纳入敌人管理链路 | 生成数量 / `alive_count` 一致、实体根有 `target_path` | `FAIL: Precondition: ...` |
| 前置条件：真实攻击路径可用 | `AttackTrigger.target_group` 非空、`damage` 为正且小于目标 `max_health` | `FAIL: Precondition: AttackTrigger 未配置 target_group ...` |
| N1：未致死伤害 | 生命值下降但不死亡，存活计数 / 出口门 / 状态均不变 | `hp_before=... hp_after_first=...` |
| D1：生命值归零 | 攻击预算内 `Health.died` 触发，死亡时生命值为 0 | `DEATH: ... hp_after_kill=...` |
| D2：死亡传播 | `died` 恰好一次、存活计数恰好减一、HUD 同步、实体按既有规则退出战斗 | `died_events=... alive_after_death=... removed=...` |
| N2：重复处理 | 死亡后继续攻击 / 再次 `take_damage` 不产生第二次 `died`、不重复计数 | `alive_after_extra=...` |
| V2：不提前胜利 | 仍有必需敌人存活时出口门关闭、状态保持 Playing | `door_open_with_survivor=0` |
| V1：胜利条件 | 最后一个必需敌人死亡后出口门由场景逻辑打开；玩家真实输入走进出口区 → `Completed` + `arena_finished` 一次 | `VICTORY: ... state_after_exit=1 finish_events=1` |

`--expect survive` 用于**受控负向**：同一场景把敌人 `Health.max_health` 抬到攻击预算之上
（其余逐字保留）后，探针必须观察到「敌人仍存活、计数不变、门始终关闭、状态始终 Playing、
无 `arena_finished` 事件」；同一变异体在默认期望下必须失败 —— 证明 V1 依赖真实死亡。

任一项失败 → `printerr("FAIL: ...")` + `quit(1)`，并带上实际数值；调用方（Python）
除退出码外还独立解析 `DEATH:` / `VICTORY:` 行断言。机制与行为探针同构：渲染临时
GDScript 到 `Tests/e2e_death_victory_probe.gd`（**不带 `test_` 前缀**）并在 `finally` 删除。

### `level_orchestration_probe.py`（生成关卡配置的运行时消费探针，Phase 1.13）

把 `gameplay_planner/level_planner.py` 生成的 `Levels/<level_id>.json` 放进项目真实游戏场景
`res://Scenes/TimedCombatArena.tscn`，验证**配置真的驱动了关卡行为**（观测运行时状态：
生成数量 / 波次推进 / 出口门 / 胜负状态 / 胜负事件次数），而不是「配置文件能否被解析」。

```bash
python .ai/tools/e2e/level_orchestration_probe.py res://Levels/E2eProbeLevel.json \
    --focus-scene res://Scenes/E2eProbeEnemy.tscn
python .ai/tools/e2e/level_orchestration_probe.py <无效配置> --expect invalid
# 退出码: 0 = 断言通过；1 = 断言失败（含前置条件不成立）；2 = 输入/环境错误
```

期望数量由 Python 侧从**同一份配置**独立解析后传给探针（L7 的证据来源），因此断言不是
「探针自己说了算」。`--focus-scene` 用于单独统计某个生成物（通常是 Scene Composer 的生成
场景）实际被生成的次数，以证明跑的确实是生成物。

| 断言 | 判定 | 诊断输出 |
| --- | --- | --- |
| L7 生成数量来自配置 | 运行时波数 / 首波数量 = Python 从配置解析的值 | `LEVEL: ... wave1_count=... spawned_wave1=...` |
| L8 生成物来源与接口 | 每个生成敌人的 `scene_file_path` ∈ 配置声明的场景集合；`Health` + `target_path` 齐备 | `entity_scene_match=...` / `focus_hits=...` |
| L9 未清波不提前生成 | 首波仍有存活时不进入下一波 | `index_after_wave1=...` |
| L10 清波后按配置生成 | 首波清空 → 第二波数量 = 配置值，且只推进一次 | `wave2_count=... alive_after_wave1=...` |
| L11 出口锁定 | 仍有必需敌人存活时出口门关闭 | `door_open_with_survivor=0` |
| L12 清场开启出口 | 全部必需波次清空后出口开启（状态仍 Playing） | `door_open_after_all=1` |
| L13 / L14 完成与胜负一次 | 玩家真实输入走进出口区 → Completed，`arena_finished` 恰好一次 | `state_after_exit=1 finish_events=1` |
| Q 受控负向 | 无效配置（count=0）被运行时拒绝：零生成 + `state=Failed` + 可定位诊断 | `--expect invalid` |

首波首个敌人用**真实攻击输入路径**击杀（其余用既有伤害接口）以保持运行时间可控；
机制与其它探针同构：临时 GDScript `Tests/e2e_level_orchestration_probe.gd`
（**不带 `test_` 前缀**）→ 项目真实 Godot `-s` 运行 → 解析 `LEVEL:` 机读行 → `finally` 删除。

### Phase 1.14：通用关卡编排与第二个接入场景（不新增探针，证据归位于运行时测试）

Phase 1.14 把关卡编排从 `TimedCombatArena` 专属实现整理为场景无关的通用管线
（`Orchestration/level_orchestrator.gd` + `Orchestration/level_config.gd`），并用**同一套实现**
接入第二个场景 `SurvivalArena`（holdout 生存模式，`Levels/survival_arena.json` 驱动）。
本目录**不新增 holdout 探针**：holdout 配置不经生成链产出（`level_planner` 产 waves / boss
配置，不产 holdout，见 `level_schema.yaml` 的 `generator_scope`），为其单建探针只会复制既有证据。

两个场景的真实 Godot 运行证据归位于：

- `Tests/test_generic_level_orchestration.gd`（G1–G13，统一入口自动发现）：
  G1 合成宿主（非任何 `.tscn`）驱动完整波次→出口→胜利；G2 发布场景 + 发布配置的
  Phase 1.13 行为清单；G3/G4 SurvivalArena 复用同一编排脚本（holdout）且生成节奏 /
  精英延迟 / 存活上限 / 生存胜利 / 玩家失败 / 拾取物与陷阱不回归；G5–G9 波次与出口门控、
  死亡幂等、胜负一次；G10 无效配置拒绝（waves 与 holdout 两类规则集）；G11 旧场景兼容
  （手写 waves / 遗留导出 / v1 配置 / 缺省选填块）；G13 诊断定位到配置文件、字段、消费场景与阶段。
- `Tests/test_level_orchestration.gd`（Phase 1.13 L7–L15）与
  `Tests/test_timed_combat_arena.gd`（既有集成断言）继续作为迁移后行为不回归的证据。
- `gameplay_planner/tests/test_level_planner.py`（L1–L8）：waves/holdout 校验 +
  版本兼容 + 生成器 + CLI。

### `boss_level_probe.py`（Boss 生成链路的运行时探针，Phase 1.20）

把 `level_planner.py --mode boss --plan <自动计划>` 生成的关卡配置交给
`Orchestration/level_host.gd`（通用宿主适配器），在**真实组合宿主**
（`scene_composer --compose-plan` 产物）上验证：

```bash
python .ai/tools/e2e/boss_level_probe.py res://Levels/<id>.json \
    --bad-config res://Levels/<id>_bad.json
# 退出码: 0 = 断言通过；1 = 断言失败；2 = 输入/环境错误
```

| 断言 | 判定 | 诊断输出 |
| --- | --- | --- |
| Boss 身份 | `boss.instance` 解析到的节点就是编排器绑定的 Boss；mode=boss | `boss_alias=1 config_errors=0` |
| 存活不胜利 | Boss 受伤未死 → 状态仍 Playing，零完成事件 | `state_after_partial=0 finish_before_kill=0` |
| 死亡一次完成 | Boss 死亡 → Completed、`boss_defeated` 与 `finished(true)` 各一次 | `boss_events=1 finish_after_kill=1` |
| 重复死亡幂等 | 重复 `died.emit()` 不重复开门/完成 | `events_after_duplicate=1 finish_after_duplicate=1` |
| 玩家失败 | 玩家死亡 → Failed + `finished(false)` 一次 | 探针内部断言 |
| 宿主不匹配 | 静态合法但 `boss.instance` 不存在 → `boss.instance` 诊断 + Failed + 零完成事件 | `bad_setup_errors>=1 bad_state=2` |

机制同其它探针：临时 GDScript `Tests/e2e_boss_level_probe.gd`（**不带 `test_` 前缀**）
→ 真实 Godot `-s` → 解析 `BOSS:` 机读行 → `finally` 删除；超时会如实报告，
不会伪装 PASS。

### `multi_stage_boss_probe.py`（多阶段 Boss 生成链路的运行时探针，Phase 1.21）

把 `level_planner.py --mode boss --stage clear:<entity>:<n> --stage boss` 生成的
多阶段配置交给 `LevelHost`，在真实组合宿主上验证：

```bash
python .ai/tools/e2e/multi_stage_boss_probe.py res://Levels/<id>.json
# 退出码: 0 = 断言通过；1 = 断言失败；2 = 输入/环境错误
```

| 断言 | 判定 | 诊断输出 |
| --- | --- | --- |
| 初始阶段 | 从 clear_enemies 开始，生成配置声明的敌人数 | `stage0=0 alive_after_start=2` |
| 清理未完成 | 击杀部分敌人不推进阶段、不胜利 | `stage_after_one=0` |
| 清理完成 | 全部清除后只激活一次 Boss 阶段 | `stage_after_clear=1 stage_started=2 stage_completed=1` |
| Boss 存活 | 受伤未死 → Playing，零完成事件 | `finish_before_boss=0` |
| Boss 死亡 | 完成一次，阶段历史 `clear_1, boss` | `boss_events=1 state_after_boss=1 finish_after_boss=1 history_len=2` |
| 重复死亡 | 不重复结算 / 不重复完成 | `duplicate_events=1 duplicate_finish=1` |
| 玩家死亡 | 清理阶段玩家死亡 → Failed + `finished(false)` 一次，阶段不推进 | `player_state=2 player_finish_false=1 player_stage=0` |

机制同其它探针：临时 GDScript `Tests/e2e_multi_stage_boss_probe.gd`（**不带 `test_` 前缀**）
→ 真实 Godot `-s` → 解析 `STAGE:` 机读行 → `finally` 删除。

Phase 1.22 起同一探针在 Boss 死亡结算后，把**真实运行**的结构化诊断事件 trace
导出到 `Tests/e2e_multi_stage_boss_trace.json`（`OrchestrationTrace` 纯数据 JSON），
由 `validator/trace_replay.py` 独立回放（E2E P14–P18：状态一致 / 确定性 / 去掉终结
事件后为 playing / 临时文件清理）；CLI 缺省在报告后删除 trace，`--keep-trace` 保留。

### Phase 1.15：跨层契约一致性与统一 Validator（证据归位于工具层测试目录）

跨层一致性测试不在本目录（它们不测生成链路，测的是**同一契约在多层的判定一致性**）：

- `validator/tests/test_cross_layer_contract.py`（C1–C9）：共享正反例关卡配置同时经过
  Python `validate_level` 与 Godot `LevelConfig`（真实 headless 探针）逐例比较判定与
  错误字段路径；C9 断言 Godot 编排层不消费资源绑定（作用域权威 = bind_assets.py）。
- `validator/tests/test_unified_validator.py`（C10）：统一 Validator 汇总、稳定错误代码、
  Runtime 不可用（Godot 缺失）如实报告为 UNAVAILABLE/INCOMPLETE。
- `asset_registry/tests/test_binding_scope.py`（I1-A…I1-G）：显式绑定 entity 作用域
  （Phase 1.15）：单实体兼容 / 作用域路由 / 多实体角色级绑定按既有规则处理且可见 /
  未知实体可定位失败 / 类型门禁不回退 / 既有工作流不回归 / 错误不静默。

### `tests/test_end_to_end_generation.py`

用真实 CLI（子进程，不 mock）跑目标链路：

```text
自然语言需求
  → Gameplay Blueprint            planner.py
  → 每实体 Entity Blueprint       planner.py --emit-entities
  → Feature Discovery             feature_registry/feature_discovery.py --json
  → 显式候选选择                  feature_registry/discovery_to_binding.py --select
  → Resource Binding              asset_registry/bind_assets.py --gameplay --binding
  → Scene Intent / 场景生成       scene_composer/scene_composer.py
  → 静态验证                      validator/check_scene_composition.py
                                  validator/check_gameplay.py
  → 真实 Godot 运行时             runtime/run_scene.py + 生成的场景回归测试
  → 真实玩法行为断言              e2e/behavior_probe.py（实体根实际接近目标 + 接触伤害结算）
  → 真实死亡与胜利闭环断言        e2e/death_victory_probe.py（真实攻击输入击杀生成实体
                                  → 死亡事件 → 击杀计数 → 胜负状态）
  → 关卡编排生成与运行时消费      gameplay_planner/level_planner.py（生成 config）
                                  + e2e/level_orchestration_probe.py（配置驱动波次/出口/胜利）
  → Boss 编排（Phase 1.20）        composition_plan → --compose-plan 宿主
                                  + level_planner --mode boss → e2e/boss_level_probe.py
  → 多阶段 Boss（Phase 1.21）      composition_plan → --compose-plan 三实例宿主
                                  + level_planner --mode boss --stage ...
                                  + check_level --plan → e2e/multi_stage_boss_probe.py
```

覆盖 A～K 段：正向链路（A–G，含结构语义断言 G6b–G6d 与玩法行为断言 G10a–G10h）、
负向用例（H：未知 Feature 零产物、显式绑定指向不存在资源时报缺失而不编造；
G11：缺少行为的生成场景必须让行为探针失败退出非零；
G12：去掉接触形状的变异体在 `--expect none` 下必须零伤害、在默认期望下必须失败）、
死亡与胜利闭环（J1–J9，见下）、
已知缺口回归（I：角色级显式绑定跨实体泄漏时必须被标记 INCOMPATIBLE，绝不静默 COMPATIBLE）。

Phase 1.11 起 G 段还锁定生成物的**结构语义**：实体根必须是 `chase_movement` 入口场景
实例（追击脚本驱动实体本身），且实体根/接触范围都带真实碰撞形状 —— 静态结构断言
（G6b–G6d）与玩法断言（G10f–G10h）同时成立才算通过。

Phase 1.12 起 J 段把刚生成的实体场景放进项目真实竞技场场景：J1–J6 正向（真实攻击路径
打死 → 死亡事件恰好一次 → 击杀计数恰好减一 → 实体退出战斗 → 仍有敌人时不提前胜利 →
最后一个敌人死后场景自身开门 → 玩家进出口区完成，探针脚本已清理），J7 手写
`Scenes/Enemy.tscn` 等价性（同一探针同样结论），J8a–J8c 受控负向（不死变异体零胜利 +
正向期望必须失败），J9 缺少运动能力的生成实体无法进入既有管理链路。

Phase 1.13 起 K 段把生成链路延伸到**关卡编排**：K1–K3 由 Gameplay Blueprint 生成关卡配置
（引用刚生成的实体场景）并通过独立校验，K4 受控负向（非法数量被拒且可定位），K5–K11 真实
运行时（配置驱动的生成数量 / 两波顺序且只推进一次 / 出口锁定与清场开启 / 进出口区 Completed
+ 胜负一次 / 生成物身份），K12 受控负向（无效配置在运行时被拒绝，零生成 + `state=Failed`）。

Phase 1.20 起 N 段建立 **Boss 编排生成链路**：N1 蓝图生成 Boss 实体蓝图（player 复用既有
场景）；N2 bind_assets 解析真实资源绑定；N3 Scene Composer 生成 Boss 实体场景；
N4 `plan_generator` 从蓝图 + 生成物自动产出计划（实例 + `e2e_boss→player` 目标）；
N5 正式入口组合多实体宿主（实例唯一 + `target_path`）；N6 `level_planner --mode boss`
从同一计划生成关卡配置（arena = 组合宿主，boss 身份/实例显式）；N7 独立验证器 PASS；
N8 受控负向：静态合法但宿主实例不存在的配置仍通过契约检查（证明 N9 测的是运行时解析）；
N9–N12 真实 Godot：Boss 身份 / 存活不胜利 / 死亡一次完成 / 重复死亡幂等 / 玩家失败 /
非法 `boss.instance` 运行期拒绝；N13 探针清理。

Phase 1.21 起 P 段建立 **多阶段 Boss 生成链路**：P1 蓝图生成 grunt/boss 两个实体蓝图
（player 复用）；P2 真实绑定覆盖两者；P3 两个实体场景由 Scene Composer 生成；
P4 `plan_generator` 自动产出三实例计划；P5 正式入口组合三实例宿主；P6
`level_planner --stage clear:stage_grunt:2 --stage boss` 生成显式阶段配置；
P7 `check_level --plan` 通过交叉校验；P8 受控负向：`boss.instance=NoSuchBoss` 在构建期
被交叉校验拒绝（exit 1，不进入 Godot）；P9–P12 真实 Godot：清理阶段 Boss 不激活 /
清理完成只激活一次 / Boss 存活不胜利 / 死亡一次完成 / 重复死亡幂等 / 玩家死亡失败；
P13 探针清理。

Phase 1.17 起 L 段建立**多实体组合与绑定完整性**：L1–L5 player 与 enemy 走同一条
显式实体作用域链路（player 角色发现 → `--resolve-entity-from` 打标 → bind_assets
全部 `resolved_from=binding`），L6–L8 player 实体场景独立生成、最终资源归属落盘、
双向无泄漏（enemy 场景无 player 资源、反之亦然），L9–L10 两个生成实体场景由
**正式管线入口** `scene_composer --compose-plan`（Phase 1.18：composition_plan 文档，
composite.py 唯一实现）以 Godot 原生 instancing 组合进同一宿主
（`E2eProbeDualHost.tscn`，宿主不复制实体内容；dry-run 只校验不落盘；L10b 受控负向：
未知目标实例 exit 1 无产物），L11 真实 Godot headless 运行宿主
`status=PASS`，L12–L14 瞬态探针断言两实例存在、命名唯一、且运行时子树资源归属互不覆盖
（enemy=slime、player=player），**L16–L17（Phase 1.18 运行时交互契约）**：enemy 实例根
携带计划声明的 `target_path = NodePath("../E2eProbePlayer")` 并在真实物理帧中朝目标
实例移动（无编排器、探针不指派目标）。L15 探针清理。

Phase 1.19 起 M 段验证**组合计划的自动生成**：计划不再手写，而是由
`scene_composer/plan_generator.py` 依据蓝图与真实生成产物产生 ——
M1 蓝图派生出 `E2eProbeEnemy -[attack]-> E2eProbePlayer`（planner 写 entity_graph 的
同一函数）；M2 自动生成的计划保留实体身份并映射到真实生成场景
（`--entity-scene` 显式映射带显式绑定的玩家场景，provenance=override）；
M3 未声明关系时计划**不含** `targets`（不凭空造追击目标）；M4 蓝图派生关系经
`--relations + --relation attack` 变成声明式目标引用；M5 缺场景映射 exit 1 +
预期路径诊断 + 无产物；M6 未知目标 exit 1 + 无产物。
L9/L10/L16/L17 自此消费的是**自动生成**的计划（不再手写 dual_plan.yaml）。

运行：

```bash
python .ai/tools/e2e/tests/test_end_to_end_generation.py
# 或经统一入口（会被自动发现）
python .ai/tools/run_tests.py e2e
```

组合计划生成器可单独运行：

```bash
python .ai/tools/scene_composer/plan_generator.py <blueprint.yaml> --host DualHost \
    --out Plans/dual.yaml [--entity-scene E=res://...] [--target E1:E2] \
    [--relations .ai/context/entity_graph.json --relation attack] [--dry-run] [--json]
# 退出码: 0 = 计划已生成并通过 compose_from_plan 校验；1 = 失败（无产物）；2 = 用法错误
```

Phase 1.23 起 T 段建立 **黄金 Trace 基线回归检测**：T1–T3 断言四个已批准基线
（`.ai/tools/validator/baselines/{multi_stage_boss,single_stage_boss,waves,holdout}.json`）
存在、
满足基线契约（版本/批准记录/可回放事件）且只归一化显式动态字段；T4 由
`trace_baseline_capture.py` 在**隔离沙箱**内重跑完整生成链路 + 真实 Godot 捕获两个
场景的真实 trace（沙箱用后即删）；T5a–T5d 与批准基线**逐事件比较**（比较器
`validator/trace_baselines.py`：先 trace 校验与回放，后按序对齐比较，动态字段仅
run_id/timestamp_ms，data 默认 strict）；Phase 1.25 起 waves 基线 v2 含波次语义事件
（7 事件链：started→wave_started(0)→wave_cleared(0)→wave_started(1)→wave_cleared(1)→
exit_unlocked→victory）——波次推进与出口解锁直接受事件级保护；覆盖声明只描述
真实事件链（探针度量断言单独列出，不冒充事件覆盖）；T7 捕获 trace 过
Phase 1.22 回放器；
Phase 1.26 起，waves 胜利若声称 `exit_reached_after_unlock` 则必须已有
`exit_unlocked`（回放层 `victory_without_exit_unlock`；出口锁定期间不可能成立胜利）。
Phase 1.27 起 holdout 基线为 v2（3 事件链 started→spawn_schedule_started(0)→victory）：
生成调度激活由事件级保护；旧 v1 形态 trace 与 v2 基线比较会得到 EVENT_MISSING
（explicit re-approval 的结果，不是兼容性破坏）。holdout 的失败路径与终结后重复
由 `Tests/test_holdout_trace.gd`（H1–H7）在真实 Godot 中验证，不进基线。
该守卫另有一条**真实 Godot 注入**证据：`Tests/test_waves_exit_gate.gd`（G1–G6）
在出口锁定时把玩家注入出口区（真实 Area2D 路径）→ 无 level_victory；解锁后才结算；
事件取自生产导出接口 `export_trace_json`，不是手工拼装。
T8/T9 差异注入（改 victory reason → REGRESSION + 字段路径 + CLI exit 1）；
T10 run_id/timestamp_ms 变化保持 PASS（显式动态策略）；T11/T12 基线缺失/损坏 =
BASELINE_MISSING/INVALID_BASELINE（exit 2，绝不 PASS）；T13 断言本次运行**没有改写
任何批准基线**（bytes+mtime 不变）；T14 断言无探针/trace/候选目录残留。

基线批准是显式人工流程（测试永不写基线）：

```bash
python .ai/tools/e2e/approve_trace_baselines.py candidate --scenario multi_stage_boss \
    --out <候选目录>     # 沙箱内真实 Godot 捕获 → 候选文件（绝不覆盖正式基线）
python .ai/tools/e2e/approve_trace_baselines.py review --candidate <候选目录>
python .ai/tools/e2e/approve_trace_baselines.py apply --candidate <候选目录> \
    --approver <name> --note "<批准理由>" --i-approve
# apply 先打印「现有基线 → 候选」逐事件差异并 version+1；无 --i-approve 拒绝写入
```

指纹方案（Phase 1.26）：候选记录 `approval.candidate_fingerprint_scheme`。scheme 1 是
Phase 1.23 的历史 payload（含 scenario_id），只有两条 boss 基线使用；scheme 2 是
Phase 1.24+ 的当前 payload（trace schema 版本 + 事件）。历史文件缺该字段时按已记录
方案集合逐个验算，必须精确命中——不降低篡改检测。

审批入口的信任边界（Phase 1.29）：

- **新候选必须声明当前方案**：缺少 `candidate_fingerprint_scheme` 或声明 scheme 1 的候选
  review/apply 一律拒绝（exit 1）——否则 apply 会按当前方案写入记录，而指纹实际由
  scheme 1 算出，使正式基线的批准记录永远无法复算。scheme 1 仅用于验证**已批准的历史
  基线**（`matching_fingerprint_schemes`）。
- **身份一致性**：给出 `--scenario` 时其必须与候选内容 `scenario_id` 一致（不一致 =
  输入错误 exit 2）；写入目标始终跟随**内容**，CLI 声明不会被静默忽略。
  `--candidate <文件> --scenario <id>` 现在按文件处理（此前会被当成目录拼接路径）。
- **输入错误统一**：候选不可读 / 非 JSON / 非对象时，review 与 apply 给出相同诊断并
  返回 2（不抛异常）。
- 这些规则不改变正常审批路径：`candidate` 产物（scheme 2）仍可 review → apply。

## 环境与副作用边界

- **Godot 缺失**：运行时断言打印 `SKIP` 并记录原因，不会假装已运行。
- **项目内写入**：Godot 只能运行 `res://` 内的资源，因此生成物会短暂写入
  `Scenes/E2eProbeEnemy.tscn`、`Scenes/E2eProbeNochase.tscn`（缺少行为的负向用例）、
  `Scenes/E2eProbeNoContact.tscn`（去掉接触形状的变异体，由生成场景文本派生）、
  `Scenes/E2eProbeImmortal.tscn`（抬高血压的不死变异体，用于死亡/胜利受控负向）、
  `Scenes/E2eProbePlayer.tscn` 与 `Scenes/E2eProbeDualHost.tscn`（Phase 1.17：
  独立生成的玩家实体场景与多实体宿主，Z1 断言清理）、
  `Levels/E2eProbeLevel.json`（生成的关卡配置）与 `Levels/E2eProbeLevelBroken.json`
  （非法数量变异体，用于运行时受控负向）、
  `Scenes/E2eBoss.tscn`、`Scenes/E2eBossHost.tscn`（Phase 1.20：生成的 Boss 实体与
  多实体宿主）、`Levels/E2eBossLevel.json` / `Levels/E2eBossLevelBad.json`
  （boss 生成配置与宿主不匹配变异体）、
  `Scenes/StageGrunt.tscn`、`Scenes/StageBoss.tscn`、`Scenes/E2eStageBossHost.tscn`
  （Phase 1.21：两个实体与三实例宿主）、
  `Levels/E2eStageBossLevel.json` / `Levels/E2eStageBossLevelBad.json`
  （多阶段配置与交叉校验负向变异体）、
  `Tests/test_e2e_probe_enemy.gd`、`Tests/e2e_behavior_probe.gd`、
  `Tests/e2e_death_victory_probe.gd`、`Tests/e2e_level_orchestration_probe.gd`、
  `Tests/e2e_dual_host_probe.gd`、`Tests/e2e_boss_level_probe.gd` 与
  `Tests/e2e_multi_stage_boss_probe.gd`（探针脚本）与
  `Tests/e2e_multi_stage_boss_trace.json`（Phase 1.22：真实诊断 trace，读取后清理），
  并在 `finally` 中删除（`Z1` 断言无残留）。实体 id 一律带 `e2e_probe_`
  前缀，遵守 `gameplay_schema.yaml`「与既有手工场景同名必须显式复用或改名」。
  Phase 1.14 起 `Tests/test_generic_level_orchestration.gd` 另会短暂写入
  `Levels/E2eGeneric*.json`（waves/holdout/非法/v1 等临时关卡配置），
  在收尾 `_cleanup()` 中删除并由 `Z:` 残留断言把关。
- **不改动既有产物**：测试不写入 `Features/`、`Assets/`、既有 `Scenes/*.tscn`、
  既有 `Tests/*.gd`；绑定文档与蓝图写在系统临时目录。
