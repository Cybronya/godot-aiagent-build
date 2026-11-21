# Feature 行为证据覆盖矩阵（Phase 1.49 建立；1.50 / 1.51 更新）

> Phase 1.63 补记（2026-11-04，HEAD `dd3a0e4`）：逐行为绑定已覆盖**整个动态支持集**
> （23 Feature / 60 Behavior，全部经显式审批 + Ed25519 签名登记；BND-005 因 M04
> 契约修复被 SUPERSEDED，由 BND-TRIGGER_SW-LATCH_ONCE 顶替）。八维覆盖快照
> （Evidence / Signature / Attestation 8/60，Evaluation 5/60，Holdout 1/60，
> L5 Mutation Killed 9/60，Fully Covered 0/60）以
> `.ai/context/coverage_matrix.md` 为准，由 `evaluation/coverage_matrix.py`
> 动态生成——本文件不再手抄逐 Behavior 状态。

> Phase 1.60 补记（2026-11-03，HEAD `dd3a0e4`）：在 L4 证据之上新增**逐行为绑定层**。
> 正式支持集动态读取（`template.yaml#behavior`，60 行为）；其中 **6 个行为**已有
> 契约级逐行为绑定（`validator/bindings/behavior_bindings.json`，BND-001…006：
> collect_pickup/collect_on_contact、health/damage、save_game×2、
> trigger_switch/latch_once、openable_door/open），expected 逐项来自正式契约且
> 不宽于契约（漂移由契约内容摘要检测）；**其余 54 个行为如实未绑定**。
> 4 条编排场景 Golden Trace（waves/holdout/boss×2）保持 `SCENARIO_ONLY`，
> 不作为逐行为 Golden Trace 依据（`evidence_eval.py` 报告的
> `binding_reconciliation` 块为动态对账事实源）。

> 口径说明：本文件只记录**当前仓库里能跑出什么证据**，不记录「计划要做什么」。
> 每一行都可以用列出的命令重新生成结论；矩阵中的任何 `PASS` 都必须能对应到
> 具体的契约文件、测试文件和退出码，不接受「有个测试文件存在」作为依据。
>
> 生成日期：2026-10-27（Phase 1.51）。基线 HEAD：`1c30f94`（分支 `master`；工作区有未提交修改，
> 见 `PHASE_1_49_AUDIT.md` §1；本行由 `PHASE_1_50_AUDIT.md` §1.3 与 `PHASE_1_51_AUDIT.md` §1 逐字核对）。

---

## 1. 证据层级（矩阵里的每一列对应一层，层与层不能互相顶替）

| 层 | 名称 | 判定来源 | 能证明什么 | 不能证明什么 |
| --- | --- | --- | --- | --- |
| L1 | 静态结构检查 | `Features/<id>/template.yaml` 的 `validation.required_nodes`、`interfaces`，由 `template_loader.py` / `check_feature_metadata.py` 校验 | 声明与入口 `.tscn`、`feature.yaml` 的文本一致 | 运行时会真的加载成这个样子 |
| L2 | 静态实例证据 | `template.yaml#instance`（`node_type` / `children`）+ `instance_evidence.py` 对账 | 声明的节点结构与 `.tscn` 文本一致 | 加载后的真实对象树 |
| L3 | 运行时实例证据 | 同上 `instance.runtime` → `runtime_instance_evidence.py` → `probes/instance_runtime_probe.gd`（真实加载 + 稳定 2 帧） | Godot 真实加载后的对象树符合声明 | 组件行为正确 |
| L4 | 行为契约 | `template.yaml#behavior` → `feature_behavior_evidence.py` → `probes/feature_behavior_probe.gd`（真实动作 + 真实 physics 帧 + 重放 2 次） | 在真实运行时里，动作导致的状态/信号符合契约 | 契约之外的边界（未声明的行为） |
| L5 | 负向对照 | 隔离副本内注入缺陷 → 期望判定（`MISMATCH` / `INSUFFICIENT` / `INVALID`）→ 逐字节恢复 | 契约**能拒绝**错误实现，而不是只会 PASS | 与注入无关的其它缺陷 |
| L6 | 组合场景验收 | `.ai/context/composite_scenes/<id>.yaml` → `composite_behavior_evidence.py` → `probes/composite_behavior_probe.gd`（逐字白名单场景） | 多个 Feature 在真实场景里的**链路**行为 | 场景里未被断言的段落 |

补充约定（与协议文件一致，不是本文件新造）：

- 行为的「真实动作」判定来自 `feature_behavior_evidence.py` 的记录字段
  `action_executed` 与每条动作的 `executed: true`；`state.set_property` 夹具不计入真实动作。
- 重放一致性由 `replay_count == 2` 且 `replay_consistent == True` 表示；不一致是
  `INSUFFICIENT/replay_inconsistent`，不会降级成 PASS。
- 观察不到时状态是 `INSUFFICIENT`（`check_unavailable` / `action_unavailable` /
  `precondition_unmet` / `evidence_unavailable`），**不是** PASS。
- Phase 1.57 起，L4 的「真实执行」不再只靠采集侧自报：Validator 会打开每条 behavior 每次
  重放的 `result.json`（`evidence_paths`），独立重算执行标识、重放条数与序号、动作是否真的
  执行、观测是否等于证据 `actual[]`、重放一致性，并校对产物 sha256（`artifact_digests`）。
  本表里的 L4 结论以 `validator/check_behavior_evidence.py` 的交叉验证通过为前提；矩阵中
  任何 L4 行都可用 `--behavior-evidence` 复核（见 `PHASE_1_57_COMPLETION_REPORT.md`）。

---

## 2. 状态定义（互斥，比 Phase 1.45 更严）

| 状态 | 本文件采用的判定规则 |
| --- | --- |
| `VERIFIED` | 声明的每条 behavior 都在真实运行时执行（L4）、replay 2 一致 PASS，**且**该 Feature 至少有一条针对自身的缺陷注入证明测试会拒绝错误实现（L5） |
| `PARTIAL` | 有真实运行时行为证据与重放，但**缺少针对该 Feature 的缺陷注入**，或已声明的边界明显未覆盖 |
| `UNIT_TESTED` | 没有行为契约，只有 Feature 级 Godot 单元测试（真实运行时，但不是行为证据） |
| `NOT_COVERED` | 没有任何可用的正式证据 |
| `INSUFFICIENT` | 尝试过验证，但当前能力拿不到足够证据（有明确阻塞原因） |

> **与 Phase 1.45 的差异（必须说明）**：1.45 的 `RUNTIME_VERIFIED` 只要求「有运行时证据且重放一致」，
> 因此把 `health` / `collect_pickup` / `heal_pickup` / `player_movement` 也记为通过。
> 本阶段按题目要求「不得仅凭一次 PASS 判定 VERIFIED」把 **L5（能否拒绝错误实现）** 纳入 `VERIFIED`
> 的必要条件，这 4 个 Feature 因此降为 `PARTIAL`。**这是口径加严，不是回归**：它们的运行时证据没有变差，
> 变的是「PASS 能说明什么」的判据。

---

## 3. 覆盖矩阵（12 个正式 Feature）

枚举来源：`Features/*/feature.yaml`（目录枚举，不是行为 CLI 的输出）。
合计声明 **32 条 behavior**（Phase 1.45 时 17 条；1.47 +3、1.49 +5、1.50 +5、1.51 +2，
另强化 1 条已有契约的信号参数断言）。

| # | Feature | L2 静态实例 | L3 运行时实例 | L4 行为契约（条） | 真实动作 | L5 本 Feature 缺陷注入 | 重放×2 | L6 组合场景 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `chase_movement` | 未声明 | 未声明 | 2 | 是（帧推进 + 真实位移） | **2**（冻结追击 / 无目标漂移） | 一致 | `slime_contact`（敌人不动，未被激励） | `VERIFIED` |
| 2 | `collect_pickup` | 有 | 有（PASS） | 1 | 是（`physics.overlap`） | 无 | 一致 | 无 | `PARTIAL` |
| 3 | `condition_gate` | 未声明 | 未声明 | 3 | 是（overlap → 聚合） | **2**（阈值失效 / 条件输入断开） | 一致 | `escape_room` | `VERIFIED` |
| 4 | `contact_damage` | 未声明 | 未声明 | 3 | 是（overlap → 真实节拍） | **1**（伤害调用被移除） | 一致 | `slime_contact` | `VERIFIED` |
| 5 | `heal_pickup` | 有 | 有（PASS） | 1 | 是（`physics.overlap`） | 无 | 一致 | 无 | `PARTIAL` |
| 6 | `health` | 未声明 | 未声明 | **5** | 是（`take_damage` / `heal`） | **8**（数值 / 治疗上限 / 事件参数×2 / 事件次数 / 下限钳制 / 守卫×2） | 一致 | `slime_contact` | `VERIFIED` |
| 7 | `health_bar` | 未声明 | 未声明 | **5** | 是（`take_damage` / `heal` → 真实显示比例） | **3**（公式错 / 恒满 / 绑定拆掉） | 一致 | 无 | `VERIFIED` |
| 8 | `moving_platform` | 有 | 有（PASS） | 2 | 是（帧推进） | **3**（不动 / 单向 / 周期） | 一致 | 无 | `VERIFIED` |
| 9 | `openable_door` | 有 | 有（PASS） | 1 | 是（`door.set_open`） | **3**（no-op / 反向 / 入口移除） | 一致 | `escape_room`、`survival_arena` | `VERIFIED` |
| 10 | `player_movement` | 有 | 有（PASS） | 2 | 是（`input.press/release`） | 无 | 一致 | `escape_room`、`slime_contact` | `PARTIAL` |
| 11 | `stun` | 未声明 | 未声明 | **5** | 是（受击 → 真实停摆） | **5**（暂停/恢复/受击判定/死亡守卫/幂等） | 一致 | 无（`slime_contact` 未含 Stun） | `VERIFIED` |
| 12 | `trigger_switch` | 有 | 有（PASS） | 2 | 是（`physics.overlap`） | **2**（发信号不改状态 / 观测入口移除） | 一致 | `escape_room`、`survival_arena` | `VERIFIED` |

统计：`VERIFIED` **9**、`PARTIAL` **3**、`UNIT_TESTED` **0**、`NOT_COVERED` **0**、`INSUFFICIENT` **0**。

> Phase 1.51 后：12 个正式 Feature **全部**拥有正式行为契约；其中 9 个有「能拒绝错误实现」的
> 缺陷注入证据，3 个只有运行时证据与重放（缺口是负向对照，不是行为证据）。
>
> **基线口径**：本矩阵评估的是 Phase 1.51 当时的 **12** 个正式 Feature（HEAD `1c30f94` → `5d585e4`）。
> 自 `a851ce2` 起，并行工作流新增 `screen_shake` / `hit_flash`（`Features/` 现为 **14** 个），
> 本矩阵**尚未评估**这两个 Feature 的任何一层证据；它们的计数与索引同步问题
> 已在 `PHASE_1_51_AUDIT.md` §6.2.1 登记（与本阶段的 health 证据无关）。
>
> **口径提醒**：本表 L5 列只统计“被契约检出的注入”。`health` 在 Phase 1.51 还跑了一个
> **不被任何契约检出**的注入（`_ready()` 硬编码初始值），它不计入 L5 的 8，而是记入 §6 的缺口清单。

---

## 4. 逐 Feature 可追溯依据

行号指当前工作区文件；命令都在仓库根目录执行。

### 4.1 `chase_movement` — `VERIFIED`

- 契约：`Features/chase_movement/template.yaml:34-`（`approach_target` :38、`hold_without_target` :56），
  专用证据场景 `Features/chase_movement/ChaseTargetFixture.tscn`。
- 证据：`python .ai/tools/scene_composer/tests/test_chase_movement_behavior.py` → 31 PASS；
  `feature_behavior_evidence.py --all` 中转出 `PASS`。
- 负向对照：同一测试 Case 2（追击失效 → `approach_target` `MISMATCH` 而 `hold_without_target` 仍 PASS；
  空闲漂移 → 反向命中）；Case 3（目标配置错误 → `MISMATCH`）；Case 4（观测目标不可解析 →
  `INSUFFICIENT/check_unavailable`）。
- 缺口：未声明 `instance`（L2/L3 空）；`slime_contact` 里 `ChaseMovement.target_path` 为空，
  因此**组合层没有激励追击**，敌人不动是被断言的现状而不是缺陷。

### 4.2 `collect_pickup` — `PARTIAL`

- 契约：`Features/collect_pickup/template.yaml:40` → `collect_on_contact`（`physics.overlap` 生成真实接触体，
  断言节点 freed 与 `pickup.collected` 次数）。
- 证据：L2/L3 有（`instance:` 声明 + `runtime_instance_evidence.py` PASS=6 之一）；
  行为证据 PASS 且 replay 一致。
- 缺口：**没有**任何针对本 Feature 的缺陷注入。断言本身可证伪（节点未释放 / 信号不多发都会失败），
  但「实现变坏时测试会抓到」没有被证明过。这是本 Feature 未能升为 `VERIFIED` 的唯一原因。

### 4.3 `condition_gate` — `VERIFIED`

- 契约：`Features/condition_gate/template.yaml:28-`（3 条），证据场景 `ConditionGateFixture.tscn`。
- 证据：`test_condition_gate_behavior.py` → **53 PASS**（本阶段修复后重跑；修复内容见 §6）。
- 负向对照：Case 2（忽略 `condition_count` → 部分条件用例 `MISMATCH`；条件输入被断开 → 全条件用例
  `MISMATCH`；输出信号被阻断 → 两条用例分别 `MISMATCH`）；Case 3（条件源不可达 → `MISMATCH`）；
  Case 4（观测不可解析 → `INSUFFICIENT`）。
- 组合层：`escape_room` 第 2/3 段（部分条件保持关门 → 全部条件开门）。

### 4.4 `contact_damage` — `VERIFIED`（Phase 1.47 建立）

- 契约：`Features/contact_damage/template.yaml:50-`（`damage_on_contact` :51、`no_damage_without_contact` :63、
  `damage_amount_is_respected` :75），证据场景 `ContactDamageFixture.tscn`（含 `damage=3` 的第二实例，
  用来证明「配置的伤害量被尊重」而不是「生命值变了」）。
- 证据：`test_contact_damage_behavior.py` → 39 PASS。
- 负向对照：Case 2（移除伤害调用 → `MISMATCH/state_mismatch`，且伤害量契约同时失败）；
  Case 3（观测目标缺失 → `INSUFFICIENT`；5 帧窗口看不到 0.5 s 节拍 → `MISMATCH`）。
- 组合层：`slime_contact` 的接触段（见 §5）。

### 4.5 `heal_pickup` — `PARTIAL`

- 契约：`Features/heal_pickup/template.yaml:39` → `heal_damaged_target`（先把目标打到 3/5，再 overlap，
  断言回到 4 且拾取物 freed）。
- 证据：L2/L3 有；行为证据 PASS。
- 缺口：无缺陷注入（同 4.2 的理由）。

### 4.6 `health` — `VERIFIED`（Phase 1.51 建立负向证据）

- 契约：`Features/health/template.yaml#behavior`，5 条：`damage`、`heal_clamped`、`death`
  （Phase 1.40）、`overkill_clamps_at_zero`、`post_death_guard`（Phase 1.51）；
  入口场景即证据场景（`Health.tscn`，`max_health` 取默认 5）。
- 证据：CLI `--feature health --replay 2` → **5/5 PASS / exit 0**；
  `test_health_behavior.py` → **104 PASS / 0 FAIL / exit 0**（≈76 s）。
  全部 5 条 `action_executed=True`、无夹具动作、`waited_frames=0`（同步语义，不靠窗口等待）。
- 负向对照（9 类注入，隔离副本逐字节恢复）：**8 类被检出**，并且每类都记下了失败落在哪一层：
  `damage` 数值少扣 1（`state_mismatch`）、治疗上限钳制被移除（`heal_clamped`/`state`）、
  扣血事件参数颠倒（`signal`）、治疗事件参数错误（`signal`）、`died` 触发两次（`signal`）、
  伤害下限钳制被移除（`overkill_clamps_at_zero`/`state`）、`take_damage` 死亡守卫被移除
  （`post_death_guard`/`signal`）、`heal` 死亡守卫被移除（`post_death_guard`/`state`）。
  每类都同时断言了“相邻契约仍通过”（例如 2f 只打穿 `overkill`，`damage`/`death` 照旧 PASS）。
- **1 类未被检出（真实缺口，如实记录）**：把 `_ready()` 的初始化硬编码成 5、忽略 `max_health` 配置。
  仓库里没有任何契约在 `max_health != 5` 的场景上跑，所以 5 条契约全部 PASS——该注入"全部 PASS"
  本身就是证据，不是通过。
- 其余边界（未覆盖，事实）：伤害量 0/负数在**行为证据层不可表达**（协议把 `health.take_damage` / 
  `health.heal` 的参数域声明为 `1..100`，0/-3/101 一律 `INVALID`），只由 Godot 单元测试覆盖；
  `max_health` 运行期变更无观测也无夹具（`properties` 未声明 `health.max_health`）。

### 4.7 `health_bar` — `VERIFIED`（Phase 1.50 建立）

- 契约：`Features/health_bar/template.yaml` 的 `behavior:`，5 条：
  `initial_health_bar_ratio`、`damage_updates_health_bar`、`healing_updates_health_bar`、
  `death_empties_health_bar`、`unbound_bar_reports_no_fill`；证据场景 `HealthBarFixture.tscn`
  （`Host/Health(max 10)` + `Host/Bar` 已绑定 + `Orphan` 未绑定）。
- 观测：`health_bar.ratio`（Phase 1.50 新增的**只读**观测，读 `get_ratio()`；
  `_draw()` 用它算填充宽度，除此之外没有变换）。
- 证据：`python .ai/tools/scene_composer/tests/test_health_bar_behavior.py` → **65 PASS / exit 0**；
  5 条行为均 `replay=2 consistent`，实测值 1.0 / 0.6 / 0.8 / 0.0 / 0.0（未绑定），`waited_frames=0`。
- 负向对照（3 类，均逐字节恢复）：比例公式忘了除 max（→10.0）/ 比例恒为 1.0 / 绑定被拆掉（→0.0）。
- **已登记的边界**：本组件不缓存显示值（`_draw` 现算），Godot 也不提供「是否重绘过」的只读查询，
  所以「重绘时机」与真实像素不可观测；`health_changed` 断连只会造成 stale 像素，**读比例看不出来**。
  可观测的等价缺陷是「血条不再跟随 Health」（绑定被拆），已被注入检出。细节见 `PHASE_1_50_AUDIT.md` §6.4。

### 4.8 `moving_platform` — `VERIFIED`

- 契约：`Features/moving_platform/template.yaml:41-`（`travel` :42 60 帧 ≈100 px；`round_trip` :54 240 帧回原点）。
- 负向对照：`test_behavior_time_driven.py` Case 6（不移动 → `MISMATCH`；单向运动 → `travel` 仍 PASS 而
  `round_trip` `MISMATCH`——证明对照本身有分辨力；`period=400` → 窗口看不到运动 → `MISMATCH` 而非 PASS）。
- 证据：`test_behavior_time_driven.py` → 72 PASS；L2/L3 有。

### 4.9 `openable_door` — `VERIFIED`

- 契约：`Features/openable_door/template.yaml:40` → `open`（`door.set_open(true)` + 后置状态 + 信号一次）。
- 负向对照：`test_feature_behavior_evidence.py` Case 11（no-op → `MISMATCH/state_mismatch` 且满窗口；
  `_apply(false)` → `MISMATCH` 且观测值 false；删入口 → `INSUFFICIENT/action_unavailable`）；
  `test_behavior_protocol_consistency.py` Case 9 复现 no-op 缺陷。
- 组合层：`escape_room`（门确实挡住玩家 / 开门后可通行）、`survival_arena`（开关 → 双门）。

### 4.10 `player_movement` — `PARTIAL`

- 契约：`Features/player_movement/template.yaml:47-`（`move_right` :48 12 帧 ≈44 px；`stop_on_release` :61
  松开后位移不再变化）。
- 证据：行为证据 PASS；`escape_room` 与 `slime_contact` 都在真实输入下驱动玩家移动（间接的行为验证）。
- 缺口：无缺陷注入（例如「松开后仍滑动」「速度翻倍」都没有被证明会被抓到）。

### 4.11 `stun` — `VERIFIED`（本阶段建立）

- 契约：`Features/stun/template.yaml:37-`，5 条：
  `hit_stuns_and_freezes_host` :39、`stun_expires_and_host_resumes` :60、`heal_does_not_stun` :79、
  `death_guard_rejects_stun` :97、`reentry_extends_without_rebroadcast` :116。
- 证据场景：`Features/stun/StunFixture.tscn`（`Host` = `player_controller.gd` 的 CharacterBody2D +
  `Health(10)` + `Stun(stun_on_hit=true, stun_duration=0.4)`）；入口 `Stun.tscn` 未被改动。
- 触发方式：只用 `health.take_damage`，经 `Health.health_changed → stun_on_hit 订阅 → call_deferred` 的
  真实链路；**不调用 `stun()` 方法**（那会绕过被测的触发逻辑）。
- 观测：`node2d.displacement`（宿主是否真的停摆）、`health.current`（受击量）、
  `signal` + `stun.stunned`（跨越广播次数与参数）。
- 证据：`python .ai/tools/scene_composer/tests/test_stun_behavior.py` → **70 PASS / exit 0**；
  5 条行为均 `replay=2 consistent`。
- 负向对照：同测试 Case 2（5 类注入，逐字节恢复）；Case 3（观测缺口）；Case 4（重放不一致）；
  Case 5（非法契约）；Case 6（CLI 退出码 + 副本恢复）。明细见 `PHASE_1_49_AUDIT.md` §6。

### 4.12 `trigger_switch` — `VERIFIED`

- 契约：`Features/trigger_switch/template.yaml:41-`（`latch_once` :42、`toggle_on_second_contact` :57，
  后者用 `state.set_property` 夹具切 Toggle 模式——属白名单属性，不算真实动作）。
- 负向对照：`test_behavior_time_driven.py` Case 6（发信号但不改状态 → `MISMATCH`；
  `is_triggered` 入口移除 → `INSUFFICIENT`）。
- 组合层：`escape_room`（两个开关）、`survival_arena`（奖励开关同时驱动双门）。

---

## 5. 组合场景（L6）与 Feature 的映射

| 场景（逐字白名单） | 契约 | 覆盖的 Feature 链 | 证据 |
| --- | --- | --- | --- |
| `Scenes/EscapeRoom.tscn` | `composite_scenes/escape_room.yaml`（4 段） | `player_movement` → `trigger_switch` ×2 → `condition_gate` → `openable_door` ×2 → 通行 | `test_composite_behavior_evidence.py` 100 PASS；`composite_behavior_evidence.py --all` 4/4 |
| `Scenes/SlimeContactArena.tscn` | `composite_scenes/slime_contact.yaml`（3 段） | `player_movement` → （`chase_movement` 实例）→ `contact_damage` → `health`（玩家） | `test_slime_contact_arena.py`；CLI 3/3 |
| `Scenes/SurvivalArena.tscn` | `composite_scenes/survival_arena.yaml`（2 段） | `trigger_switch` → `openable_door` ×2 | 同上，2/2 |

未进入任何组合场景的 Feature：`collect_pickup`、`heal_pickup`、`moving_platform`、`health_bar`、`stun`。
其中 `moving_platform` / `stun` / `health_bar` 的单 Feature 证据已充分（`VERIFIED`），
缺的是「与其它组件的交互」这一类证据（`health_bar` 在 `Scenes/Enemy.tscn` 里是 HealthBar 的实例，
但没有任何组合契约去看它；这是下一步可选项，不是当前缺口）。

---

## 6. 已知弱断言与证据缺口（按严重度排序）

1. **`health_bar` 的像素/重绘时机不可观测**：本组件不缓存显示值，Godot 也没有「是否重绘过」的
   只读 API，所以 `health_changed` 断连（stale 像素）在当前实现下无法通过任何只读手段检出。
   要补这一类证据，必须让组件暴露显示缓存或重绘计数——那是组件/架构决策，不是测试能自己解决的。
2. **3 个 `PARTIAL` 缺缺陷注入**：`collect_pickup`、`heal_pickup`、`player_movement`。
   `health` 已于 Phase 1.51 补齐（见 §4.6）；下一个最值得补的是 `player_movement`
   （输入是组合场景的地基，速度/松键语义一旦坏掉，`escape_room`/`slime_contact` 会以别的形态失败）。
3. **组合场景的三个已知盲区**（不是本阶段引入，也不是本阶段修掉）：
   - `survival_arena` 的**通行段**不可重放（`_enemy_spawn_offset()` 随机刷怪会挡住玩家，Phase 1.46 §7 记录）；
     本阶段未尝试、也未放宽该断言。
   - `slime_contact` 不覆盖玩家死亡（10 点生命 × 1/0.5 s 需要 5 s 推进）与敌人受击。
   - `escape_room` 不覆盖玩家被门夹住、`ConditionGate` 的 `Repeat` 模式等边界。
4. **协议能表达的观测仍然只有 12 项**：任何「读某个私有 getter」的契约都必须先扩协议，这是
   有意的成本（防止治理层被绕过）。`health_bar.ratio` 是 Phase 1.50 唯一的增量（只读、无参数写入）；
   Phase 1.51 **未动协议**，能力表逐项不变（8 动作 / 12 观测 / 7 信号 / 1 属性）。
5. **`stun` 未进入组合场景**：`SlimeEnemy.tscn` 目前不含 Stun；把它加进正式敌人属于游戏设计变更，
   本阶段不做（见 `PHASE_1_49_AUDIT.md` §7）。
6. **`health` 的初始值配置不可观测**（Phase 1.51 实测，不是推测）：把 `_ready()` 里的
   `_current_health = max_health` 硬编码成 `= 5`，5 条契约**全部 PASS**——因为仓库里每一条
   health 契约都跑在 `max_health` 为默认值 5 的场景上。要补这条，需要先有一个
   `max_health != 5` 的证据场景（例如 `Features/health/HealthFixture.tscn`，与 `HealthBarFixture`
   同构），或者声明一个 `health.max_health` 只读观测；两者都不在本阶段范围内，**本阶段按缺口记录**。

---

## 7. 下一阶段建议（按本矩阵的证据缺口，不是按代码量）

1. **给 3 个 `PARTIAL` 补缺陷注入**：优先 `player_movement`（松键后仍滑动、速度常量被改），
   其次 `collect_pickup` / `heal_pickup`（同为 `physics.overlap` 触发，注入方式可参考 `contact_damage`）。
   另：`health` 的初始值缺口（§6 第 6 条）需要先做**证据场景或只读观测**的决定，不要用夹具硬写。
2. **`stun` 的组合位置**（可选）：如果设计上敌人需要硬直，应在*设计*层面决定是否给
   `SlimeEnemy.tscn` 加 Stun，再加组合契约；不要为了让证据好看而改场景。

---

## 附：一次性复核命令（可复制）

```bash
# L4 全部 32 条行为（重放 2 次，缺证据即报 INSUFFICIENT 并被 --require-behavior 判失败）
python .ai/tools/scene_composer/feature_behavior_evidence.py --all --require-behavior --replay 2
# L3 运行时实例证据（6 个声明 Feature）
python .ai/tools/scene_composer/runtime_instance_evidence.py --all
# L6 三个组合场景
python .ai/tools/scene_composer/composite_behavior_evidence.py --all --require-composite --replay 2
# 单个 Feature 的行为契约
python .ai/tools/scene_composer/feature_behavior_evidence.py --feature stun --replay 2
# L5 health 的缺陷检出能力（9 类注入 + 正向证据 + 逐字节恢复 + CLI）
python .ai/tools/scene_composer/tests/test_health_behavior.py
```

---

## 附：Phase 1.52 增量（code_library 批量资产，2026-10-28）

> 本节为增量记录，不重写上方按 Phase 1.51 基线生成的矩阵。复核命令同上（`--all`
> 现在覆盖 49 条行为，不是 32 条）。

**新增带行为契约的 Feature（6 个，均为「片段 → Feature」流水线产物，出处见各 README）：**

| Feature | 行为契约数 | 证据场景 | 备注 |
| --- | --- | --- | --- |
| cooldown | 3 | Cooldown.tscn（组件即根） | 新动作 `cooldown.start`、新观测 `cooldown.is_ready` |
| screen_shake | 2 | ScreenShakeFixture.tscn | 新动作 `screenshake.add_trauma`；断言只落在 shaking(bool) 信号跨越，不断言噪声偏移 |
| hit_flash | 3 | HitFlashFixture.tscn | 复用 health.take_damage；新信号登记 `hitflash.flashing` |
| i_frames | 3 | IFramesFixture.tscn | 全程既有词汇（health 门控事件计数）；夹具必须实例化 IFrames.tscn（Cooldown 子节点必需） |
| projectile | 3 | ProjectileHit/FreeFlight Fixture.tscn | 位移断言用 node2d.displacement；销毁断言用 node.exists==false（node.freed 对已释放子节点解析为 UNAVAILABLE） |
| patrol_movement | 3 | PatrolLoop/PingPong Fixture.tscn | 新信号登记 `patrol.waypoint_reached`；观察期 = 动作帧 + window + settle，断言帧数按此换算 |

**协议词汇增量（behavior_protocol.yaml，计数 8→10 动作 / 12→13 观测 / 7→13 信号）：**

- 动作：`cooldown.start`、`screenshake.add_trauma`（均为组件公开方法调用，与 door.set_open 同型）
- 观测：`cooldown.is_ready`
- 信号登记：`cooldown.started/finished`、`screenshake.shaking`、`hitflash.flashing`、`patrol.waypoint_reached`、`projectile.finished`
- 组合探针（composite_behavior_probe.gd）同步实现新动作/观测（组合协议允许项一致性要求）

**探针行为修正（Phase 1.52）：**

- 信号观测在目标节点已释放时改按**连接期 watch_key**（target|signal 组合键）读取事件
  ——自释放型组件（projectile finished 后 queue_free）的终止信号是真实观测而非
  UNAVAILABLE；此前 node.freed 对已释放**子节点**同样退化为 UNAVAILABLE，销毁断言
  请用 `node.exists == false`（协议明确支持节点缺失语义）。

---

## 附：Phase 1.53 增量（code_library 批量资产第二批，2026-10-30）

**新增带行为契约的 Feature（3 个）：**

| Feature | 行为契约数 | 证据场景 | 备注 |
| --- | --- | --- | --- |
| state_machine | — | StateMachineBehaviorFixture.tscn | 新动作 `statemachine.start/transition_to`、新观测 `statemachine.current_state_name`、新信号 `statemachine.state_changed` |
| save_game | — | SaveGameBehaviorFixture.tscn | 新动作 `savegame.save_slot/load_slot`、新观测 `savegame.last_slot`、新信号 `savegame.game_saved/game_loaded` |
| attack_emitter | — | AttackEmitterFixture.tscn | 新动作 `attackemitter.do_attack`、新信号 `attackemitter.attack_hit` |

## 附：Phase 1.54 增量（code_library 批量资产第三批，2026-10-30）

**新增带行为契约的 Feature（2 个）：**

| Feature | 行为契约数 | 证据场景 | 备注 |
| --- | --- | --- | --- |
| knockback | 3 | KnockbackFixture.tscn（CharacterBody2D 根 + Knock） | 新动作 `knockback.apply`、新信号 `knockback.changed`；位移断言复用 node2d.displacement（离散帧和 = F²/(2D) + F·dt/2 = 38px，固定物理帧确定） |
| sfx_pool | 2 | SfxPoolFixture.tscn（Node 根 Pool） | 新动作 `sfx.play`（探针内部构造静音 AudioStreamWAV）、新观测 `sfx_pool.active_count`、新信号 `sfx.played`；占用断言依赖 headless 确定性（finished 不触发 → 簿记只增不减，直到抢占） |

**协议词汇增量（behavior_protocol.yaml，计数 15→17 动作 / 15→16 观测 / 17→19 信号）：**

- 动作：`knockback.apply`（params: dir_x/dir_y/force 标量）、`sfx.play`（stream 由探针构造，协议参数是标量无法表达流对象）
- 观测：`sfx_pool.active_count`（自管簿记是 headless 下唯一确定的占用读法）
- 信号登记：`knockback.changed`、`sfx.played`（无载荷——协议 args 只允许 bool/int/string，含对象载荷的组件信号不改协议语义）
- 组合探针（composite_behavior_probe.gd）补齐 1.53 全部 5 动作/2 观测 + 1.54 全部 2 动作/1 观测（两端能力一致性）

## 附：Phase 1.56 增量（L4 证据接入 Validator，2026-11-01）

**本阶段没有新增任何 Feature、行为契约或证据层级。** 变化的只是 L4 证据的**去向**：
此前 `feature_behavior_evidence.py` 的结论只打印在终端（`PASS`/`MISMATCH`/...），
Validator 与 Evaluation 都读不到；现在 L4 证据可以落盘为带完整性摘要的证据包，并由
Validator 的独立阶段重新判定。

| 事项 | 事实 |
| --- | --- |
| 采集侧 | `scene_composer/feature_behavior_evidence.py --evidence-out DIR` → `feature_behavior_evidence_bundle`（schema_version 1），`evidence_level: L4`，含每条 check 的 `expected` / `observed` / `observed_args` / 重放次数与一致性 / 证据路径 |
| 复核侧 | `validator/check_behavior_evidence.py`（`validate.py --behavior-evidence`，默认不执行）；用 `template.yaml#behavior` 重算，不采信证据自报 `status` |
| 真实实测（2026-11-01，HEAD `dd3a0e4`） | 采集：23 Feature / **60 条行为** `pass=60 mismatch=0 insufficient=0 invalid=0`；复核：`Behavior evidence (L4): PASS (bundles=1, features=23, pass=60, fail=0, incomplete=0)`，`validate.py` 退出码 0 |
| 完整性 | 证据包 `integrity.payload_sha256`（规范化 JSON，排除 `integrity` 自身）；篡改一条真实观测 → `FAIL integrity mismatch`（实测）；删除一条行为记录并重签 → `INCOMPLETE behavior_uncovered`（实测） |
| 等级纪律 | 只复核 L4。证据包声明 L2/L5 → `FAIL`（实测）；本阶段**不为任何 Feature 声明 L5** |

各 Feature 的 L2/L3/L4/L5/L6 状态与本文件 §3 一致，**未因本阶段变化**：
L5（缺陷注入）仍只有 `health` 等已列出的 Feature 具备；`PARTIAL` 仍是 `PARTIAL`。
`PASS (L4)` 只表示「契约声明的行为在真实运行时符合」，不等于 `VERIFIED`。

未解决的信任边界：哈希能发现生成后的改动，**不能**证明来源可信（同一权限下改实现再重签
即可绕过）。该边界在 `PHASE_1_56_COMPLETION_REPORT.md` §7 显式记录，未声称已解决。

```bash
# 采集 + 复核（Phase 1.56 全链路）
python .ai/tools/scene_composer/feature_behavior_evidence.py --all --evidence-out .ai/tmp/behavior_bundles
python .ai/tools/validator/validate.py --behavior-evidence --evidence-dir .ai/tmp/behavior_bundles
```

---

## Phase 1.58：证据 → 评估 的对账（2026-11-03，真实运行）

证据「存在且有效」不等于「被评估过」。这一节只记录**本轮真实跑出来的**集合关系，
数字都可用下面命令复现（`.ai/tmp/p158/bundles` 为 2026-11-03 真实采集，8 条行为全 PASS）：

```bash
python .ai/tools/scene_composer/feature_behavior_evidence.py \
  --feature collect_pickup --feature health --feature save_game \
  --evidence-out .ai/tmp/p158/bundles --bundle-id p158-real
python .ai/tools/evaluation/evidence_eval.py --evidence-dir .ai/tmp/p158/bundles
```

| 集合 | 数量 | 口径 |
| --- | --- | --- |
| 支持集（契约声明） | 60 | `declared_features()` = 23 Feature，`build_contracts()` = 60 Behavior，动态读取 |
| 证据集（本轮采集） | 8 | collect_pickup 1 + health 5 + save_game 2 |
| 评估集（任务覆盖） | 5 | E1 `collect_on_contact`、E2 `damage`、E3 两条 save 行为、E4 `latch_once` |
| Golden Trace 集 | 0 | 4 个已批准基线只有场景级绑定，无 Feature/Behavior 对应 → `NOT_APPLICABLE` |
| Holdout 集 | 0 | E5 未提供独立批次 → `NOT_EVALUATED(holdout_unavailable)`，不计为通过 |

有证据但**没有**对应评估任务（如实登记，未补任务凑数）：`health/death`、
`health/heal_clamped`、`health/overkill_clamps_at_zero`、`health/post_death_guard`。

本轮真实结论：`VERIFIED_PASS=4`（E1–E4），Mode B 的 E4 由本次采集产生证据后同样经
Validator 复核；`VETO` 路径实测可用——同一批真实证据 + 更严期望 → `VERIFIED_FAIL`；
证据包篡改 → `INVALID_EVIDENCE`。报告：`.ai/tmp/eval/10856-84242ddd/evidence_report.json`。

**注意**：此处 `VERIFIED_PASS` 只覆盖 5/60 条行为，不代表整体行为质量已验收；
其余 55 条行为既未评估、也未在本轮采集，状态是 `NOT_EVALUATED`，不是 PASS。

---

## Phase 1.59：L5 缺陷注入扩展（2026-11-03，真实 Godot 运行）

上文 §3 的 L5 列来自 Phase 1.51（只覆盖 `health` 的 9 类注入，注入方式为一次性脚本）。
本阶段把它做成**可重复、可审计的 mutation harness**：`evaluation/mutation/` 在 `Features/` 的
隔离副本里按 catalog 注入一处真实缺陷 → 真实采集 → 现有 Validator + Evaluation 判定 →
逐字节恢复 → 再跑一次。仓库 `Features/**` 全程只读（每次 run 比对哈希）。

**判定纪律**：`INVALID_MUTANT`（注入没造成预期行为变化）**不计入** killed/survived 分母，
也不为本 Feature 增加 L5 覆盖；`NOT_RUN`（哈希过期/未声明）不等于通过。

| # | Feature / Behavior | 缺陷类型 | 关键观测（control → mutant） | 判定 |
| --- | --- | --- | --- | --- |
| M01 | `health` / `damage` | 状态更新遗漏（不扣血只发信号） | `health.current` 1 → 5 | `MUTANT_KILLED` |
| M02 | `health` / `post_death_guard` | 生命周期守卫缺失 | `health.health_changed` count 1 → 2 | `MUTANT_KILLED` |
| M03 | `collect_pickup` / `collect_on_contact` | 资源释放遗漏 | `node.freed` true → false | `MUTANT_KILLED` |
| M04 | `trigger_switch` / `latch_once` | 状态锁存守卫移除 | `trigger.activated` 1 → 1（无差异） | `INVALID_MUTANT` |
| M05 | `openable_door` / `open` | 事件广播遗漏 | `door.state_changed` 1 → 0 | `MUTANT_KILLED` |
| M06 | `save_game` / `save_slot_persists_world_state` | 持久化记录遗漏 | `savegame.last_slot` 相同（`user://` 残留） | `INVALID_MUTANT` |
| M07 | `save_game` / `load_slot_restores_world_state` | 持久化读取遗漏 | `World/Player/Health.current` 3 → 1 | `MUTANT_KILLED` |
| M08 | `trigger_switch` / `latch_once` | 状态转移写错值 | `trigger.is_triggered` true → false | `MUTANT_KILLED` |

**本轮真实结论**：8 条注入 / 6 条 `MUTANT_KILLED`（5 Feature、6 Behavior）/ 2 条 `INVALID_MUTANT` /
0 `SURVIVED` / 0 `HARNESS_ERROR` / 0 `TIMEOUT` / 0 `NOT_RUN`。每条 KILLED 都伴随
control `VERIFIED_PASS` 与 recovery `VERIFIED_PASS`（逐字节恢复后再跑一次仍 PASS）。

因此 L5 的**新增可信覆盖**是 5 个 Feature / 6 条 Behavior：`health/damage`、
`health/post_death_guard`、`collect_pickup/collect_on_contact`、`openable_door/open`、
`save_game/load_slot_restores_world_state`、`trigger_switch/latch_once`。其余 18 个 Feature
（53 条 Behavior）**本阶段未做 L5**，状态仍是 `NOT_EVALUATED`，不是 PASS。

**两条 INVALID_MUTANT 暴露的是探针/契约的分辨力缺口（不是「没检出」）**：

- M04：删掉 Latching 分支的 `if _triggered: return` 后，契约里第二次 `physics.overlap`
  不再产生第二次 `body_entered`，那行守卫在真实执行里根本没被走到 → 观测完全相同。
- M06：`user://saved_games/_last.txt` 跨 run 残留（control 那次写下的记录），mutant「忘记记录」
  时回读到的仍是上次的值 → 该契约对「忘记记录」没有分辨力。

两条都如实记为 `INVALID_MUTANT` 并保留在 catalog 里作为**待补探针**的凭据，未通过改期望、
改证据或改实现来「凑成」KILLED。

---

## Phase 1.64：系统性扩大覆盖（Batch 1，2026-11-04，真实 Godot）

Phase 1.63 建立了八维对账，但 60 条 Behavior 里只有 8 条有证据。本阶段做的是**扩大真实覆盖**，
不是改口径：新增 4 条 Evidence/Signature/Attestation/Evaluation，新增 1 个 Fully Covered。

| Feature / Behavior | 类型 | Evidence | Signature | Attestation | Evaluation | Mutation |
| --- | --- | --- | --- | --- | --- | --- |
| `save_game/save_slot_persists_world_state` | C | ✅（重跑复核） | ✅ | ✅ | ✅ | KILLED（M06） |
| `save_game/load_slot_restores_world_state` | C | ✅（重跑复核） | ✅ | ✅ | ✅ | KILLED（M07） |
| `i_frames/iframes_block_damage_within_window` | F | ✅ **新增** | ✅ | ✅ | ✅ | KILLED（M09） |
| `i_frames/iframes_expire_and_damage_resumes` | A | ✅ **新增** | ✅ | ✅ | ✅ | KILLED（**M11 新增**） |
| `i_frames/killing_blow_still_dies` | F | ✅ **新增** | ✅ | ✅ | ✅ | 无（待补） |
| `openable_door/open` | A+B | ✅ **新增** | ✅ | ✅ | ✅ | KILLED（M05/M12） |

- 全库口径（分母 60）：Evidence/Signature/Attestation/Evaluation **12/60（20%）**、
  L5 Mutation Killed（Behavior 数）**10/60（17%）**、Holdout 1/60、
  **Fully Covered 1/60（1.7%，`openable_door/open`）**。
- 其余 **48 条无证据、50 条无 mutation、59 条无 Holdout**：状态仍是 `NOT_EVALUATED` / `NOT_TESTED`，
  **不是 PASS**。
- 两条新 mutation 的意义：M11 是 M09（开窗没关门）的互补面（到期没归还门）；
  M12 是「语法完全合法、只在行为上错」的守卫反转——两者都只有真实执行才能发现。
- 本阶段未改 `Features/**`、未改契约、未改绑定；`openable_door` 的 Holdout 来自 1.63，未重封。
