# Phase 1.46 审计报告 — Composite Scene End-to-End Behavior Evidence

> 范围：从「单个 Feature 行为已验证」推进到「Feature 组合后的整条链已验证」
> 首个验收对象：`Scenes/EscapeRoom.tscn`；对照基线：`Scenes/SurvivalArena.tscn`
> 结论先行：**两条真实组合链已在 Godot 运行时端到端 PASS（各 2 次重放语义一致）**；
> 「门报告已开但仍阻挡」被通行段抓住（不是靠 `is_open`）；SurvivalArena 的**通行段**
> 经实测不可重放（随机敌人生成），已用证据排除而不是伪造 PASS。

---

## 1. 初始状态与保护

### 1.1 Git 与工作区（事实，可复核）

| 项目 | 值 |
| --- | --- |
| HEAD | `1c30f94f95c6594c34ba296fe339455b0de10625` |
| 分支 | `master` |
| 起点 | 35 个 `M` + 29 个 `??`（Phase 1.25–1.45 既有修改，非本次产生） |
| 暂存区 | 空（本次未执行任何 `git add`） |
| 终点 | 35 个 `M` + 35 个 `??`（新增 6 条：组合协议、契约目录、两个新模块、新测试、本报告） |
| Git 操作 | 无 commit / push / reset / clean / checkout / restore |

既有未提交修改（含 `.ai/context/*` 报告、`Features/*/template.yaml`、`Tests/test_*.gd`、
`run_tests.py`、`validate.py`）全部保留；本次不覆盖、不删除任何无法证明归属的文件。

### 1.2 测试基线

Phase 1.45 结束状态即本次起点（同一工作区、同一 HEAD）：

| 口径 | 基线（1.45 结束） | 本次（1.46 结束） |
| --- | --- | --- |
| Godot `SceneTree` 测试 | 38 个文件 PASS | 38/38 PASS |
| Python 测试 | 55 个文件 PASS | 56/56 PASS（+1 新文件） |
| 行为 CLI 门禁 | 17 behavior / 17 PASS（replay 2） | 17/17 PASS（34 次真实运行，exit 0） |
| Validator | 0 error / 17 warning | 0 error / 17 warning |

起点快速探针：`feature_behavior_evidence.py --feature openable_door --replay 2` → PASS。

### 1.3 保护措施（实际执行）

1. 所有缺陷注入都在**本次运行独占的隔离副本**（`.ai/tmp/composite/workspaces/<run_id>/project`）
   内完成，结束后按 SHA256 逐字节恢复并比对；仓库 golden 文件（场景、脚本、契约、协议）
   在测试首尾做哈希快照比较（`test_composite_behavior_evidence.py` Case 14）。
2. 不删除任何既有生成物；本阶段日志与一次性评估契约写在 `.ai/tmp/`（`.gitignore` 已忽略）。
3. 审计发现（第 3–9 节）与实现（第 2 节）、修复/排除（第 6–7 节）分开记录。

---

## 2. 组合场景契约的设计与安全边界

### 2.1 为什么不复用 `Features/<f>/template.yaml#behavior`

| 原因 | 事实依据 |
| --- | --- |
| 契约属于**场景**，不属于任何 Feature | EscapeRoom 的链由 `player_movement` + `trigger_switch` ×2 + `condition_gate` + `openable_door` 共同构成；写进任一 Feature 会把场景归属记错 |
| `behavior[].scene` 只允许 `Features/<f>/` 内相对路径 | `feature_behavior_evidence.py::_behavior_scene` 明确拒绝绝对路径 / `res://` / `..`；扩大该规则会让所有单组件契约都能指向任意场景，破坏既有隔离语义 |
| 形状不匹配 | 单组件契约是「一组动作 + 一个观测窗口 + 一组后置断言」，没有阶段；组合链需要**每段自己的动作与断言**，且必须能记录「只完成到第 N 段」 |

因此新增**独立**协议与契约目录，不修改 `Features/*`，不改变 `behavior` 校验语义。

### 2.2 最小扩展清单（新增能力有据可查）

| 层 | 变更 | 是否为新增执行能力 |
| --- | --- | --- |
| 共享协议 `behavior_protocol.yaml` | +`gate.is_fulfilled` 观测（`ConditionGate.is_fulfilled()`）、+`gate.fulfilled` 信号（args `[bool]`） | 只读观测；**无**新写入能力。用于区分「门关着是因为条件未满足」与「条件满足但门没开」 |
| 组合协议 `composite_behavior_protocol.yaml` v1 | `extends: behavior_protocol.yaml v2`；`scenes`（2 个白名单场景）、`limits`（阶段/动作/观测/帧）、`denied_actions`（`state.set_property`） | 不是能力表，只是**限制** |
| 探针 `composite_behavior_probe.gd` | 分阶段执行 + 阶段级窗口 + 阶段失败记录 + 全链信号监听 | 复用共享 manifest 的 7 个动作 / 11 个观测，未新增动作 |
| 编排器 `composite_behavior_evidence.py` | 隔离副本、`owner.json` 所有权、run_id、重放、CLI | 无新执行原语 |

manifest 重新生成：`8 actions / 11 observations / 6 signals / 1 property`（
`behavior_manifest.json` 与 `composite_behavior_manifest.json` 均由生成器写出，漂移即失败）。

### 2.3 安全边界（明确禁止项）

- 不执行任意 GDScript / 任意方法名：动作必须命中共享 manifest 的 `implementation` 映射。
- 不访问任意文件路径：场景必须**逐字**等于组合协议 `scenes` 白名单中的路径；
  目标路径拒绝 `..` / 绝对路径 / 反斜杠；契约文件只从 `.ai/context/composite_scenes/` 读取。
- 无约束属性写入：`state.set_property` 被组合协议 `denied_actions` 显式禁止，
  组合探针**不实现**该动作（能力门禁会检查这一致性）。
- 每段必须有非夹具动作；「不推进任何帧 + 只断言什么都没发生」的段直接 INVALID
  （Phase 1.45 零帧规则的组合形式，Python 与探针两层各拦一次）。
- 预算：单段窗口 ≤ 120 帧、整链（推进 + 全部窗口）≤ 1200 帧、2..8 段、每段 ≤ 8 动作 / 12 断言。

### 2.4 阶段语义如何承载「次数与顺序」

`stages` 按声明顺序执行；第 N 段的断言在第 N+1 段动作**之前**求值，信号计数跨阶段累计。
因此 EscapeRoom 的「第 2 段开门事件 = 0、第 3 段 = 1」同时证明**次数**与**先后**，
不需要额外的顺序原语。任一阶段失败立即停止，并记录 `failed_stage` 与 `completed_stages`。

---

## 3. EscapeRoom 端到端证据

### 3.1 场景事实（从 `.tscn` 读取，不假定结构）

| 项目 | 内容 |
| --- | --- |
| 根 | `EscapeRoom`（`Node2D`，脚本 `Scenes/escape_room.gd`，只做胜利文案与 R 重开） |
| 节点 | `Player`、`Mechanism/SwitchA`、`Mechanism/SwitchB`、`Mechanism/ConditionGate`（`condition_count=2`）、`Mechanism/ExitDoor`、`Mechanism/EscapeZone`、`HUD/StatusLabel` |
| 连接（场景数据） | `SwitchA.activated → ConditionGate.set_condition(binds=["switch_a"])`；`SwitchB.activated → ConditionGate.set_condition(binds=["switch_b"])`；`ConditionGate.fulfilled → ExitDoor.set_open` |
| 几何 | 门碰撞 24×128 位于 (360,0)（左缘 348）；玩家碰撞 32×48、`speed=220`、physics 60 Hz（3.667 px/帧）→ 被挡时 x≈332 |

### 3.2 四段真实运行（`--replay 2`，两次语义一致）

| 段 | 动作（真实运行时） | 关键观测（实测值） |
| --- | --- | --- |
| `closed_door_blocks_traversal` | `input.press move_right` + 150 physics 帧 + release | Player x **331.99**（区间 320–340）、y 0、`door.is_open=false`、`ExitDoor.state_changed=0` |
| `switch_a_partial_condition_keeps_door_closed` | 在 SwitchA 位置生成真实 `CharacterBody2D`（`group=players`）+ 12 帧 | SwitchA=true、SwitchB=false、`gate.is_fulfilled=false`、`door.is_open=false`、`gate.fulfilled=0`、`door.state_changed=0` |
| `switch_b_fulfils_gate_and_opens_door` | 同上，目标 SwitchB + 12 帧 | SwitchB=true、`gate.is_fulfilled=true`、`door.is_open=true`、`gate.fulfilled=1`（args `[true]`）、`door.state_changed=1`（args `[true]`） |
| `player_traverses_opened_gap` | `input.press move_right` + 45 帧 + release | Player x **496.92**（≥384）、y 0、`door.is_open=true` |

预算：150+10 + 12+20 + 12+20 + 45+5 = **274 帧**（上限 1200）。

### 3.3 五级区分（本题要求的「不得混用」）

| 级别 | 证据 | 是否由本次证明 |
| --- | --- | --- |
| 场景结构正确 | `Tests/test_escape_room.gd` 段 A/B + Validator 结构检查 | 既有证据，本次未改 |
| 信号连接存在 | `get_signal_connection_list("activated").size()==1`（既有测试段 A） | 既有证据 |
| 连接**真的生效** | 第 3 段的 `gate.fulfilled=1` + `door.state_changed=1`（事件由真实接触驱动） | **本次证明** |
| 中间状态正确 | 第 2 段：A 已触发 / B 未触发 / gate 未满足 / 门未开 / 0 次事件 | **本次证明** |
| 真实运行时行为正确 | 第 2、3 段动作是真实物理接触（`body_entered`），不是私有回调 | **本次证明** |
| 玩家实际穿越成功 | 第 4 段 `global_position` = 496.92，**同一玩家、同一输入**，与第 1 段唯一差别是门开了 | **本次证明** |

第 1 段与第 4 段的对照是本契约的核心：若只看 `is_open`，两者无法区分（§6 Case 6 用缺陷注入
验证了这一点）。契约未使用 teleport、未调用 `set_open`、未直接设置最终状态。

### 3.4 明确未覆盖

1. **条件回落**：EscapeRoom 的两个开关是 `Latching`（触发后保持），无法撤回条件，
   因此「All 聚合动态回落 → 门关闭」不能在本场景可靠证明；该能力仍只有
   `condition_gate` 的单组件 behavior（夹具）证据。
2. **EscapeZone / HUD / 胜利文案**：`Mechanism/EscapeZone` 是 `Area2D` 且没有连接任何信号；
   场景在 `ConditionGate.fulfilled` 时就进入 `Escaped`（Phase 1.45 R1），本契约不断言这类表现层语义。
3. **R 重载复位**：由 `Tests/test_escape_room.gd` 段 H 覆盖，不在组合契约内。

---

## 4. 每条关键断言的观测来源

| 断言 | 观测原语 | 来源（谁产生该值） | 能否被「制造」 |
| --- | --- | --- | --- |
| 玩家被挡在门左侧 | `node2d.position(Player, x∈[320,340])` | `PlayerController._physics_process` + `move_and_slide` + 门的 `CollisionShape2D` | 否：位置由物理求解器产生 |
| 玩家越过门口 | `node2d.position(Player, x≥384)` | 同上（输入驱动） | 否 |
| 门关闭/打开 | `door.is_open` | `OpenableDoor` 状态 | 是（但单独不足以 PASS，见 Case 6） |
| 条件聚合满足 | `gate.is_fulfilled` | `ConditionGate._evaluate` | 否（由上报条件计算） |
| 开关被触发 | `trigger.is_triggered` | `TriggerSwitch._on_body_entered`（真实 Area2D 接触） | 否（没有夹具直接写 `_triggered`） |
| 事件次数与参数 | `signal(...count, last_args)` | 探针在**场景加载后、任何动作前**注册的监听器 | 否（监听器只计数） |
| 两扇门各开一次 | `signal(door.state_changed, count=1, last_args=[true])` | 同上 | 否 |

所有动作都是协议注册动作；探针不做「先写状态再断言」的捷径。唯一的状态构造是
`physics.overlap` 在开关位置生成**真实** `CharacterBody2D`（group=players），
它只构造「玩家进入触发范围」这一前置条件，开关状态与后续门事件仍由组件产生。

---

## 5. 重放比较与时间语义

| 项目 | 内容 |
| --- | --- |
| 比较字段 | `status` / `reason` / `failed_stage` / `action_executed` / `completed_stages` / 每段 `id+status+reason` / 每条 check 的 `check,target,entry,expected,observed,status` |
| 有意排除 | `run_id`、`replay_index`、绝对帧号、`waited_frames`、`duration`、证据路径 |
| 排除依据 | 每次重放是独立 Godot 进程与独立场景副本，绝对帧号不可比；帧号属于调度而不是行为语义 |
| PASS 且不一致 | 降级 `INSUFFICIENT / replay_inconsistent`，**绝不保留 PASS** |
| 结果（EscapeRoom） | `--all --require-composite --replay 2` 连续 3 次调用，每次 2 场景 × 2 重放，全部 `consistent=True` |
| 结果（SurvivalArena） | 同上（2 段链），全部 `consistent=True` |
| 反例（真实发生） | SurvivalArena 三段实验中 1 次调用出现 `INSUFFICIENT / replay_inconsistent`（两次重放分别停在 x≈505 与 x≈617），证明该降级路径在真实数据上生效 |
| 不能推出的结论 | `waited_frames` / `first_observed_frame` 不参与比较，也没有 `min_frames`/`max_frames` 语义 → **本层不提供「事件在 N 帧内发生」的时序上界** |

补充时间语义（事实）：本轮所有 PASS 段都是 `waited_frames=0`（动作推进的帧数已足够），
`window_frames` 只在违规时被耗尽（Case 9 的反例为 `waited 20/20`）。这说明窗口不是
「等够固定帧就判过」，而是「有界轮询」；它也不掩盖「过晚触发」，因为动作段本身推进了真实帧。

---

## 6. 负向对照（注入 → 判定 → 恢复）

全部在隔离副本内注入，注入前后记录 SHA256，恢复后逐字节比对。

| # | 注入的缺陷 | 期望 | 实际 | 恢复 |
| --- | --- | --- | --- | --- |
| C1 | 删除 `SwitchB.activated → ConditionGate.set_condition` 的 `[connection]` | 链失败，且定位在第 3 段 | `MISMATCH / state_mismatch`，`failed_stage=switch_b_fulfils_gate_and_opens_door`，`completed=[段1,段2]`，`gate.is_fulfilled=false` | 场景文件 SHA256 恢复一致 |
| C2 | `openable_door.gd` 不再释放碰撞（`set_deferred("disabled", false)`） | 门「已开」但玩家过不去 | `MISMATCH`，`failed_stage=player_traverses_opened_gap`，门 `is_open=true` 仍 PASS 该 check，Player x<384，`completed=3/4` | 脚本 SHA256 恢复一致 |
| C3 | 把第 2 段的 gate 观测目标改成不存在的节点 | 观测不可用，不得 PASS | `INSUFFICIENT / check_unavailable`，`failed_stage=段2` | 契约内存变异，磁盘无写入 |
| C4 | 前置条件改成 `door.is_open == true` | 动作前中止 | `INSUFFICIENT / precondition_unmet`，`stages=[]`，`action_executed=false` | 契约内存变异 |
| C5 | 第 2 段期望 `gate.is_fulfilled == true`（错误中间预期） | 中间状态被判错，后续段不执行 | `MISMATCH`，`failed_stage=段2`，`completed=[段1]`，第 4 段无证据 | 契约内存变异 / CLI 用临时契约目录 |
| C6 | 绕过 Python 校验，直接向探针提交「零帧 + 纯否定」段 | 探针拒绝 | `INVALID / contract_invalid`，detail 含 `no observation window` | 无写入 |
| C7 | 契约里的场景改成 `res://Scenes/../project.godot` | 加载前拒绝 | `INVALID`，detail 含 `allowlist` | 无写入 |
| C8 | 两次重放返回不同语义结果（runner 注入） | 不得保留 PASS | `INSUFFICIENT / replay_inconsistent` | 无写入 |
| C9 | CLI 退出码 | PASS=0；MISMATCH=1；INVALID=1；INSUFFICIENT 默认 0，`--require-composite`=1 | 全部符合；失败调用仍清理工作区（`workspace removed=True`） | — |

**检测能力结论（事实）**：本层能区分「连接断开 / 阻挡未解除但状态正确 / 观测不可用 /
前置不满足 / 中间预期错误 / 零帧 / 非法场景 / 重放不一致」八类问题，且 C1、C2 都
同时保留了「相邻阶段仍然成立」的证据（`completed_stages`），不靠整链一起失败掩盖定位。

**检测能力缺口（事实）**：未注入「开关 A 与 B 的 binds 互换」（会表现为第 2 段 B 已触发）、
「ConditionGate 的 `condition_count` 改为 1」（会在宿主场景中改变语义）等变体；
这些属于同一层的相邻缺陷，本阶段不重复注入。

---

## 7. SurvivalArena 准备度

### 7.1 依赖与组合清单

| 项目 | 内容 |
| --- | --- |
| 场景依赖 | `Scenes/survival_arena.gd`、`Orchestration/level_orchestrator.gd`、`Orchestration/level_config.gd`、`Levels/survival_arena.json`、`HealthBar.tscn`、`player_death.gd`、`Enemy.tscn`/`EliteEnemy.tscn`/`SpikeTrap.tscn`、`HealPickup.tscn` |
| 组合 Feature | `trigger_switch`（RewardSwitch）、`openable_door`（MainDoor、SideDoor）、`player_movement`、`health`、`health_bar`、`chase_movement`/`contact_damage`（敌人生成后） |
| 场景连接 | `RewardSwitch.activated → MainDoor.set_open`；`RewardSwitch.activated → SideDoor.set_open`（1 → 2） |

### 7.2 已由本次组合证据验证的链

| 段 | 观测 |
| --- | --- |
| `both_doors_start_closed` | 两门 `is_open=false`、各自 `state_changed=0`（20 帧真实推进后仍为 0） |
| `reward_switch_opens_both_doors` | 开关被真实接触触发；两门同时 `is_open=true`；各自恰好 `state_changed=1`（args `[true]`） |

`--all --require-composite --replay 2` 连续 3 次调用（=12 次真实运行）全部 PASS 且重放一致。

### 7.3 未覆盖及其阻塞点（有证据）

| 未覆盖 | 阻塞点 | 证据 |
| --- | --- | --- |
| 门关闭时阻断通行 / 开门后可通行 | 敌人**随机**生成在玩家周围：`survival_arena.gd::_enemy_spawn_offset()` = `player + Vector2.from_angle(randf()*TAU) * randf_range(180,260)`，可能正好落在通道上 | 三段契约（导航到 y≈-77 → 被挡在 x≈452 → 触发开关 → 再右移）实测：**6 次调用 / 9 次重放 → 7 PASS、2 MISMATCH（45 帧只走 60.7px，停在 x≈504.9 / 512.7）、1 次调用重放不一致**，被降级为 INSUFFICIENT |
| 撤离 / 胜负 / 计时 | `LevelOrchestrator` 的 holdout 以 real-time 驱动（30s 生存、1.2s 刷新），帧率与刷新顺序不属于语义比较范围 | 同上实验：同一工作区不同重放的玩家位置出现 100px 级差异 |
| 玩家被击杀导致链中断 | 本层没有「玩家生命」前置约束，且敌人/陷阱是并行副作用 | 3 次带 `health.is_dead` 观测的运行均 `is_dead=false`；**死亡不是已证明的原因**，只是可能原因之一 |

几何更正（本次自查发现并修正的一处错误结论）：Divider 上/下段覆盖 y∈[-338,-110] 与 [110,338]，
主门覆盖 y∈[-64,64]，剩余通道仅 **46px** 宽，而玩家碰撞高 **48px** ——
**主门关闭时确实阻断玩家**。本报告初稿曾把 46px 通道当作「可绕行开口」，是错误读数；
对应契约注释已更正（`composite_scenes/survival_arena.yaml`）。

结论：SurvivalArena 可作为「1 开关 → 2 门」的组合基线，但**不能**在本阶段给出
「通行已验证」的结论；要覆盖通行，需要先让敌人生成可确定（例如给场景/契约一个受控的
生成开关，或扩展协议提供「冻结生成」这类受限夹具），这超出本阶段「最小执行器」的范围。

---

## 8. 回归结果与计数口径

### 8.1 结果

| 项 | 命令 | 结果 | 口径 |
| --- | --- | --- | --- |
| Godot 全部 | `run_tests.py --godot-only` | **38/38 PASS**，exit 0 | 38 个 `.gd` 测试文件（12 Feature 单测 + 26 场景/集成） |
| scene_composer 段 | `run_tests.py scene_composer` | **26/26 PASS**，exit 0 | 26 个 Python 测试文件（含新组合测试） |
| validator 段 | `run_tests.py validator` | 10/10 PASS | 10 文件 |
| asset_registry 段 | `run_tests.py asset_registry` | 11/11 PASS | 11 文件 |
| runtime 段 | `run_tests.py runtime` | 5/5 PASS | 5 文件 |
| feature_registry 段 | `run_tests.py feature_registry` | 4/4 PASS | 4 文件 |
| gameplay_planner 段 | `run_tests.py gameplay_planner` | 2/2 PASS | 2 文件 |
| evaluation 段 | `run_tests.py evaluation` | 2/2 PASS | 2 文件 |
| e2e 段 | `run_tests.py e2e` | 2/2 PASS | 2 文件（含 173 项内部断言与所有权检查） |
| 行为协议一致性 | `tests/test_behavior_protocol_consistency.py` | PASS | **100 条断言** |
| 组合场景测试（新） | `tests/test_composite_behavior_evidence.py` | PASS | **100 条断言** / 13 Case / 连续 2 次全 PASS |
| 单组件行为证据 | `tests/test_feature_behavior_evidence.py` | PASS | 169 条断言（未改动） |
| 时间驱动行为 | `tests/test_behavior_time_driven.py` | PASS | 72 条断言 |
| 条件门控行为 | `tests/test_condition_gate_behavior.py` | PASS | 53 条断言（更新了能力计数断言） |
| 行为 CLI 门禁 | `feature_behavior_evidence.py --all --require-behavior --replay 2` | **exit 0** | **17 behavior / 34 次真实运行**（replay 2），pass=17 |
| 组合 CLI 门禁（新） | `composite_behavior_evidence.py --all --require-composite --replay 2` | **exit 0** | **2 条链 / 4 次真实运行**（每链 2 次重放），pass=2 |
| 静态 Validator | `validator/validate.py` | **exit 0** | 0 error / 17 warning（全部是既有资产 manifest 缺失图片） |

### 8.2 计数口径与一处诚实的限制

- 「测试文件数」≠「断言数」≠「behavior 数」≠「链数」≠「重放数」，本报告不把它们相加。
- Python 段之间按**路径子串**过滤、互相重叠：8 段合计 **62 次测试调用**，覆盖 **56 个唯一文件**
  （重叠 6 个：`scene_composer` 下名为 `*_validator*.py` 的文件同时落入 validator 段等）。
- **单命令全量 `run_tests.py` 本次未取得结果**：它在运行超过 10 分钟时被工具超时截断
  （输出为缓冲写盘，日志为空）。因此本次改为按运行器文档化的分段执行方式（上表），
  每段独立 exit 0。这是**执行环境的时限观测**，不是测试失败；不得据此声称
  「单命令 94/94 通过」——只能说「分段执行：Godot 38/38 + Python 56/56 全部 PASS」。

---

## 9. 已知局限与不能据此得出的结论

1. **只有两条链**：`scenes` 白名单只有 EscapeRoom 与 SurvivalArena；其余场景
   （SlimeEnemy、TimedCombatArena、BossChallenge 等）没有组合证据。
2. **重放一致 ≠ 确定性**：只证明「两次运行的状态/事件观测相同」，不证明时序确定，
   也不给延迟上界（帧号与 `waited_frames` 不参与比较）。
3. **阶段边界证明顺序，但不证明间隔**：能证明「第 2 段时事件为 0、第 3 段时为 1」，
   不能证明「在第 N 帧到第 N+k 帧之间」。
4. **EscapeRoom 的开关是真实物理接触**，但 `physics.overlap` 生成的是一个简化
   `CharacterBody2D`（32×32 方块），不是完整玩家（32×48 + Health）；它只用于触发 Area2D，
   不影响通行段（通行段用的是真正的 `Player`）。
5. **表现层不在范围内**：HUD 文案、动画、音效、`EscapeZone` 的语义都没有断言。
6. **SurvivalArena 不能得出「门 → 通行」结论**（§7.3），也不能得出「存活/胜负逻辑正确」。
7. **协议仍有重复代码**：组合探针为了独立入口，重复了单个 Feature 探针的参数/观测校验逻辑；
   能力定义的唯一权威仍是共享 manifest，且由一致性测试（`check_capabilities`）守门，
   但两处校验逻辑需要同步修改——这是可接受的维护成本，不是「第二份能力定义」。
8. **未覆盖的配置矩阵**：`condition_gate` 只覆盖 All 聚合；`trigger_switch` 只覆盖默认
   Latching；`openable_door` 只覆盖 `start_open=false`。

---

## 10. 是否需要进一步扩展协议

| 问题 | 结论 | 依据 |
| --- | --- | --- |
| 组合链需要新的执行原语吗？ | **不需要**。现有动作（真实输入、physics 帧推进、真实接触）与观测（状态、事件次数/参数、位置）足以表达两条链 | §3.2 全部断言都由既有原语获得 |
| 需要新的只读观测吗？ | **需要 1 个**：`gate.is_fulfilled`（+ 对应信号 `gate.fulfilled`）。没有它就无法区分「条件未满足」与「门没开」 | §6 C1：断连后门关着，但只看门无法区分原因 |
| 需要夹具写状态吗？ | **不需要，且明确禁止** | 组合证据的意义是真实组件交互；`state.set_property` 列入 `denied_actions` |
| 需要时序上界吗？ | 本阶段不需要。若未来要断言「N 帧内」，需要新增 `min_frames`/`max_frames` 观测语义并给出兼容性影响 | §5 排除项 |
| 是否需要为 SurvivalArena 通行段加能力？ | 需要「受控的生成冻结」类能力或场景侧可注入开关；在拿到该能力前，不把通行写入契约 | §7.3 的不可重放证据 |

---

## 11. 本次运行产生的文件

| 文件 | 性质 |
| --- | --- |
| `.ai/context/composite_behavior_protocol.yaml` | 新增：组合场景协议（场景白名单 / 阶段预算 / 禁止动作） |
| `.ai/context/composite_scenes/escape_room.yaml` | 新增：EscapeRoom 四段契约 |
| `.ai/context/composite_scenes/survival_arena.yaml` | 新增：SurvivalArena 两段契约（含通行段排除理由） |
| `.ai/tools/scene_composer/composite_behavior_protocol.py` | 新增：协议加载 / 契约校验 / manifest 与能力门禁 |
| `.ai/tools/scene_composer/composite_behavior_evidence.py` | 新增：隔离工作区（owner.json）/ 重放 / 判定 / CLI |
| `.ai/tools/scene_composer/probes/composite_behavior_probe.gd` | 新增：分阶段组合探针 |
| `.ai/tools/scene_composer/probes/composite_behavior_manifest.json` | 新增：生成物（探针只读） |
| `.ai/tools/scene_composer/tests/test_composite_behavior_evidence.py` | 新增：13 Case / 100 断言 |
| `.ai/context/behavior_protocol.yaml` | 修改：+`gate.is_fulfilled`、+`gate.fulfilled`（只读能力） |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | 修改：实现 `observe_gate_is_fulfilled` |
| `.ai/tools/scene_composer/probes/behavior_manifest.json` | 重新生成（8/11/6/1） |
| `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 修改：能力计数断言 8/10/5/1 → 8/11/6/1 |
| `.ai/tools/scene_composer/tests/test_condition_gate_behavior.py` | 修改：同一计数断言（并说明新增的是只读观测） |
| `.ai/tools/run_tests.py` | 修改：文档中的 Python 计数 55 → 56、总量 93 → 94、scene_composer 25 → 26 |
| `.ai/context/scene_composer_schema.yaml` | 修改：新增 `composite_behavior_evidence` 段 + `gate.is_fulfilled` |
| `.ai/context/CONTRACT_INDEX.yaml` | 修改：新增两个模块条目、检查项与独立 CLI |
| `.ai/context/PHASE_1_46_AUDIT.md` | 本报告（新增） |

证据目录：`.ai/tmp/composite/<run_id>/`（契约、结果、stdout/stderr）保留；隔离工作区
`.ai/tmp/composite/workspaces/<run_id>/` 在正常结束、失败结束与异常路径下都只删除
`owner.json` 证明属于本运行的副本（他人目录只报告、不删除）。未提交、未推送。
