# Phase 1.44 审计报告 — Condition Gate Behavior Evidence

日期：2026-10-23
分支：`master`　HEAD：`1c30f94`（本阶段未提交、未推送）

---

## 1. 开始状态、未提交修改与测试基线

- 起点：`master` / `1c30f94`；`git status` = **34 modified + 25 untracked = 59**
  （Phase 1.36–1.43 的未提交成果：行为协议 v2、探针、行为/实例证据模块、
  14 个 behavior、`PHASE_1_43_AUDIT.md` 等）。
- 未执行 reset / clean / checkout / 批量 restore；不删除无法归属本次运行的文件。
- 测试基线（1.43 结束）：**92/92 PASS（Godot 38 + Python 54）**。
  本阶段新增 1 个 Python 测试文件，结束时为 **93/93 PASS（Godot 38 + Python 55）**。
- 最终：**35 modified + 28 untracked**（`+template.yaml`；`+夹具`、`+测试`、`+本报告`）。
  对 tracked 文件的改动全部是**追加式**：`condition_gate/template.yaml` 追加 `behavior:` 段
  （`git diff` 显示 +70 行、0 删除），`CONTRACT_INDEX.yaml` / `validator/README.md` /
  `run_tests.py` 增加条目与计数说明；两个既有测试只把「已声明 behavior 集合/数量」更新到 17。
  没有删除、重写或弱化任何既有断言。

运行环境：Windows + `Godot_v4.7-stable_win64_console.exe`（`--headless --path <copy> -s ...`）。

---

## 2. `condition_gate` 实际实现与契约依据

`Features/condition_gate/condition_gate.gd`（`class_name ConditionGate extends Node`）：

```gdscript
signal fulfilled(is_fulfilled: bool)
enum Aggregation { All, AtLeast }
@export var condition_count := 2
@export var aggregation: Aggregation = Aggregation.All

func set_condition(value: bool, id: String) -> void:
    _states[id] = value
    _evaluate()

func _evaluate() -> void:
    # All: 全部已上报条件为 true 且数量 ≥ condition_count
    # AtLeast: 当前 true 数 ≥ condition_count（动态重评）
    # 仅在跨越阈值时广播（重复同值幂等）
```

- 纯逻辑组件：**没有** `_process` / `_physics_process` / Timer / 输入读取；
  状态只由 `set_condition(value, id)` 与 `reset()` 改变。
- 输出只有 `fulfilled(bool)` 信号与 `is_fulfilled()` 查询；不直接驱动任何下游。
- 与 `trigger_switch` / `openable_door` 的组合契约见 `feature.yaml` 的 `composition.usage`：
  `activated(bool)` → `set_condition`（`binds=["条件id"]`）、`fulfilled` → `set_open`。
  仓库中 `Scenes/EscapeRoom.tscn` 等已按此方式连接。

Feature 文档明确的行为规则（契约依据）：

1. All（默认）：已上报条件全为 true **且** 数量达到 `condition_count` 才达成；
2. 任一已上报条件回落 → 聚合回落（`set_condition` 是绝对值上报）；
3. 重复上报同值不产生多余广播（幂等）；
4. 纯逻辑：不知道条件来自开关、按钮还是脚本。

本阶段据此只声明三条可证明的契约：**条件不足时输出不成立**、**条件齐备时输出成立一次**、
**条件回落时输出撤回**。不把 AtLeast 模式、`reset()` 时机、信号抖动等未在本阶段观测的内容
写成契约（见 §9）。

---

## 3. 能力缺口审计：结论是「不需要扩展协议」

在写任何契约前逐项核对现有能力：

| 需要的能力 | 现有实现是否足够 | 说明 |
| --- | --- | --- |
| 提供条件输入 | 足够（组合） | `physics.overlap` 在开关位置生成真实 `CharacterBody2D`（`players` 组），由物理帧触发 `Area2D.body_entered`；开关的 `activated(bool)` 经场景连接送入 `set_condition` |
| 观察门控输出 | 足够（组合） | `fulfilled` 直连 `OpenableDoor.set_open`，用既有观测 `door.is_open` + `signal door.state_changed` 计数/参数判断；无需新增 `is_fulfilled` 观测 |
| 让条件回落 | 足够（既有夹具） | `trigger_switch` 的 `Toggle` 模式可由第二次接触翻转；夹具在 **场景内** 声明 `trigger_mode`，未使用 `state.set_property` |
| 条件输入不可满足 | 足够 | 夹具副本把 `target_group` 改成 `enemies`，真实物理事件就不再匹配 |
| 帧推进 / 观察窗口 | 足够 | `simulation.advance_frames`（physics 帧，固定 delta）+ `window_frames` |

因此 **没有新增任何 action / observation / signal / 参数**：

- `behavior_protocol.yaml` 仍为 **v2，8 动作 / 10 观测 / 5 信号**，内容零改动；
- `behavior_manifest.json` **未重新生成**，`--check-manifest` 输出 `PASS: manifest matches the protocol`；
- 只复用 Phase 1.43 引入的 `behavior[].scene`（同一 Feature 目录内的相对 `.tscn`）。
  其路径校验保持不变（拒绝绝对路径、`res://`、`.`/`..` 段、非 `.tscn`、缺失文件），
  本阶段额外验证了**跨 Feature 夹具**（`../chase_movement/...`）同样被拒绝。

---

## 4. 证据场景与三个 behavior

### 4.1 为什么必须用证据场景

入口 `ConditionGate.tscn` 只有一个 `Node` 根：既没有条件输入源，也没有下游。
只用它只能声明「没有条件就什么都不发生」——而**失效的门控同样什么都不发生**，
这正是 1.43 已经识别过的假 PASS 陷阱。因此三条行为都使用同目录夹具。

### 4.2 夹具 `Features/condition_gate/ConditionGateFixture.tscn`

```
ConditionGateFixture (Node2D)
├── Gate     (ConditionGate, condition_count=2, aggregation=All)
├── SwitchA  (TriggerSwitch, Latching, (-100,0))
├── SwitchB  (TriggerSwitch, Toggle,   ( 100,0))
└── Door     (OpenableDoor, (0,200), start_open=false)

SwitchA.activated -> Gate.set_condition  binds=["a"]
SwitchB.activated -> Gate.set_condition  binds=["b"]
Gate.fulfilled    -> Door.set_open
```

- 连接写法与 `Scenes/EscapeRoom.tscn` 完全一致：**没有胶水脚本、没有内部回调调用**。
- `SwitchB` 用 `Toggle` 才能表达「条件回落」；`SwitchA` 保持默认 `Latching`，
  确保回落只由单个条件引起，而不是两个条件同时变化。
- 场景只提供条件源与下游，不预设门控结论：`Gate` 的初始状态由组件自身 `_evaluate` 得出。

### 4.3 逐条结果（真实 Godot，2 次重放）

| behavior | actions | 帧预算 | 实测 | 重放 |
| --- | --- | --- | --- | --- |
| `partial_conditions_block_output` | overlap(SwitchA) + 6 帧 | 6+10=16 | SwitchA=true, SwitchB=false, door=false, `state_changed`=0 | 2/2 一致 |
| `all_conditions_fulfill` | overlap(A) + 6 + overlap(B) + 6 | 12+10=22 | A=true, B=true, door=true, `state_changed`=1 (`[true]`) | 2/2 一致 |
| `condition_fallback_withdraws_output` | overlap(A)+6, overlap(B)+6, overlap(B)+6 | 18+10=28 | A=true, B=false, door=false, `state_changed`=2 (`[false]`) | 2/2 一致 |

- 三次行为在动作完成后 **当帧即满足**（`waited_frames=0`、`first_observed_frame=0`），
  因为动作序列末尾的 `advance_frames 6` 已经让物理事件与信号链完整发生；
  观察窗口仍保留 10 帧，用于「事件迟到时也不会误判」。
- `all_conditions_fulfill` 与 `condition_fallback_withdraws_output` 的**最终状态相同**
  （door 关闭），只有事件次数/最后一次参数不同；这正是本阶段不能只看终态的原因
  （见 §5）。

---

## 5. PASS / MISMATCH / INSUFFICIENT 的判定依据

- **PASS**：`action_executed=true`、每条 check 在窗口内满足、2 次重放的关键结果
  （status / reason / 动作是否执行 / 每条 check 的 expected+observed+status）一致。
  三次行为的 PASS 都同时包含「输入已送达」（`trigger.is_triggered=true`）与
  「输出符合预期」两类断言，不存在只断言终态的情况。
- **MISMATCH**：动作已执行但观测到的状态/信号与契约冲突。
  `partial` 的失败原因稳定为 `state_mismatch`（门被打开），
  输出被阻断时表现为 `signal_mismatch`（计数 0 < 2）。
- **INSUFFICIENT**：观察目标/前置条件不可用（`check_unavailable` / `precondition_unmet`）
  或动作无法执行（`action_unavailable`），永不降级为 PASS。
- 「条件始终不满足」不会被当作正确：`partial` 的期望里同时要求**条件源确实被触发**，
  因此条件源不可达时是 MISMATCH（§6 第 4 项），不是 PASS；
  而「输出被阻断」这类**不产生变化**的缺陷由 `all_conditions_fulfill` /
  `condition_fallback_withdraws_output` 捕获（§6 第 3 项）。

---

## 6. 负向对照

缺陷全部注入在**隔离工作区副本**（`BehaviorWorkspace` 的 `Features` 副本）里，
每次注入后立即按字节恢复并核对 SHA256。

| # | 注入方式 | 预期 | 实际（分类 / 退出码） | 恢复 |
| --- | --- | --- | --- | --- |
| 1 | 删除 All 分支的 `condition_count > _states.size()` 检查（阈值被忽略） | 条件不足也不该 PASS | `partial` → **MISMATCH / state_mismatch**（door=true, 信号 1）；`all` 仍 PASS；CLI `--feature` → **exit 1** | 脚本 SHA256 复原 |
| 2 | 删除夹具中 `SwitchB.activated -> Gate.set_condition` 连接（输入断开） | 条件齐备无法达成 | `all` → **MISMATCH**（SwitchB=false, door=false）；`partial` 仍 PASS | 夹具 SHA256 复原 |
| 3 | `if met != _is_fulfilled:` → `if met != _is_fulfilled and false:`（输出信号被阻断） | 不得 PASS | `all` → **MISMATCH**；`fallback` → **MISMATCH / signal_mismatch**（0 vs 2）；`partial` 仍 PASS（该行为不期待任何输出） | 脚本 SHA256 复原 |
| 4 | 夹具把 `SwitchB.target_group` 改为 `enemies`（条件源真实不可达） | 窗口耗尽 → 不得 PASS | `all` → **MISMATCH**（SwitchB=false、door=false、信号 0）；`partial` 仍 PASS | 夹具 SHA256 复原 |
| 5 | 把夹具节点 `SwitchA` 改名（观测目标消失） | 有依据的 INSUFFICIENT | `partial` → **INSUFFICIENT / precondition_unmet**（前置状态 `UNAVAILABLE`）；`all` → **INSUFFICIENT / precondition_unmet**；`fallback` → **INSUFFICIENT / action_unavailable**（动作目标不可解析）；**没有任何 behavior 变 PASS** | 夹具 SHA256 复原 |
| 6 | 契约期望目标 `Absent`（观测不可用） | INSUFFICIENT | **INSUFFICIENT / check_unavailable**，check 状态 `UNAVAILABLE` | 仅临时契约，无文件改动 |
| 7 | `scene: ../chase_movement/ChaseTargetFixture.tscn` / 绝对路径 / `res://` / 缺失 / 非 `.tscn` | INVALID | 5/5 **INVALID**（`relative path inside` / `scene not found` / `.tscn`） | 仅临时契约 |
| 8 | 未声明动作 `condition_gate.set_condition` | 拒绝执行 | **INVALID**（未知动作），不会退化为任意方法调用 | 仅临时契约 |

说明：

- 第 4 项是对「观察窗口耗尽」的适用形式：动作已执行、窗口用满 10 帧仍不满足 →
  `MISMATCH`（协议 v2 的 `timing.timeout` 语义），**不是** `INSUFFICIENT`、更不是 PASS。
  本 Feature 的判定点是帧内事件，构造不出「需要更多帧才能证明」的自然场景，
  因此没有人为制造延迟来伪造该对照。
- 第 3 项的 `partial` 仍 PASS 是**契约范围**问题而非漏洞：该行为不期待任何输出，
  输出被阻断与「门控未达成」在观测上等价；同一缺陷由另外两条行为稳定捕获，
  失败集合不是「全部一起失败」，可以定位到具体契约。

---

## 7. 回归结果与计数口径

| 检查 | 结果 |
| --- | --- |
| 新增 `condition_gate` 行为测试 | **53/53 PASS** |
| 行为证据测试 `test_feature_behavior_evidence.py` | **162/162 PASS**（1.43 为 145，新增 17 = 3 行为 × 5–6 条） |
| 协议一致性 `test_behavior_protocol_consistency.py` | **100/100 PASS**（1.43 为 96，新增 condition_gate 覆盖断言） |
| 1.43 追逐 `test_chase_movement_behavior.py` | **31/31 PASS**（行为未改） |
| 1.42 `test_behavior_time_driven.py` | **72/72 PASS**（行为未改） |
| 行为 CLI `--all --require-behavior --replay 2` | **17/17 PASS**（pass=17 mismatch=0 insufficient=0 invalid=0），exit 0 |
| 协议清单 `behavior_protocol.py --check-manifest` | PASS：v2，actions 8 / observations 10 / signals 5 |
| 完整 `run_tests.py` | **93/93 PASS**（Godot 38 + Python 55），exit 0，无 INCOMPLETE |
| 静态 Validator | **0 error / 17 warning**，与 1.43 完全一致（全部为既有 `assets/...` 缺失路径），**无新增 warning** |

计数口径（不得相加）：

- 93 = 测试**文件**数；Godot 38 + Python 55。Python 55 含本阶段新增 1 个文件；
  `scene_composer` 段由 24 变为 **25**（`run_tests.py` 文档已同步）。
- 上面各「独立套件」数字是**断言**数，只描述该套件自身，不能与 93 相加。
- 1.40 的 6 个 behavior、1.42 的 6 个、1.43 的 2 个全部仍在同一 CLI 运行中
  被检查并 PASS（17 = 6 + 6 + 2 + 3）。

---

## 8. SHA256 恢复验证与工作区清理

本阶段结束时的仓库文件摘要（`sha256`）：

```
a72ca024507c46b56c2681817d4f95d95ca1057297b28f065a94b52c4a9763ef  Features/condition_gate/condition_gate.gd
2c7155feffdf2e09e118127e606dc95797d43a17873a68a593451ebe8e982d22  Features/condition_gate/ConditionGateFixture.tscn
f9cd41a77bc90d61470a0b98995b858f8b39f072b38353537a5303d2a798b5ef  Features/condition_gate/template.yaml
f309097bf7388a456266e884d2cf93d6a48c74730397514873ac00ef8435b4bc  .ai/context/behavior_protocol.yaml
1f3a0c7f33bbe7d3a86cc2edd90213e86e20035a5fadc5b52bfbb4f48e445f4e  .ai/tools/scene_composer/probes/behavior_manifest.json
```

- 测试在每个注入点前后比较 `condition_gate.gd` / 夹具 / `template.yaml` 的 SHA256，
  8 次注入全部按字节恢复；仓库文件从未被写入。
- 测试同时断言 `behavior_protocol.yaml` 与 manifest 未被改动
  （协议仍为 v2、8/10/5），与 `--check-manifest` 结果一致。
- 隔离工作区：`.ai/tmp/behavior/workspace-*` 计数为 **0**（每个 CLI/测试运行结束时删除）；
  `.ai/tmp/behavior/<run_id>/` 证据目录保留，供追溯，位于 git 忽略路径下。
- e2e 产物：`git status` 中没有 `Scenes/E2eProbe*.tscn`、`Tests/e2e_death_victory_probe.gd`、
  `Tests/test_e2e_probe_enemy.gd` 等生成物；Godot 用例数保持 38，与 1.43 稳态一致。
- 未 commit、未 push、未 stash；`HEAD` 仍为 `1c30f94`。

---

## 9. 本阶段没有验证的能力 / 不能据此得出的结论

- **AtLeast 聚合**：本阶段三个行为只覆盖默认 `All`。`AtLeast` 的「至少 N 个」动态重评
  仍只有组件自测（`test_condition_gate.gd`）覆盖，未进入 evidence 契约。
- **`reset()`**：可观测（清空后广播 false），但需要能触发场景级重置的合法动作；
  当前协议没有重置动作，因此未纳入，也没有为此新增能力。
- **幂等性**：重复上报同值不广播，需要同一 `toggle switch` 重复上报相同值；
  `physics.overlap` 每次生成新实体、必然翻转，无法自然构造，故未纳入。
- **`condition_count` 的其它取值**（0/1/3…）、`condition_count` 与已上报数量不一致的边界
  组合：只验证了 `count=2` 且两个条件都上报的正常路径。
- **多实例 / 多次触发下的时序**：只验证单实例、单次达成与单次回落。
- **不能得出**的结论：不证明任意 N 条件组合、任意触发源（按键、计时器、脚本上报）
  都能正确门控；不证明输出信号不会在其它场景抖动；不证明 `condition_gate`
  在组合场景（如 `Scenes/EscapeRoom.tscn`）中的整链行为——本阶段只证明
  「真实接触 → 聚合 → 下游」这一条链路在证据夹具上可复现、可重放、可被缺陷证伪。
