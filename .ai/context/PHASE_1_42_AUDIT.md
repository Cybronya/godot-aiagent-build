# Phase 1.42 审计报告 — Frame Control & Constrained State Setup

日期：2026-10-23
分支：`master`　HEAD：`1c30f94`（本阶段未提交、未推送）

---

## 1. Git 初始与最终状态

- 初始：`master` / `1c30f94`（2026-10-20），工作区带着 Phase 1.36–1.41 的未提交成果
  （行为协议、探针、行为证据模块、实例证据模块、各 Feature 的 `behavior:` / `runtime:` 声明等）。
- 最终：仍为 `master` / `1c30f94`；**未 commit、未 push、未 stash**，未执行 reset / clean /
  checkout / 批量恢复。
- 初始 `git status --short`：33 modified + 27 untracked（含 Phase 1.36–1.41 的未跟踪模块/
  测试/审计，以及上一轮 e2e 中断留下的 6 个固定名产物：`Scenes/E2eProbe{Enemy,Immortal,
  NoContact,Nochase}.tscn`、`Tests/e2e_death_victory_probe.gd`、`Tests/test_e2e_probe_enemy.gd`）。
- 最终：33 modified + 22 untracked；本阶段新增 `PHASE_1_42_AUDIT.md` 与
  `test_behavior_time_driven.py`，其余未跟踪文件集合不变。
- **唯一减少项**：全量回归中的 e2e 测试按 Phase 1.33 的既有所有权契约
  （签名验证 → 启动期回收上一轮残留 → 本轮结束删除本轮产物）清掉了上述 6 个**生成物**；
  这是该测试的既定行为，不是手动删除。没有删除任何 tracked 文件，也没有改写
  用户既有的 33 个修改。该清理在运行前无法预知，故在此如实记录。
- 本阶段未改写任何 tracked 的 `Scenes/*.tscn`、黄金 trace 基线、e2e 基线或既有 6 个
  behavior 的 `template.yaml`；`moving_platform` / `trigger_switch` / `player_movement` 的
  模板只**新增** `behavior:` 段落。

运行环境：Windows + `Godot_v4.7-stable_win64_console.exe`（`--headless --path <copy> -s ...`）。

---

## 2. 帧推进机制与真实执行语义

### 2.1 协议入口（唯一）

```yaml
simulation.advance_frames:
  implementation: simulation_advance_frames
  target: none
  advances_frames: true          # 计入帧预算
  params:
    frames: {type: int, required: true, min: 1, max: 300}
    phase:  {type: enum, values: [physics], default: physics}
```

- **只支持 physics 帧**。`process` 未声明：`--headless` 下 process 帧不被节流、
  `delta` 随墙钟变化，无法保证可重放，因此协议拒绝该值（Python 与探针各校验一次）。
- 帧预算：单次 ≤ `limits.max_frames_per_action`（300）；单契约累计
  `所有推进动作 + window_frames ≤ max_total_frames`（600）。两条上限同源于
  `behavior_protocol.yaml`，探针从 manifest 读取，不另存常量。
- 目标类型 `none`：`target` 必须省略或为 `"."`；指向具体节点即 `INVALID`。

### 2.2 真实执行语义

探针是 `extends SceneTree` 脚本，实现为：

```gdscript
for _i in frames:
    await physics_frame
record["executed"] = true
```

- 每个 `await physics_frame` 恰好恢复一次于一次真实 physics tick，**不使用** Feature 的
  私有回调、不手工改写状态、不调用 `_physics_process`。被测 Feature 的位移/信号来自它自己
  的 `_physics_process` / `body_entered`。
- `project.godot` 未覆盖 `physics/common/physics_ticks_per_second`，即默认 60 Hz；
  物理 `delta` 固定为 `1/60`，与墙钟无关，因此同一动作序列在真实运行时是确定的。
- 实测线性：`moving_platform`（`travel=200`，`period=4s`，三角波 ⇒ 100 px/s）
  推进 60 帧位移 **100.0 px**；12 帧落在 18–22 px 容差断言内（线性比例约为 1/5）。
- 帧账本：每个动作记录 `started_frame` / `ended_frame`（`Engine.get_physics_frames()`）
  与 `advanced_frames`；每次运行记录 `advanced_frames` / `frame_budget` /
  `observed_physics_frame`。`run_id` 形如 `<pid>-<hash>-<behavior>-r<n>`，证据目录
  `.ai/tmp/behavior/<run_id>/`。
- 观测窗口：所有动作完成后，在 `window_frames` 个 physics 帧内逐帧轮询；全部断言满足即停，
  否则等满窗口。每个检查记录 `first_observed_frame`（相对帧号，-1 = 未满足）。

### 2.3 三个目标 Feature 的帧语义审计

| Feature | 真实驱动方式 | Timer / `_process` | 本阶段如何推进 |
| --- | --- | --- | --- |
| `moving_platform` | `AnimatableBody2D._physics_process` 三角波，`sync_to_physics = true` | 无 | 推进 physics 帧 |
| `trigger_switch` | `Area2D.body_entered`（物理接触信号） | 无 | `physics.overlap` 生成真实 `CharacterBody2D` + 推进 physics 帧 |
| `player_movement` | `CharacterBody2D._physics_process` 读 `Input.get_vector` → `move_and_slide` | 无 | `Input.action_press/release` + 推进 physics 帧 |

---

## 3. 受约束状态设置的范围与安全限制

新增 `state.set_property`（`fixture: true`），只在**无法用合法动作构造前置条件**时使用。
当前仅声明 1 个属性：

```yaml
properties:
  trigger_switch.trigger_mode:
    property: trigger_mode
    class: TriggerSwitch
    values: [Latching, Repeat, Toggle]
```

安全限制（Python 与探针双侧实现）：

1. **白名单属性**：`property` 必须是 `property_ref`，引用 `properties:` 中已注册的 ID；
   未注册 → `contract_invalid`（"is not a registered property"），不执行任何写入。
2. **类型与值域**：`value` 必须是 `any` 参数，且必须落在该属性的 `values` 内；否则拒绝。
   探针再按属性 `hint_string` 解析枚举序号，`hint` 不含该枚举名 → 拒绝。
3. **类名匹配**：探针要求目标节点脚本的全局类名 == 声明 `class`（`_script_global_name`），
   在 `OpenableDoor` 上设置 `trigger_switch.trigger_mode` → 失败（非 PASS）。
4. **顺序**：夹具必须排在所有非夹具动作之前；Python `sequence_errors()` 与探针
   `_check_action_sequence()` 同时拒绝"先动作后设置"。
5. **数量**：单契约夹具 ≤ `max_fixture_actions`（4）；且必须至少有一个非夹具动作
   （"setup alone can never prove behavior"）。
6. **审计记录**：探针记录 `before`（读取原值）、`value`（协议值）、`after`（写入后回读），
   实测量 `0 → "Toggle" → 2`。
7. **隔离**：所有设置只作用于 `.ai/tmp/behavior/workspace-*/project` 的隔离副本；
   仓库场景与黄金基线不被写入。
8. **不能替代断言**：夹具只构造前置条件，后置断言仍在真实动作之后从运行时读取；
   本阶段没有任何 behavior 通过"直接设置最终状态"取得 PASS。

同时新增受控输入夹具 `input.press` / `input.release`：只接受**项目 InputMap 中已存在**的
动作名（`InputMap.has_action`），使用 `Input.action_press/release`，探针退出时释放本次
按下的全部动作；不注入任意键鼠事件、不执行脚本。

---

## 4. 协议与 manifest 变更

`.ai/context/behavior_protocol.yaml`（唯一权威）从 v1 升到 v2：

| 维度 | v1（1.41） | v2（1.42） |
| --- | --- | --- |
| `protocol_version` | 1 | 2 |
| actions | 4 | 8（+`simulation.advance_frames`、`state.set_property`、`input.press`、`input.release`） |
| observations | 6 | 10（+`node.exists`、`trigger.is_triggered`、`node2d.position`、`node2d.displacement`） |
| signals | 4 | 5（+`trigger.activated`） |
| 顶层 | — | `limits`（3 项）、`properties`（1 项）、`targets.kinds.none` |
| 参数类型 | bool/int/string/scalar_list/signal_ref | 增加 `enum` / `property_ref` / `any` / `float` |
| 动作标志 | — | `advances_frames`、`fixture` |

生成物与门禁：

- `probes/behavior_manifest.json` 由 `behavior_protocol.py --write-manifest` 重新生成；
  重复生成逐字节一致。
- `behavior_protocol.py --check-manifest --capabilities` → `PASS`（actions 8 / observations 10 /
  signals 5，实现映射完整、版本三方一致）。
- 探针 `PROTOCOL_VERSION = 2`；能力声明全部来自 manifest，探针只保留
  `implementation ID → 内部方法` 映射。
- 文档同步：`CONTRACT_INDEX.yaml`、`scene_composer_schema.yaml`、`Features/FEATURE_SCHEMA.md`、
  `validator/README.md`、`run_tests.py` 的 Phase 1.42 说明与测试清单。

---

## 5. 新接入 Feature 的前置条件、动作与后置断言

三个 Feature 各 2 个 behavior（共 6 个），均在隔离副本中双次重放：

| Feature / behavior | 前置条件 | 真实动作（帧） | 后置断言 | 实测 | 重放 |
| --- | --- | --- | --- | --- | --- |
| `moving_platform` / `travel` | `node2d.position(y)=0±0.5` | 推进 60 physics 帧 | `displacement(x) 98..102`；`displacement(y)=0±0.5` | 100.0 / 0.0 | 2/2 一致 |
| `moving_platform` / `round_trip` | — | 推进 240 physics 帧（一个完整往返） | `displacement(x)=0±2`；`node.exists=true` | 0.0 / true | 2/2 一致 |
| `trigger_switch` / `latch_once` | 未触发；`trigger.activated` 计数 0 | 真实接触 → 6 帧 → 再次真实接触 | 已触发；信号计数 1（`last_args [true]`） | true / 1 | 2/2 一致 |
| `trigger_switch` / `toggle_on_second_contact` | 未触发；夹具 `trigger_mode: 0→Toggle→2` | 接触 → 6 帧 → 接触 | 回到未触发；信号计数 2（`last_args [false]`） | false / 2 | 2/2 一致 |
| `player_movement` / `move_right` | `displacement(x)=0±0.01` | 按下 `move_right` → 1 帧（输入刷新）→ 12 帧 | `displacement(x) 43.5..44.5`；`y=0±0.5` | 44.0000038 / 0.0 | 2/2 一致 |
| `player_movement` / `stop_on_release` | — | 按下 → 1+12 帧 → 释放 → 12 帧 | 位移仍 43.5..44.5（不再移动） | 44.0000038 | 2/2 一致 |

要点：

- 平台位移**没有**通过写 `global_position` 制造；`travel` 的 100 px 完全来自
  `_physics_process` 在 60 个真实物理帧上的积分。`round_trip` 用 4 秒完整往返把
  "单向运动 / 半途停住"排除在外。
- `latch_once` 的两次接触都由真实的 `physics.overlap` 生成 `CharacterBody2D`，
  由物理引擎触发 `Area2D.body_entered`，没有直接调用 `_on_body_entered`。
- `toggle_on_second_contact` 展示了受约束夹具的合法用途：`Latching → Toggle` 无法用
  游戏动作构造，故用协议白名单属性；夹具记录 `before/value/after`，其余断言仍来自
  真实接触后的运行时状态。
- `player_movement` 走真实输入入口（`Input.action_press/release` + InputMap），
  位置由 `move_and_slide()` 产生；`stop_on_release` 证明释放后不再移动。
- 时间点观测示例：`toggle_on_second_contact` 的 `first_observed_frame = 1`——第二次接触的
  `body_entered` 在下一物理帧才被观测到；`travel`/`latch_once` 为 0（检查点已满足）。

---

## 6. 证据语义、时间窗口与重放一致性

状态语义保持不变：

- `PASS`：动作真实执行（`action_executed=true`）、窗口内全部后置断言成立、重放关键结果一致。
- `MISMATCH`：动作已执行但状态/信号与契约冲突，或窗口耗尽仍未满足。
- `INSUFFICIENT`：帧推进失败、前置不满足、观测不可用、采集失败、重放不一致、Godot 缺失。
- `INVALID`：动作/参数/观测/契约非法，或协议非法/漂移（fail closed）。
- `NOT_DECLARED`：未声明 `behavior:`。

时间驱动测试显式区分：起始状态（前置断言 + 位移基线）→ 动作时机（`started_frame`）→
推进区间（`ended_frame`）→ 检查点（`first_observed_frame` / `observed_physics_frame`）→
最终状态（后置断言）→ 重放比较范围。

重放比较（`BehaviorRun.fingerprint()`）只比：

```
status / reason / action_executed / 每条 check 的 (check, target, entry, expected, observed, status)
```

忽略 `run_id`、绝对帧号、耗时。实测 `round_trip` 两次重放的 `started_frame` 为 9 与 10
（调度抖动），观测值同为 0.0，仍判一致；这符合"比较关键状态与事件，而非绝对时序"。
反之，若关键状态不同（负向对照中的真实缺陷），即使帧推进成功也不会 PASS。

12 个 behavior（既有 6 + 新增 6）全部 2/2 一致，CLI `--all --require-behavior` 退出 0。

---

## 7. 负向对照与恢复校验

全部对照都在隔离副本 / 本次拥有的临时目录内进行；结束后比对 `sha256` 恢复原状。

| # | 对照 | 预期 | 实际 | 退出码 / 恢复 |
| --- | --- | --- | --- | --- |
| N1 | `frames: 0` | 拒绝 | Python `INVALID`（"does not match type int"）；Godot `INVALID/contract_invalid` | 验证器 exit 0（断言成立）；CLI 实测 exit 1 |
| N2 | `frames: 301` / `700`（超单次上限） | 拒绝 | 同上，`INVALID` | 同上 |
| N3 | `phase: process` | 拒绝 | Python `INVALID`（enum）；Godot `INVALID` | 同上 |
| N4 | 300+300 帧 + 窗口 30（>600） | 拒绝 | `INVALID`（"exceeds max_total_frames"） | 断言成立 |
| N5 | 帧推进带 `target: Child` | 拒绝 | `INVALID`（"target kind none"） | 断言成立 |
| N6 | 未注册属性 `door.is_open` | 拒绝 | `INVALID`（"not a registered property"） | 断言成立 |
| N7 | 非法枚举值 `Bogus` | 拒绝 | Python + Godot 均 `INVALID` | 断言成立 |
| N8 | 夹具排在动作之后 | 拒绝 | Python "setup must come first"；Godot `INVALID` | 断言成立 |
| N9 | 只有夹具、没有行为动作 | 拒绝 | `INVALID`（"at least one non-fixture"） | 断言成立 |
| N10 | 在错误类上设置声明属性 | 不 PASS | `INSUFFICIENT`/`INVALID`，绝不 PASS | 断言成立 |
| N11 | 平台永不移动（真实缺陷） | 非 PASS | `MISMATCH/state_mismatch` | CLI 实测 exit 1（`MISMATCH`） |
| N12 | 平台只去不回（真实缺陷） | `travel` 仍 PASS、`round_trip` 失败 | 分别为 PASS / `MISMATCH`（证明断言有针对性） | 断言成立 |
| N13 | `period=400`，窗口内看不到运动 | 非 PASS | `MISMATCH`（窗口耗尽，不因推进成功而 PASS） | 断言成立 |
| N14 | 开关只发信号、不改状态 | 非 PASS | `MISMATCH`（信号 1 但状态未变） | 断言成立 |
| N15 | 移除 `is_triggered()`（观测不可用） | 非 PASS | `INSUFFICIENT` | 断言成立 |
| N16 | 改协议不重新生成 manifest | 漂移门禁失败 | `FAIL: behavior manifest drift in limits`，验证器 `INVALID/protocol_drift`（启动 Godot 前拒绝） | 漂移门禁实测 exit 1；探针副本恢复后门禁再次通过且 `sha256` 一致 |

恢复校验：注入缺陷后恢复的平台/开关脚本、CLI 使用的 Features 副本、漂移实验探针副本，
`sha256` 均与操作前一致；仓库 `Features/**.gd` 从未被写入。

---

## 8. Phase 1.38–1.41 回归矩阵

| 检查 | 结果 |
| --- | --- |
| 新增时间驱动测试（Case 1–7） | **72/72 PASS**，exit 0（`.ai/tmp/p142_time_driven.log`） |
| 协议一致性测试（1.41，含 Case 8/9/10） | **92/92 PASS**，exit 0 |
| Phase 1.40 行为证据测试 | **134/134 PASS**，exit 0 |
| 行为 CLI `--all --require-behavior`（每行为 2 次重放） | **12/12 PASS**（6 既有 + 6 新增），exit 0 |
| Phase 1.38 静态实例证据 | **41/41 PASS**，exit 0 |
| Phase 1.39 运行时实例证据 | **67/67 PASS**，exit 0 |
| Scene Composer 段 | 23/23 PASS |
| Validator 段 | 10/10 PASS（含于全量） |
| Godot headless | 39/39 PASS |
| 全量 `.ai/tools/run_tests.py` | **92/92 PASS**，exit 0（Godot 39 + Python 53） |
| 静态 Validator `validate.py` | **0 error / 17 warning**，exit 0 |
| 协议 manifest / 能力门禁 CLI | PASS（8 动作 / 10 观测 / 5 信号，实现映射完整） |

既有 6 个 behavior 的观测值（最终代码实测，与 1.41 完全一致）：

| Feature / behavior | 观测值 |
| --- | --- |
| `openable_door` / `open` | `[true, 1]` |
| `health` / `damage` | `[1, 1]` |
| `health` / `heal_clamped` | `[5, 2]` |
| `health` / `death` | `[0, true, 1]` |
| `collect_pickup` / `collect_on_contact` | `[true, 1]` |
| `heal_pickup` / `heal_damaged_target` | `[4, true]` |

17 条 warning 与 1.40/1.41 相同，均为 `assets/**.png` 不在当前检出中，与本阶段无关。

---

## 9. 仍未支持的能力与原因

1. **process 帧推进**：未声明。`--headless` 下 process 帧不被节流、`delta` 非确定，
   无法保证可重放；声明它等于承诺一个做不到的语义。
2. **任意属性写入 / 任意方法调用 / GDScript 执行**：明确不做。状态设置只有 1 个白名单属性，
   属性解析依赖 `hint_string`，类名必须精确匹配。
3. **任意输入注入**：只支持 InputMap 中已有的动作名，用 `Input.action_press/release`；
   不注入键鼠事件、不支持鼠标/摇杆、不支持组合宏。
4. **条件式等待**：只有固定帧数推进；没有 "advance until signal/condition"，
   因此对"何时发生"未知的行为需要靠足够大的窗口 + 范围断言，帧数预算受 600 限制。
5. **速度/加速度观测**：未声明 `node2d.velocity`；`player_movement` 只能以位置证明移动，
   无法直接断言速度大小。
6. **Timer / 墙钟驱动行为**：未覆盖。当前三个 Feature 都不依赖 Timer；
   若将来引入，需先定义可重放的时钟语义。
7. **多实体/组合行为**：仍是单 Feature、单场景；没有跨 Feature 的协同行为断言。
8. **自动修复 / 默认嵌入静态 Validator**：不做；行为证据仍是独立入口，
   `validate.py` 只保留实例证据，不因本阶段改变退出语义。
9. **严格绝对时序比较**：刻意不做；重放只比关键状态与事件顺序，不比帧号与耗时。

---

## 10. 下一阶段建议

1. 把时间驱动能力扩展到 `chase_movement`、`condition_gate`、`contact_damage` 等
   帧/接触驱动 Feature，优先复用现有动作与观测，不轻易新增协议项。
2. 评估 `simulation.advance_until`（有上限的谓词等待），减少对固定帧数的硬编码，
   同时保持帧预算与 fail-closed 语义。
3. 若确实需要速度类断言，再引入受约束的 `node2d.velocity` 观测（只读、单轴、带容差），
   不为"更完整"而提前扩表。
4. 把"协议生成 + 漂移门禁 + 行为证据"串成单条验收命令（例如 `behavior_protocol.py --check`
   后接 `--all --require-behavior`），便于 CI 使用；不改变静态 Validator 默认行为。
5. 为 `state.set_property` 增加"属性值域来自真实脚本 hint"的一致性测试，
   防止协议白名单与运行时枚举漂移。

---

## 11. 结论

- 帧推进是**真实 physics 帧**：探针 `await physics_frame`，Feature 自己的
  `_physics_process` / `body_entered` 产生状态变化；未使用私有回调或手工状态模拟。
- 状态设置是**受约束夹具**：单一白名单属性、类名匹配、值域/hint 校验、顺序与数量限制、
  before/value/after 审计、隔离副本，且不能替代后置断言。
- 时间点观测来自真实运行时对象（`global_position`、节点有效性、协议属性、信号计数），
  Python 不根据期望值推导实际值。
- 新增 6 个时间驱动 behavior 全部 PASS 且 2/2 重放一致；既有 6 个 behavior 的观测值、
  状态语义与重放结果与 1.41 完全相同。
- 负向对照覆盖非法帧/预算/类型、非法属性、真实缺陷、窗口耗尽、观测不可用与协议漂移，
  全部稳定失败并可逐字节恢复。
- 全量回归 92/92（Godot 39 + Python 53）、静态 Validator 0 error；限制与后续建议见 §9/§10。
