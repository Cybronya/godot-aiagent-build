# Phase 1.68.1 — Contract Observation Gap Audit

日期：2026-11-09
阶段：Phase 1.68.1（**只读审计**；未进入 1.68.2）
Git：**未 commit / push / reset / clean**；HEAD `54169659`，暂存区为空。
Godot：`4.7.stable.official.5b4e0cb0f`（`F:\Godot_v4.7-stable\Godot_v4.7-stable_win64_console.exe`）。

> 本报告只回答一个问题：**为什么场景已经真实执行并通过自身 Evaluation，却仍无法达到官方契约 Fully Covered？**
> 所有数字都在当前工作区重新读取 Registry/契约/证据后计算，不沿用 1.67.1/1.67.2 的假设。
> 审计期间未生成场景、未执行 Godot 场景、未生成 Evidence、未改任何 Registry/契约/代码，未做 Git 写操作。

---

## 1. Baseline（重新核实）

### 1.1 仓库与环境

| 项 | 实测值 | 说明 |
| --- | --- | --- |
| HEAD | `54169659` | `git rev-parse --short HEAD` |
| 暂存区 | 0 项 | `git diff --cached --name-only` 为空 |
| 工作区未提交变更 | 审计前 1094；审计后 1095 | 本报告是唯一新增文件 |
| Godot | `4.7.stable.official.5b4e0cb0f` | `env_paths.find_godot_binary()` → `--version` |
| 信任级别 | `LOCAL_ISOLATED` | 来自 `scenario_results.json` |

### 1.2 动态支持集与契约

| 项 | 数量 | 来源 |
| --- | --- | --- |
| Feature | 23 | `Features/*/template.yaml#behavior` |
| Behavior / Contract | **60 / 60** | `paths.supported_behaviors()` + `feature_behavior_evidence.build_contracts()` |
| Contract 检查项（expected） | **145** | 每条 Behavior 的 `expected[]` 去重后求和 |
| 非法契约 | 0 | `build_contracts` 无 `INVALID` 报告 |
| 已注册 Observation 类型 | 16 | `behavior_protocol.yaml#observations`，全部 `implemented: true` |
| 已注册 Signal | 19 | `behavior_protocol.yaml#signals` |
| 已注册 Action | 17 | `behavior_protocol.yaml#actions` |

检查项按类型分布：

| 检查类型 | 数量 |
| --- | --- |
| `signal` | 52 |
| `health.current` | 29 |
| `node2d.displacement` | 23 |
| `trigger.is_triggered` | 8 |
| `health.is_dead` | 7 |
| `health_bar.ratio` | 6 |
| `node.exists` | 5 |
| `door.is_open` | 4 |
| `cooldown.is_ready` | 3 |
| `node.freed` | 2 |
| `sfx_pool.active_count` | 2 |
| `statemachine.current_state_name` | 2 |
| `node2d.position` | 1 |
| `savegame.last_slot` | 1 |
| **合计** | **145** |

**Observation Definition 结论：145/145 的检查类型与 signal entry 都有已注册、已实现的观测定义；本轮未发现 A 类“没有观测能力”的检查项。** 这不等于这些检查项被真实观测过——见 §2。

### 1.3 场景、执行与证据

| 项 | 实测值 |
| --- | --- |
| Scenario | **9**（P4 5 + P5 4） |
| Scenario Validation | **9/9 VALID** |
| 真实执行 | **9/9 PASSED**，0 FAILED / 0 BLOCKED |
| Evidence | **9/9 `EVIDENCE_VERIFIED`** |
| Attestation | **9/9 `ATTESTED_VERIFIED`** |
| 场景 Evaluation | **9/9 `VERIFIED_PASS`** |
| 官方契约判定 | **1 PASS / 3 FAIL / 5 INCOMPLETE** |
| 官方契约 PASS 的 Behavior | **1/60**（`openable_door/open`） |
| 官方检查项被真正裁决 | **4/145**（2 PASS + 2 行为性 FAIL；另有 1 个表示性 FAIL，见 §2.3） |

每条 P4/P5 证据的采集侧事实一致：`action_executed=true`、`replay_count=2`、`replay_consistent=true`、`waited_frames=0`（所有检查在动作帧即满足；动作本身已推进帧）。这不是“没执行”，而是“执行了，但只观测了场景自己声明的检查”。

### 1.4 Coverage Matrix（canonical 输入）

以 `coverage_matrix.py` 的默认输入（`DEFAULT_EVIDENCE_DIRS` = p163/p160/p161、默认 eval 目录 `.ai/tmp/eval`、默认 runs = p163）在内存中运行：

| 维度 | 值 |
| --- | --- |
| Contract | 60/60 |
| Approved Binding | 60/60 |
| Evidence Verified | 8/60 |
| Signature Verified | 8/60 |
| Attestation Verified | 8/60 |
| Evaluation VERIFIED_PASS | 9/60 |
| Holdout Available | 1/60 |
| Mutation Killed | 9/60 |
| **Fully Covered** | **0/60** |

两个必须写明的口径事实：

1. **Approved Binding 已是 60/60**，不是旧文档 `FEATURE_BEHAVIOR_COVERAGE.md` 里的 6/60；本审计以当前 `binding_candidates.binding_gate_status` 为准。Binding 不是当前的覆盖瓶颈。
2. **P4/P5 的 9 个证据包不在 canonical evidence 目录**（它们在 `.ai/tmp/p166/evidence`），因此 canonical 矩阵的 `evidence_verified=8` 不包含这 9 条。把 p166 证据显式加入后，`evidence_verified` 变为 9。
3. **矩阵的 `evaluation` 维度与场景 Evaluation 不是同一套东西**：它读取 `.ai/tmp/eval/*/evidence_report.json` 的任务结果，不读取 `scenario_results.json`。因此 P5 的 9/9 `VERIFIED_PASS` 对 `fully_covered` **没有贡献**。

### 1.5 一个必须记录的可复现性异常

在“p166 证据 + 默认 eval 目录 + p166 runs”组合下，矩阵曾报告 `fully_covered=1`（`openable_door/open`）。追查发现：该行使用的是一条 **P2 期、HEAD `dd3a0e4d`** 的评估报告 `.ai/tmp/eval/8264-b57a4950/evidence_report.json`，其 `P166-16F6576C8683F7BC` 任务为 `VERIFIED_PASS`，于是把 openable_door 的 evaluation 维度补满；而 canonical 输入不含 p166 evidence，所以 canonical 仍是 0/60。

这说明 `evaluation_dimension()` 的“取最新 mtime 报告”策略对输入目录与历史报告敏感；`Fully Covered` 不是仅由当前 HEAD 的官方契约 PASS 决定。该异常不作为覆盖提升，作为**矩阵可复现性缺口**记录。

### 1.6 与任务书基线的差异

| 任务书 | 实测 | 结论 |
| --- | --- | --- |
| HEAD `54169659` | `54169659` | 一致 |
| Behavior 60 | 60 | 一致 |
| 场景链 9/60 | 9 | 一致 |
| 官方 Fully Covered 0/60 | 0/60（canonical） | 一致 |
| P5 4/4 执行/证据/Attestation/场景 Eval | 4/4 全部一致 | 一致 |
| P5 官方 1 FAIL / 3 INCOMPLETE | 一致 | 一致 |

---

## 2. Contract Observation Matrix（全部 145 项）

### 2.1 计算口径

- `Scenario declared`：该检查的 `(check,target,entry)` 是否出现在该 Behavior 的场景 `expected_observations` 中（按键匹配，不按位置）。
- `Evidence observed`：该检查的 `(check,target,entry)` 是否出现在该 Behavior 的 Evidence `actual[]` 中。
- `Attested`：该 Behavior 的证据包/运行是否有通过验证的 Attestation；**这是行为级，不是逐检查级**。
- `Official eval`：用 `check_behavior_evidence.judge_record(record, official_contract)` 的判定。`NOT_DECIDED` 表示条数不匹配、判定器在比较值之前就返回 INCOMPLETE；`NOT_REACHED` 表示前一项已失败，判定器提前返回；`NOT_RUN` 表示没有任何场景/证据。
- `Status`：`DECIDED_PASS` / `DECIDED_FAIL` / `NOT_DECIDED` / `NOT_REACHED` / `NO_SCENARIO`。

### 2.2 汇总

| 指标 | 数量 |
| --- | --- |
| Contract 总数 | 60 |
| Contract 检查项总数 | 145 |
| Observation 定义存在 | **145** |
| 场景声明（官方键） | **16** |
| Evidence 真实观测（官方键） | **16** |
| Attestation 覆盖的官方检查（行为级） | **19**（9 个 Behavior） |
| 官方判定 PASS | **2** |
| 官方判定 FAIL | **3**（其中 1 个是顺序/表示性 FAIL） |
| 官方判定 NOT_DECIDED | **10** |
| 官方判定 NOT_REACHED | **4** |
| 从未进入任何场景 | **126** |
| 无法判定（145 − 2 PASS − 3 FAIL） | **140** |

> “Attested 19”不等于“19 个检查被验证”：Attestation 只证明运行/产物/证据摘要，不证明官方检查项被采集或满足。

### 2.3 完整矩阵

| # | Behavior | Contract check | Target / entry | Expected | Obs defined | Scenario declared | Evidence observed | Attested | Official eval | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `attack_emitter/raycast_hit_deals_damage` | `health.current` | `Target/Health` | `=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 2 | `attack_emitter/raycast_hit_deals_damage` | `signal` | `Emitter:attackemitter.attack_hit` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 3 | `attack_emitter/repeated_attack_can_kill` | `health.current` | `Target/Health` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 4 | `attack_emitter/repeated_attack_can_kill` | `health.is_dead` | `Target/Health` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 5 | `attack_emitter/repeated_attack_can_kill` | `signal` | `Target/Health:health.died` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 6 | `chase_movement/approach_target` | `node2d.displacement` | `Chaser` | `range=57.5..62.5` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 7 | `chase_movement/approach_target` | `node2d.displacement` | `Chaser` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 8 | `chase_movement/approach_target` | `node2d.position` | `Target` | `=300.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 9 | `chase_movement/approach_target` | `node.exists` | `Chaser` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 10 | `chase_movement/hold_without_target` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 11 | `chase_movement/hold_without_target` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 12 | `collect_pickup/collect_on_contact` | `node.freed` | `.` | `=True` | YES | YES | YES | YES | FAIL | DECIDED_FAIL |
| 13 | `collect_pickup/collect_on_contact` | `signal` | `.:pickup.collected` | `count=1` | YES | YES | YES | YES | NOT_REACHED | NOT_REACHED |
| 14 | `condition_gate/all_conditions_fulfill` | `trigger.is_triggered` | `SwitchA` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 15 | `condition_gate/all_conditions_fulfill` | `trigger.is_triggered` | `SwitchB` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 16 | `condition_gate/all_conditions_fulfill` | `door.is_open` | `Door` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 17 | `condition_gate/all_conditions_fulfill` | `signal` | `Door:door.state_changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 18 | `condition_gate/condition_fallback_withdraws_output` | `trigger.is_triggered` | `SwitchA` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 19 | `condition_gate/condition_fallback_withdraws_output` | `trigger.is_triggered` | `SwitchB` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 20 | `condition_gate/condition_fallback_withdraws_output` | `door.is_open` | `Door` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 21 | `condition_gate/condition_fallback_withdraws_output` | `signal` | `Door:door.state_changed` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 22 | `condition_gate/partial_conditions_block_output` | `trigger.is_triggered` | `SwitchA` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 23 | `condition_gate/partial_conditions_block_output` | `trigger.is_triggered` | `SwitchB` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 24 | `condition_gate/partial_conditions_block_output` | `door.is_open` | `Door` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 25 | `condition_gate/partial_conditions_block_output` | `signal` | `Door:door.state_changed` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 26 | `contact_damage/damage_amount_is_respected` | `health.current` | `@actor/Health` | `=2` | YES | NO | NO | YES | NOT_DECIDED | NOT_DECIDED |
| 27 | `contact_damage/damage_amount_is_respected` | `signal` | `@actor/Health:health.health_changed` | `count=1` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 28 | `contact_damage/damage_on_contact` | `health.current` | `@actor/Health` | `=4` | YES | NO | NO | YES | NOT_DECIDED | NOT_DECIDED |
| 29 | `contact_damage/damage_on_contact` | `signal` | `@actor/Health:health.health_changed` | `count=1` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 30 | `contact_damage/no_damage_without_contact` | `health.current` | `@actor/Health` | `=5` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 31 | `contact_damage/no_damage_without_contact` | `signal` | `@actor/Health:health.health_changed` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 32 | `cooldown/cooldown_blocks_during_window` | `cooldown.is_ready` | `.` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 33 | `cooldown/cooldown_blocks_during_window` | `signal` | `.:cooldown.started` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 34 | `cooldown/cooldown_expires_and_notifies` | `cooldown.is_ready` | `.` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 35 | `cooldown/cooldown_expires_and_notifies` | `signal` | `.:cooldown.started` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 36 | `cooldown/cooldown_expires_and_notifies` | `signal` | `.:cooldown.finished` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 37 | `cooldown/restart_resets_remaining_window` | `cooldown.is_ready` | `.` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 38 | `cooldown/restart_resets_remaining_window` | `signal` | `.:cooldown.started` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 39 | `cooldown/restart_resets_remaining_window` | `signal` | `.:cooldown.finished` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 40 | `heal_pickup/heal_damaged_target` | `health.current` | `@actor/Health` | `=4` | YES | NO | NO | YES | NOT_DECIDED | NOT_DECIDED |
| 41 | `heal_pickup/heal_damaged_target` | `node.freed` | `.` | `=True` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 42 | `health/damage` | `health.current` | `.` | `=1` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 43 | `health/damage` | `signal` | `.:health.health_changed` | `count=1` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 44 | `health/death` | `health.current` | `.` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 45 | `health/death` | `health.is_dead` | `.` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 46 | `health/death` | `signal` | `.:health.died` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 47 | `health/heal_clamped` | `health.current` | `.` | `=5` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 48 | `health/heal_clamped` | `signal` | `.:health.health_changed` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 49 | `health/overkill_clamps_at_zero` | `health.current` | `.` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 50 | `health/overkill_clamps_at_zero` | `health.is_dead` | `.` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 51 | `health/overkill_clamps_at_zero` | `signal` | `.:health.health_changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 52 | `health/post_death_guard` | `health.current` | `.` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 53 | `health/post_death_guard` | `health.is_dead` | `.` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 54 | `health/post_death_guard` | `signal` | `.:health.died` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 55 | `health/post_death_guard` | `signal` | `.:health.health_changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 56 | `health_bar/damage_updates_health_bar` | `health.current` | `Host/Health` | `=6` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 57 | `health_bar/damage_updates_health_bar` | `health_bar.ratio` | `Host/Bar` | `=0.6` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 58 | `health_bar/damage_updates_health_bar` | `signal` | `Host/Health:health.health_changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 59 | `health_bar/death_empties_health_bar` | `health.current` | `Host/Health` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 60 | `health_bar/death_empties_health_bar` | `health.is_dead` | `Host/Health` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 61 | `health_bar/death_empties_health_bar` | `health_bar.ratio` | `Host/Bar` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 62 | `health_bar/healing_updates_health_bar` | `health.current` | `Host/Health` | `=8` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 63 | `health_bar/healing_updates_health_bar` | `health_bar.ratio` | `Host/Bar` | `=0.8` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 64 | `health_bar/healing_updates_health_bar` | `signal` | `Host/Health:health.health_changed` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 65 | `health_bar/initial_health_bar_ratio` | `health_bar.ratio` | `Host/Bar` | `=1.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 66 | `health_bar/initial_health_bar_ratio` | `health.current` | `Host/Health` | `=10` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 67 | `health_bar/unbound_bar_reports_no_fill` | `health_bar.ratio` | `Orphan` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 68 | `health_bar/unbound_bar_reports_no_fill` | `health_bar.ratio` | `Host/Bar` | `=1.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 69 | `health_bar/unbound_bar_reports_no_fill` | `health.current` | `Host/Health` | `=10` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 70 | `hit_flash/flash_ends_after_duration` | `signal` | `Host/Flash:hitflash.flashing` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 71 | `hit_flash/heal_does_not_flash` | `health.current` | `Host/Health` | `=10` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 72 | `hit_flash/heal_does_not_flash` | `signal` | `Host/Flash:hitflash.flashing` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 73 | `hit_flash/hit_flashes_host` | `health.current` | `Host/Health` | `=9` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 74 | `hit_flash/hit_flashes_host` | `signal` | `Host/Flash:hitflash.flashing` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 75 | `i_frames/iframes_block_damage_within_window` | `health.current` | `Host/Health` | `=9` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 76 | `i_frames/iframes_block_damage_within_window` | `signal` | `Host/Health:health.health_changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 77 | `i_frames/iframes_expire_and_damage_resumes` | `health.current` | `Host/Health` | `=8` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 78 | `i_frames/iframes_expire_and_damage_resumes` | `signal` | `Host/Health:health.health_changed` | `count=2` | YES | YES | YES | YES | NOT_DECIDED | NOT_DECIDED |
| 79 | `i_frames/killing_blow_still_dies` | `health.current` | `Host/Health` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 80 | `i_frames/killing_blow_still_dies` | `health.is_dead` | `Host/Health` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 81 | `i_frames/killing_blow_still_dies` | `signal` | `Host/Health:health.died` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 82 | `knockback/knockback_applies_and_signals` | `signal` | `Knock:knockback.changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 83 | `knockback/knockback_applies_and_signals` | `node2d.displacement` | `.` | `range=10.0..None` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 84 | `knockback/knockback_applies_and_signals` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 85 | `knockback/knockback_decays_to_rest` | `signal` | `Knock:knockback.changed` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 86 | `knockback/knockback_decays_to_rest` | `node2d.displacement` | `.` | `=38.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 87 | `knockback/knockback_decays_to_rest` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 88 | `knockback/knockback_rejects_invalid` | `signal` | `Knock:knockback.changed` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 89 | `knockback/knockback_rejects_invalid` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 90 | `moving_platform/round_trip` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 91 | `moving_platform/round_trip` | `node.exists` | `.` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 92 | `moving_platform/travel` | `node2d.displacement` | `.` | `range=98.0..102.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 93 | `moving_platform/travel` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 94 | `openable_door/open` | `door.is_open` | `.` | `=True` | YES | YES | YES | YES | PASS | DECIDED_PASS |
| 95 | `openable_door/open` | `signal` | `.:door.state_changed` | `count=1` | YES | YES | YES | YES | PASS | DECIDED_PASS |
| 96 | `patrol_movement/loop_patrol_cycles_waypoints` | `signal` | `.:patrol.waypoint_reached` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 97 | `patrol_movement/outbound_leg_moves_at_constant_speed` | `node2d.displacement` | `.` | `=20.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 98 | `patrol_movement/ping_pong_reverses_at_path_end` | `signal` | `.:patrol.waypoint_reached` | `count=4` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 99 | `player_movement/move_right` | `node2d.displacement` | `.` | `range=43.5..44.5` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 100 | `player_movement/move_right` | `node2d.displacement` | `.` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 101 | `player_movement/stop_on_release` | `node2d.displacement` | `.` | `range=43.5..44.5` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 102 | `projectile/hit_deals_damage_and_expires` | `health.current` | `Target/Health` | `=9` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 103 | `projectile/hit_deals_damage_and_expires` | `node.exists` | `Projectile` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 104 | `projectile/hit_deals_damage_and_expires` | `signal` | `Projectile:projectile.finished` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 105 | `projectile/in_flight_moves_until_lifetime` | `node.exists` | `Projectile` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 106 | `projectile/in_flight_moves_until_lifetime` | `node2d.displacement` | `Projectile` | `=50.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 107 | `projectile/in_flight_moves_until_lifetime` | `signal` | `Projectile:projectile.finished` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 108 | `projectile/lifetime_expiry_frees_projectile` | `node.exists` | `Projectile` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 109 | `projectile/lifetime_expiry_frees_projectile` | `signal` | `Projectile:projectile.finished` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 110 | `save_game/load_slot_restores_world_state` | `health.current` | `World/Player/Health` | `=3` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 111 | `save_game/load_slot_restores_world_state` | `signal` | `Saver:savegame.game_loaded` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 112 | `save_game/save_slot_persists_world_state` | `signal` | `Saver:savegame.game_saved` | `count=1` | YES | YES | YES | YES | FAIL | DECIDED_FAIL |
| 113 | `save_game/save_slot_persists_world_state` | `savegame.last_slot` | `Saver` | `=behavior_save` | YES | YES | YES | YES | NOT_REACHED | NOT_REACHED |
| 114 | `save_game/save_slot_persists_world_state` | `health.current` | `World/Player/Health` | `=3` | YES | YES | YES | YES | NOT_REACHED | NOT_REACHED |
| 115 | `screen_shake/shake_stops_after_decay` | `signal` | `Shake:screenshake.shaking` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 116 | `screen_shake/trauma_starts_shake` | `signal` | `Shake:screenshake.shaking` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 117 | `sfx_pool/sfx_play_emits_and_occupies` | `signal` | `.:sfx.played` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 118 | `sfx_pool/sfx_play_emits_and_occupies` | `sfx_pool.active_count` | `.` | `=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 119 | `sfx_pool/sfx_pool_steals_oldest_when_full` | `signal` | `.:sfx.played` | `count=9` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 120 | `sfx_pool/sfx_pool_steals_oldest_when_full` | `sfx_pool.active_count` | `.` | `=8` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 121 | `state_machine/previous_backtracks_via_history` | `statemachine.current_state_name` | `Machine` | `=idle` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 122 | `state_machine/previous_backtracks_via_history` | `signal` | `Machine:statemachine.state_changed` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 123 | `state_machine/transition_to_named_state` | `statemachine.current_state_name` | `Machine` | `=chase` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 124 | `state_machine/transition_to_named_state` | `signal` | `Machine:statemachine.state_changed` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 125 | `stun/death_guard_rejects_stun` | `node2d.displacement` | `Host` | `range=60.0..80.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 126 | `stun/death_guard_rejects_stun` | `health.current` | `Host/Health` | `=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 127 | `stun/death_guard_rejects_stun` | `health.is_dead` | `Host/Health` | `=True` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 128 | `stun/death_guard_rejects_stun` | `signal` | `Host/Stun:stun.stunned` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 129 | `stun/heal_does_not_stun` | `node2d.displacement` | `Host` | `range=70.0..95.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 130 | `stun/heal_does_not_stun` | `health.current` | `Host/Health` | `=10` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 131 | `stun/heal_does_not_stun` | `signal` | `Host/Stun:stun.stunned` | `count=0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 132 | `stun/hit_stuns_and_freezes_host` | `node2d.displacement` | `Host` | `range=-1.0..8.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 133 | `stun/hit_stuns_and_freezes_host` | `node2d.displacement` | `Host` | `=0.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 134 | `stun/hit_stuns_and_freezes_host` | `health.current` | `Host/Health` | `=9` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 135 | `stun/hit_stuns_and_freezes_host` | `signal` | `Host/Stun:stun.stunned` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 136 | `stun/reentry_extends_without_rebroadcast` | `node2d.displacement` | `Host` | `range=-1.0..8.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 137 | `stun/reentry_extends_without_rebroadcast` | `health.current` | `Host/Health` | `=8` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 138 | `stun/reentry_extends_without_rebroadcast` | `signal` | `Host/Stun:stun.stunned` | `count=1` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 139 | `stun/stun_expires_and_host_resumes` | `node2d.displacement` | `Host` | `range=45.0..100.0` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 140 | `stun/stun_expires_and_host_resumes` | `health.current` | `Host/Health` | `=9` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 141 | `stun/stun_expires_and_host_resumes` | `signal` | `Host/Stun:stun.stunned` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 142 | `trigger_switch/latch_once` | `trigger.is_triggered` | `.` | `=True` | YES | YES | YES | YES | FAIL | DECIDED_FAIL |
| 143 | `trigger_switch/latch_once` | `signal` | `.:trigger.activated` | `count=1` | YES | YES | YES | YES | NOT_REACHED | NOT_REACHED |
| 144 | `trigger_switch/toggle_on_second_contact` | `trigger.is_triggered` | `.` | `=False` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |
| 145 | `trigger_switch/toggle_on_second_contact` | `signal` | `.:trigger.activated` | `count=2` | YES | NO | NO | NO | NOT_RUN | NO_SCENARIO |

**矩阵读法**：126 项从未进入任何场景；10 项有观测但因条数不匹配被判 `NOT_DECIDED`；4 项在前项失败后未到达；3 项被官方判定为 FAIL；2 项 PASS。真正被官方契约“看到并裁决”的只有 4 项行为性检查（door 2 + collect 1 + trigger 1）。

---

## 3. P4/P5 Analysis（逐场景）

### 3.1 九个场景的真实语义

| Scenario | Behavior | Rule | 动作（语义） | 场景期望 | 官方期望 | 官方结果 |
| --- | --- | --- | --- | --- | --- | --- |
| `s-16f6576c8683f7bc` | `openable_door/open` | `idempotent_repeat` | `set_open(true)` ×2 | `is_open=true`；`state_changed` 1 | 同左 | **PASS** |
| `s-37cd4dc9f084950e` | `trigger_switch/latch_once` | `foreign_group_ignored` | 两次 `physics.overlap` 放到 `p166_foreign` | `is_triggered=false`；`activated` 0 | `is_triggered=true`；`activated` 1 | **FAIL** |
| `s-7771e41885fcd58e` | `health/damage` | `post_terminal_input_ignored` | 伤害 4 → 致死伤害 100 → 治疗 1 | `current=0`；`is_dead=true`；`health_changed` 2；`died` 1 | `current=1`；`health_changed` 1 | **INCOMPLETE**（4 vs 2） |
| `s-8b9f108ecb56beb2` | `save_game/save_slot_persists_world_state` | `invalid_slot_rejected` | 伤害 2 → 用非法槽 `p166/invalid:slot` 存档 | `current=3`；`game_saved` 0；`last_slot=""` | `game_saved` 1；`last_slot="behavior_save"`；`current=3` | **FAIL**（check[0] target mismatch：实际顺序 `health.current` 与官方 `signal` 不同） |
| `s-e6eb3fc5c8e82e32` | `i_frames/iframes_expire_and_damage_resumes` | `dependency_postcondition_after_death` | 伤害 10 → 帧 → 伤害 1 → 帧 | `current=0`；`is_dead=true`；`health_changed` 1；`died` 1 | `current=8`；`health_changed` 2 | **INCOMPLETE**（4 vs 2） |
| `s-eef9972034da734b` | `collect_pickup/collect_on_contact` | `foreign_group_ignored` | `physics.overlap` 放到 `p166_foreign` | `node.freed=false`；`pickup.collected` 0 | `node.freed=true`；`pickup.collected` 1 | **FAIL** |
| `s-d2fe30d380537d07` | `contact_damage/damage_on_contact` | `foreign_group_ignored` | `physics.overlap` 放到 `p166_foreign` | `health_changed` 0 | `health.current=4`；`health_changed` 1 | **INCOMPLETE**（1 vs 2） |
| `s-d503c62564c391ef` | `contact_damage/damage_amount_is_respected` | `foreign_group_ignored` | `physics.overlap` 放到 `p166_foreign` | `health_changed` 0 | `health.current=2`；`health_changed` 1 | **INCOMPLETE**（1 vs 2） |
| `s-9efdc90351f7112e` | `heal_pickup/heal_damaged_target` | `foreign_group_ignored` | `physics.overlap`（`damage=3`，`health_max=5`）放到 `p166_foreign` | `node.freed=false` | `health.current=4`；`node.freed=true` | **INCOMPLETE**（1 vs 2） |

### 3.2 关键结论：8/9 场景不可能满足官方契约

这不是“观测没采到”那么简单。除 `openable_door/open` 外，8 个场景的动作或期望与官方契约**方向相反**：

- `foreign_group_ignored` 把接触体放进非目标组，正确结果就是“不拾取、不伤害、不治疗”。官方契约要求“目标组接触后拾取/伤害/治疗”。即使把 `health.current` 也观测了，按场景夹具推断，`contact_damage` 会看到未变化的初始 5（而不是官方的 4/2），`heal_pickup` 会看到初始 3（而不是 4），`collect_pickup` 会看到 `freed=false`（而不是 true）。官方判定会从 INCOMPLETE 变成 **FAIL**，不会变成 PASS（该推断未执行新场景验证）。
- `post_terminal_input_ignored` 追加致死伤害后再输入，官方 `health/damage` 期望 `current=1`、`health_changed=1`；场景实际是 `current=0`、`health_changed=2`。官方判定若按值比较，同样是 FAIL。
- `dependency_postcondition_after_death` 先杀死宿主，官方 `i_frames/iframes_expire_and_damage_resumes` 期望 `current=8`、`health_changed=2`；场景实际是 `0`/`1`。官方判定同样是 FAIL。
- `invalid_slot_rejected` 用非法槽存档，官方 `save_slot_persists_world_state` 期望 `game_saved=1`、`last_slot="behavior_save"`；场景实际是 `0`/`""`。官方判定同样是 FAIL。

因此：**P5 的 3 个 INCOMPLETE 即使补上 `health.current`，也只会得到 3 个 FAIL；P5 的官方覆盖仍不会增加。** `collect_pickup` 的 FAIL 是场景语义的必然结果，不应通过改期望消除。

### 3.3 `collect_pickup` 专项分析

- 官方检查：`node.freed`（`equals: true`）+ `signal pickup.collected`（`count: 1`）。
- 场景动作：`physics.overlap(group="p166_foreign")`，目标组不是 `collect_pickup` 监听的组；守卫 `is_in_group` 会拒绝。
- 实际观测：`node.freed=false`、`pickup.collected=0`；这与场景“外来组不得拾取”的预期完全一致，**不是观测机制错误**。
- 结论：这是**有意差异**（H 类），不是产品缺陷；当前场景没有验证官方正常拾取契约的条件。应使用**独立的正向场景**（目标组）或独立的官方契约执行来验证官方契约，不能改当前场景的期望值。

### 3.4 三个 INCOMPLETE 专项分析

| 项 | 场景声明 | 官方声明 | 实际 | 缺失层级 | 具体依据 |
| --- | --- | --- | --- | --- | --- |
| `contact_damage/damage_on_contact` | `signal health_changed=0` | `health.current=4` + `signal health_changed=1` | 1 条（signal=0） | Generator + Intent | `_rule_foreign_group` 只保留 signal 与 bool，丢弃 `health.current`（`scenario_generator.py:188-196`）；场景 JSON 无官方检查列表 |
| `contact_damage/damage_amount_is_respected` | 同上 | `health.current=2` + `signal=1` | 1 条 | 同上 | 同上 |
| `heal_pickup/heal_damaged_target` | `node.freed=false` | `health.current=4` + `node.freed=true` | 1 条 | 同上 | 同上 |

- 观测能力存在：`health.current` 在 `behavior_protocol.yaml` 注册且 `implemented: true`，探针 `_observe_health_current` 已实现；Phase 1.56 的全量官方采集曾对这三个 Behavior 真实得到 `health.current` 值（`p157-real.json`：4/2/4）。
- 当前 Runner 有能力采集：`run_probe` 会把 contract 的 `expected[]` 原样交给探针；探针 `_evaluate(expected)` 会逐项观测。问题是**没有人把 `health.current` 放进这份 expected**。
- 缺失发生在 **Intent/Generator**，不是 Runner/Evidence：Evidence 忠实保存了探针观测的 1 条；不是“观测了但没存”。
- 同一执行过程能否安全补采？能，但前提是把 `health.current` 加入请求列表；不过由于外来组不会造成伤害，按夹具推断补采后的官方值会是“未变化的初始值”，与官方期望不同 → 官方 FAIL，而不是 PASS。因此补采只解决“可判定性”，不解决“官方覆盖”。（该结论是语义推断，未执行新场景。）

### 3.5 P4 的 5 个场景

| Scenario | 官方结果 | 根因 |
| --- | --- | --- |
| `s-16f6576c8683f7bc` door | PASS | 动作/期望与官方契约一致（幂等重复不改变终态） |
| `s-37cd4dc9f084950e` trigger | FAIL | `foreign_group_ignored` 否定语义；官方期望锁存为 true，场景期望 false（H） |
| `s-7771e41885fcd58e` health/damage | INCOMPLETE | 场景追加致死输入，4 条检查 vs 官方 2 条（H + G 条数门禁） |
| `s-8b9f108ecb56beb2` save | FAIL | 非法槽场景，3 条检查顺序与官方不同（H + G 位置匹配）；值也不同（signal 0 vs 1） |
| `s-e6eb3fc5c8e82e32` i_frames | INCOMPLETE | 死亡依赖场景，4 条 vs 官方 2 条（H + G） |

P4/P5 的 Evidence 本身全部有效：9/9 `action_executed=true`、`replay=2 consistent`，且 `scenario_results.json` 记录为 9/9 `EVIDENCE_VERIFIED` / 9/9 `ATTESTED_VERIFIED`；问题不在采集可信度，而在**采集内容与官方契约不对齐**。

---

## 4. Data Flow Audit

### 4.1 实际链路

```text
Features/*/template.yaml#behavior
        │  build_contracts()  (actions / expected / preconditions / scene)
        ▼
官方契约（60 条，145 checks）
        │
        ├──[路径 A：官方契约采集]── feature_behavior_evidence.py --all
        │        └─ 60/60 PASS（p157-real，HEAD dd3a0e4d），单 bundle，无逐行为 run/attestation
        │
        └──[路径 B：学习场景链]── scenario_generator.py
                 │  规则变换 actions/expected（foreign_group / invalid_slot / post_terminal / …）
                 │  显式跳过 base contract（signature == base_signature）
                 ▼
              Scenario JSON：只有 expected_observations（场景断言）
                 │  scenario_run._contract_from_scenario()
                 ▼
              Probe contract.expected = 场景断言（不是官方断言）
                 │  feature_behavior_probe.gd _evaluate(expected)
                 ▼
              Evidence：expected[] / actual[] 只有场景断言
                 │  scenario_run._verify_and_evaluate()
                 ├─ scenario verdict: judge_record(record, 场景 expected)
                 ├─ official verdict: judge_record(record, 官方 expected)
                 └─ scenario Evaluation: evaluate_expectations(场景 expected, actual)
                 ▼
              scenario_results.json：记录 official_contract_status（只记录，不进入 coverage）
                 │
                 ├─ evidence_eval.py：任务 expect（E1–E5，独立于契约，按键匹配）
                 └─ coverage_matrix.py：读 evidence + eval report + holdout + mutation
```

### 4.2 逐层审计

| 层 | 实现 | 实际携带 | 断点 |
| --- | --- | --- | --- |
| Contract | `feature_behavior_evidence.build_contracts()`（`feature_behavior_evidence.py:410-484`） | 60 条契约、145 checks、actions/preconditions/scene | 无：契约完整、可执行、Observation 类型都有定义 |
| Intent | `scenario_generator._make_scenario()` / Scenario JSON | 只有 `expected_observations`、`actions`、`preconditions` | **没有“官方契约观测组”字段**；场景意图只表达自己的断言 |
| Generator | `scenario_generator.generate_behavior()`（`:430-462`） | 规则变换后的 actions/expected | ① 显式跳过 base contract（`:442-449`）；② `_rule_foreign_group` 丢弃非 bool/signal 检查（`:188-196`）；③ 不生成“官方正向”场景 |
| Observation | `behavior_protocol.yaml`（16 observations / 19 signals / 17 actions）+ probe | 类型与实现齐全 | 能力存在，但**调用方只请求场景断言** |
| Runner | `scenario_run._contract_from_scenario()`（`:135-144`）；`run_probe` | `contract.expected = scenario.expected_observations` | 官方 checks 从未进入探针；官方契约只在执行后用于判定 |
| Evidence | `BehaviorReport.to_dict()`（`:224-245`）；`build_bundle`（`:886-923`） | `expected[]` / `actual[]` 单列表；bundle v1；integrity/签名 | 没有 group/source/observation_id；无法表达“同一执行同时服务两组断言” |
| Attestation | `execution/attestation.py` + manifest | run / 指纹 / artifact digest / evidence_reference | 证明“产物和运行可信”，**不证明官方检查被请求/采集/满足** |
| Evaluation | `scenario_run._verify_and_evaluate()`（`:210-240`）；`evidence_adapter.evaluate_expectations()`（`:503-560`）；`coverage_matrix.evaluation_dimension()`（`:278-307`） | 场景 verdict + 官方 verdict 分别计算；场景 Evaluation 只用场景 expect | ① 场景/官方判定共用同一 `actual`；② 官方 verdict 不进入 coverage；③ 位置/条数门禁；④ feedback 不消费官方 verdict |

### 4.3 八个指定问题

1. **场景断言和官方断言是否混为一套？**
   期望层没有混（两套 expected 分开保存）；**证据/判定层混了**：两者都对同一个 `actual[]` 做位置/条数比较。结果是“场景多一条检查”就会让官方判定 INCOMPLETE，“顺序不同”就会让官方判定 FAIL。
2. **是否只采集场景主动声明的检查项？**
   是。探针只 `_evaluate(expected)`；`actual` 长度等于场景 `expected_observations` 长度。官方检查项若未被场景声明，就不会被观测。
3. **官方检查项是否在生成阶段被丢弃？**
   是。129/145 从未进入任何场景；`_rule_foreign_group` 明确丢弃 `health.current`；`generate_behavior` 明确跳过 base contract。丢弃不是“漏写”，是当前规则的有意筛选。
4. **是否存在 Observation 已采集但 Evidence 未保存？**
   未发现。`actual` 直接来自探针 `checks`，bundle 原样保存；没有“采了但丢”的证据。
5. **是否存在 Evidence 已保存但 Evaluation 无法消费？**
   是，两种形态：
   - 位置/条数门禁：`save_game` 的 3 条检查值都在，但顺序不同 → 官方 FAIL；`health/damage`/`i_frames` 有 4 条 → 官方 INCOMPLETE。
   - 覆盖消费：`scenario_results.official_contract_status` 不进入 `coverage_matrix`；矩阵的 evaluation 维度读 `evidence_report.json`。
6. **是否存在检查时机错误导致观测无效？**
   未发现。9 条场景 `waited_frames=0` 是因为检查在动作帧即满足；动作本身推进了真实帧。负向断言的 `advance_frames(1)` 提供了窗口。没有“在动作前观测”或“窗口不足”的证据。
7. **是否多个检查共享同一观测值？**
   是，但未造成错误：`signal` 的 watch key 按 `target|signal` 登记；同一 target 的多个 signal 共享连接但分别计数。`_evaluate` 的 `first_observed_frame` 缓存键是 `check|target`，不含 `entry`，会让同一 target 的多个 signal 共享首次帧（仅影响 `first_observed_frame` 元数据，不影响 PASS/FAIL）。
8. **是否通过默认值/推断值填补缺失观测？**
   未发现。`expected_holds` 在 `observed is None` 时返回 `None`；`judge_record` 返回 INCOMPLETE；没有用默认值凑 PASS。临时 `health.current` 的“初始值”也没有被写入证据。

### 4.4 两条并行的“官方覆盖”路径

本审计发现一个必须明确的架构事实：

- **路径 A（官方契约采集）** 已经存在且能跑：`feature_behavior_evidence.py --all` 在 HEAD `dd3a0e4d` 采集过 60/60 PASS 的单 bundle（`.ai/tmp/p157/bundles_real/p157-real.json`）。当前 60 条契约与该 bundle 的 expected 60/60 完全一致、actions 59/60 一致（`trigger_switch/latch_once` 的 action 记录有差异）。这证明“官方检查可被真实观测”，但该证据是**旧 HEAD、单 bundle、无逐行为 run/attestation**，不满足当前覆盖矩阵的 7 维要求。
- **路径 B（学习场景链）** 产生 P4/P5 的 9 条真实、逐场景签名/attestation 的证据，但场景语义是“守卫变体”，不是官方契约。

**当前系统没有把路径 A 的官方契约能力接入路径 B 的场景执行。** 这是“官方覆盖不增加”的结构性原因。

---

## 5. Root Cause Classification（A–H）

| 类别 | 是否存在 | 数量/证据 | 说明 |
| --- | --- | --- | --- |
| **A. Observation Definition Gap** | **否（0）** | 145/145 检查类型有定义；16 observations / 19 signals / 17 actions 全部 `implemented: true` | 没有“系统没有观测能力”的检查项 |
| **B. Observation Planning Gap** | **是（主因）** | 129/145 官方检查从未进入任何场景；9 个场景只有 `expected_observations`，无官方观测组 | Intent 不表达官方检查需求；场景只规划自己的断言 |
| **C. Generator Gap** | **是（主因）** | `_rule_foreign_group` 丢弃 `health.current`（P5 3 条）；`generate_behavior` 跳过 base contract（所有 60 条）；0 个官方正向场景 | 生成器把“新规则变体”当作唯一目标；base 被当重复而排除 |
| **D. Runner Gap** | **是（后果）** | 探针只接收场景 expected；129 项官方检查没有进入 `contract.json` | Runner 有能力采，但请求清单来自场景；不是执行失败 |
| **E. Evidence Gap** | **否（0 数据丢失）** | 9/9 bundle 的 `actual` 与探针 `checks` 一致；无“已采未存” | 证据格式缺少 group/source 字段，但没有数据丢失；属表示能力不足 |
| **F. Attestation Gap** | **是（语义层）** | 9/9 Attestation 有效；但不校验“官方检查是否被请求/采集” | 证明产物可信，不证明覆盖完整；无法区分“未请求”与“未观测” |
| **G. Evaluation Gap** | **是（主因之一）** | 1 个顺序 FAIL（save）；5 个条数 INCOMPLETE；官方 verdict 不进 coverage；feedback 不消费官方 verdict | 位置/条数匹配 + 两套评估路径 + 覆盖矩阵不读官方结果 |
| **H. Scenario Semantic Gap** | **是（主因）** | 8/9 场景是守卫变体/否定语义，官方 PASS 在构造上不可能 | 这是 P5 官方 0/4 的**首要原因**；不是产品缺陷 |

### 5.1 主因排序

1. **H：场景语义与官方契约相反**（8/9）。P5 的 4 条全部是 `foreign_group_ignored` 否定场景；官方契约要求目标组正向行为。即使观测补齐，官方也只会 FAIL。
2. **B/C：场景意图/生成器从不规划官方检查**（129/145 未进入；base contract 被显式跳过；`health.current` 被规则丢弃）。
3. **D：Runner 忠实执行了错误的请求清单**（只采场景断言），所以缺失检查连“原始观测”都没有。
4. **G：官方判定器无法消费“完整但不同形状”的证据**（条数/顺序），且官方 verdict 不进入覆盖矩阵/反馈。
5. **F：Attestation 只能证明产物可信，不能证明覆盖完整**（这是设计边界，不是缺陷）。
6. **E：没有数据丢失**；需要的是 group/source 表示，而不是补存。
7. **A：不存在**。

---

## 6. Observation Plan Proposal（设计草案，不实现）

### 6.1 目标

让“场景断言”和“官方契约断言”成为**两个独立、可追溯、可分别判定**的观测组，共享能力但不互相冒充：

```text
Scenario Intent
  → Observation Plan（两组 assertions + 观测清单）
  → Scenario Generation / Official Contract Selection
  → Godot Execution（共享或分离）
  → Evidence Bundle（observations + groups + group verdicts）
  → Attestation
  → Evaluation（每组独立）
  → Coverage（官方组单独计入 official_contract 维度）
```

### 6.2 两类需求

| 组 | 来源 | 用途 | 是否可改变场景语义 |
| --- | --- | --- | --- |
| `scenario` | Scenario `expected_observations` | 验证守卫/否定语义 | 是（场景自己的语义） |
| `official` | `build_contracts()` 的 `expected` | 验证官方契约 | **否**；必须使用官方 actions/expectations |

### 6.3 共享执行 vs 分离执行

| 条件 | 方案 | 原因 |
| --- | --- | --- |
| 两组 actions 完全相同（如 door 的幂等场景） | **共享一次执行**，观测 union，按键去重；两组各自判定 | 动作一致，同一观测可服务两组 |
| actions 不同（foreign group / invalid slot / post-terminal / dependency） | **分离执行**：场景组用场景 actions；官方组用官方 actions；各自 bundle/run/attestation | 强行共享会改变场景语义，或让官方契约执行错误动作 |
| 同一 key 两组期望不同（collect `freed=false` vs `true`） | 共享一个原始观测；两组各自按键判定 | 观测值只有一个，判定值可以不同 |
| 官方检查在场景执行中不可观测（例如外来组不产生伤害） | 官方组单独执行；场景组保持原样 | 不伪造、不推断 |

**结论：统一 Observation Plan 可行，但“统一”指统一计划/证据结构，不等于强制一次执行。** 对当前 8/9 的派生场景，必须允许 `separate_executions`。

### 6.4 数据结构草案

```json
{
  "schema": "observation_plan",
  "schema_version": 1,
  "plan_id": "op-<sha256-16>",
  "scenario_id": "s-...",
  "feature_id": "contact_damage",
  "behavior_id": "damage_on_contact",
  "contract_version": "...",
  "execution": {
    "scene": "res://Features/contact_damage/ContactDamageFixture.tscn",
    "actions": [{"type": "physics.overlap", "params": {"group": "p166_foreign"}}],
    "preconditions": [],
    "window_frames": 45,
    "mode": "separate"          // shared | separate
  },
  "observation_groups": [
    {
      "group_id": "scenario",
      "source": "scenario_assertions",
      "required": true,
      "assertions": [
        {"assertion_id": "a-sc-1", "observation_id": "o-1",
         "check": "signal", "target": "@actor/Health",
         "entry": "health.health_changed", "count": 0}
      ]
    },
    {
      "group_id": "official",
      "source": "feature_contract",
      "contract_version": "...",
      "required": true,
      "execution_ref": "official-exec-1",
      "assertions": [
        {"assertion_id": "a-off-1", "observation_id": "o-2",
         "check": "health.current", "target": "@actor/Health", "equals": 4},
        {"assertion_id": "a-off-2", "observation_id": "o-3",
         "check": "signal", "target": "@actor/Health",
         "entry": "health.health_changed", "count": 1}
      ]
    }
  ],
  "observations": [
    {"observation_id": "o-1", "check": "signal", "target": "@actor/Health",
     "entry": "health.health_changed", "params": {}},
    {"observation_id": "o-2", "check": "health.current", "target": "@actor/Health",
     "params": {}}
  ],
  "collection": {
    "dedupe_by": ["check", "target", "entry"],
    "timing": "post_actions_window",
    "allow_extra_observations": true
  }
}
```

### 6.5 Evidence 结构草案（v2，增量）

```json
{
  "observation_plan_ref": "op-...",
  "observation_plan_digest": "...",
  "observations": [
    {"observation_id": "o-1", "check": "signal", "target": "@actor/Health",
     "entry": "health.health_changed", "observed": 0, "observed_args": [],
     "first_observed_frame": 0, "status": "PASS"}
  ],
  "expectation_groups": [
    {"group_id": "scenario", "source": "scenario_assertions",
     "verdict": "PASS", "assertions": [{"assertion_id": "a-sc-1", "state": "MET"}]},
    {"group_id": "official", "source": "feature_contract",
     "verdict": "FAIL", "assertions": [{"assertion_id": "a-off-1", "state": "UNMET",
                                        "observed": 5, "expected": 4}]}
  ]
}
```

兼容策略：保留 v1 的 `expected[]` / `actual[]` 作为 `scenario` 组的别名；新字段是增量的；旧 bundle 没有 `observation_plan` 时，官方组状态为 `NOT_AVAILABLE`，不得倒推为 FAIL/INCOMPLETE。

### 6.6 判定规则

- 每组独立：`scenario` 组只看场景期望；`official` 组只看官方契约期望。
- **按键匹配**，不按位置；允许 `actual` 有额外观测；缺少某个官方 key → `INCOMPLETE(NOT_OBSERVED)`；值不满足 → `FAIL`。
- 同一 key 出现多个期望（两组）时，观测只采一次，判定分别进行。
- 官方契约组失败不得改变场景组结论；场景组通过不得冒充官方组通过。
- `attestation` 继续只证明运行/产物/证据摘要；若要证明“官方检查被请求”，把 `observation_plan` 纳入 evidence payload（digest 覆盖），attestation 自然覆盖它。

---

## 7. Compatibility Assessment

### 7.1 历史数据

| 对象 | 兼容性 | 需要的处理 |
| --- | --- | --- |
| P4 5 个场景 | 不改文件即可继续被 v1 读取 | 新增字段只读；不重写历史 |
| P5 4 个场景 | 同上 | 同上 |
| 9 个 Evidence bundle（v1） | `schema_version=1` 保持可读 | 新代码必须保留 v1 分支；无 `observation_plan` → `NOT_AVAILABLE` |
| 9 个 Attestation | 不变 | 旧签名/摘要继续有效；新 bundle 重新签名 |
| `scenario_results.json` | 增量字段兼容 | 不改已有字段语义；新增 `official_*` 字段 |
| `result_analysis` / `feedback` | 增量字段兼容 | 不改变已有 classification 规则；官方 status 已记录但未使用，不能追溯重分类 |
| `learning_plan` | 不读取新字段 | 不受影响 |
| Coverage matrix | 新维度增量 | 不改变 `fully_covered` 公式；旧 JSON 仍可读 |

### 7.2 是否需要 Schema Version

- **分离执行方案**（官方组单独 bundle/run）：复用 v1 bundle 格式即可；只需在 `scenario_results` 增加 `official_run_id` / `official_bundle_path` 等字段。**不需要 v2。**
- **统一执行方案**（共享 observations + groups）：`actual` 的语义从“场景 actual”变成“union observations”，需要 `schema_version: 2`；旧 v1 继续支持。必须显式声明 `judgment_semantics`（`positional-v1` / `keyed-v2`），否则历史评估结果会漂移。

### 7.3 历史结果是否会改变

- 如果**只新增分离的官方执行/维度**：历史 9 条场景结果、Evaluation、Evidence、Attestation 均不变。
- 如果**全局替换 `judge_record` 为按键匹配**：历史官方判定会变（例如 `health/damage` 从 INCOMPLETE 变成 FAIL；`save_game` 的 FAIL 原因从 target mismatch 变成 signal/last_slot 值不匹配；`i_frames` 从 INCOMPLETE 变成 FAIL）。这会改变历史报告的可复现性，**不建议**；应新增 `judge_record_keyed`，按 `judgment_semantics` 选择。
- 如果**把官方 verdict 纳入 coverage `evaluation` 维度**：历史 `fully_covered` 可能变化；应新增 `official_contract` 维度并保持 `fully_covered` 公式不变，直到用户明确决定。

### 7.4 风险

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| 双重执行成本 | 官方组单独跑，P5 4 条约 2× 时间 | 先只跑 4 条；可配置；不改变历史 |
| 同一 Behavior 两个 bundle | `check_behavior_evidence` 在同一目录看到两条记录可能 `duplicate_conflict` | 官方/场景分目录；或按 `plan_id` 选择 |
| 矩阵“最新 mtime”选择 | 已出现 P2 报告被选为最新，导致 fully_covered=1 | 按显式 run/plan 选择，不按 mtime |
| 官方契约在当前 HEAD 失败 | 不能假定 60/60 仍成立（最后一次全量是 dd3a0e4d） | 先跑单条，失败按真实 FAIL 记录，不修改契约 |
| 语义混淆 | 把官方 FAIL 当成场景 FAIL，或反之 | 两个 group、两个 verdict、两个字段 |
| 反馈污染 | 当前 `result_analysis` 在官方 FAIL 时仍可 `SOURCE_CONFIRMED` | 官方 verdict 进入 classification 前先做设计决策；不要自动重分类历史 |

---

## 8. Recommended Implementation Plan（Phase 1.68.2 最小方案）

### 8.1 目标与范围

**目标**：让官方契约得到真实、逐行为、可追溯的官方执行证据，并把“官方契约 PASS”与“场景 PASS”分开统计；不改变场景语义，不伪造覆盖。

**首批对象（最小）**：

1. `collect_pickup/collect_on_contact`
2. `contact_damage/damage_on_contact`
3. `contact_damage/damage_amount_is_respected`
4. `heal_pickup/heal_damaged_target`

理由：P5 已确认实现可执行；Phase 1.56 的官方 bundle 对这 4 条均有真实 PASS（`p157-real`），可作为对照基线；且它们正是当前 1 FAIL + 3 INCOMPLETE 的对象。

**回归对象**：`openable_door/open`（唯一官方 PASS 的场景）；其余 P4 场景只读回归，不重跑。

### 8.2 方案 A（推荐，最小代码改动）：分离的官方执行

不改变 Generator/Scenario/契约；只增加“官方契约执行”路径。

| 步骤 | 文件/函数 | 内容 | Schema |
| --- | --- | --- | --- |
| 1 | `scenario_run.py` 新增 `run_official_contract(scenario)` | 用 `_official_contract(feature, behavior)` 取官方 actions/expected/preconditions/scene/window；新建独立 workspace；`verify_contract(..., replay=2)`；写独立 bundle 到 `.ai/tmp/p168/official/evidence`；签名、manifest、attestation 到 `.ai/tmp/p168/official/runs` | 复用 v1 bundle |
| 2 | `scenario_run.py` 结果记录 | 新增 `official_run_id`、`official_bundle_path`、`official_execution_status`、`official_evidence_status`、`official_attestation_status`、`official_contract_status`、`official_contract_detail`；保留现有场景字段 | 增量 |
| 3 | `check_behavior_evidence.py` 新增 `judge_record_keyed()` | 按 `(check,target,entry)` 匹配；允许额外观测；缺 key → INCOMPLETE；值不满足 → FAIL；保留 `judge_record` 不动 | 无 |
| 4 | `scenario_run._verify_and_evaluate` 的官方分支 | 官方 verdict 改用 `judge_record_keyed(record, official)`；场景 verdict 继续用 `judge_record` | 无 |
| 5 | `coverage_matrix.py` 新增 `official_contract` 维度 | 读 `.ai/tmp/p168/official/results.json`（或 scenario_results 的 official_* 字段），统计 `official_contract_pass`；**不改变** `fully_covered`/`missing_requirements` 公式 | 增量 |
| 6 | 测试 | `test_scenario_run.py`：官方执行记录字段；`test_check_behavior_evidence.py`：keyed 匹配（顺序/额外/缺失/重复 key）；历史 9 条 bundle 不变 | 无 |

**关键纪律**：

- 官方执行必须使用**官方 actions**，不能复用场景的 foreign-group actions。
- 官方执行失败按真实 FAIL/INCOMPLETE/ENVIRONMENT_BLOCKED 记录，不改契约、不改期望。
- 官方 bundle 与场景 bundle **分目录**，避免 `duplicate_conflict`。
- 官方 verdict 不得回写场景 `evaluation_status`；两者并列。

### 8.3 方案 B（后续，统一 Observation Plan）

只有在用户明确接受“共享执行 + 证据 v2”后才做：

1. Scenario JSON 增加 `official_observations`（或 `observation_groups`），由 `build_contracts` 生成，不由规则改写。
2. Probe 增加 `observations`（union，去重）与 `expected_groups`；返回原始观测 + 每组 verdict。
3. Evidence `schema_version: 2`：`observations[]` + `expectation_groups[]`；保留 v1 读取。
4. Evaluation/coverage 消费 group verdicts；官方组单独统计。
5. 仅对 actions 完全一致的场景启用 `shared`；其余仍 `separate`。

**本阶段不建议直接做 B**：它改 Probe/Evidence/Validator 三层，回归面大；先用 A 把官方证据跑出来，再决定是否统一。

### 8.4 是否需要修改各层

| 层 | 方案 A（最小） | 方案 B（统一） |
| --- | --- | --- |
| Generator | **不需要** | 需要（输出官方观测组） |
| Runner | **需要**（新增官方执行路径） | 需要（union/分组） |
| Probe | 不需要（复用 `expected`） | 需要（observations + groups） |
| Evidence | 不需要（复用 v1，新增目录/索引） | 需要（v2） |
| Attestation | 不需要 | 不需要（digest 覆盖新 payload） |
| Validator | 需要（新增 keyed 函数，不改旧函数） | 需要（按 group 判定） |
| Evaluation | 需要（官方 verdict 进入新维度） | 需要（消费 group verdicts） |
| Contract | **不需要** | 不需要 |
| Scenario | **不需要** | 需要（新增字段） |

### 8.5 回归测试范围（最小）

1. `test_check_behavior_evidence.py`：新增 keyed 用例（顺序不同、额外观测、缺少 key、重复 key、历史 v1 不变）。
2. `test_scenario_run.py`：官方执行记录字段、失败不被写成场景 PASS、separate 目录不冲突。
3. `test_result_analysis.py` / `test_feedback.py`：官方字段增量不影响既有 classification。
4. 历史 9 条 bundle：digest/签名/attestation 复验不变；`scenario_results` 9 条旧字段 deep-equal。
5. `coverage_matrix`：canonical 输入仍 `fully_covered=0`；新增 `official_contract_pass` 只增不改。
6. 真实 Godot：先跑 1 条（`collect_pickup`）官方契约，确认 PASS；再跑其余 3 条。失败按真实结果记录。

### 8.6 风险与回滚

- **风险**：双倍执行时间；官方 bundle 与场景 bundle 混淆；矩阵 mtime 选择；官方契约在当前 HEAD 失败；反馈把官方 FAIL 当场景 FAIL。
- **回滚**：方案 A 只新增目录/字段/函数；删除 `.ai/tmp/p168/**`、回退新增函数即可；不触碰历史 Evidence/Attestation/契约/Generator。建议用 CLI flag（如 `--official-contracts`）默认关闭，确认后再纳入批次。
- **不承诺**：方案 A 不会让 `fully_covered` 从 0 变 1；它只让 `official_contract_pass` 可见。`Fully Covered` 仍需 evaluation/holdout/mutation 等维度，需单独决策。

---

## 9. Unresolved Questions

1. **“官方契约 PASS”应作为独立维度，还是 `Fully Covered` 的前置条件？** 当前 `Fully Covered` 是 7 维合取；官方 PASS 只是其中隐含的一环，但没有单独字段。若新增 `official_contract` 维度，是否改变 `fully_covered` 公式需要用户决策。
2. **派生场景的官方判定应显示 FAIL 还是 NOT_APPLICABLE？** 当前 8/9 场景在语义上不适合官方契约；把它们标成官方 FAIL 会污染“官方缺陷”统计。建议新增 `NOT_APPLICABLE`，但这会改变历史报告口径。
3. **是否允许 base contract 作为场景？** 生成器当前显式跳过 base（`:442-449`）。允许它会与官方契约采集重复；不允许则学习链永远不产生官方正向场景。
4. **`health.current` 在外来组场景中的“未变化值”如何推导？** 需要 fixture 初始值/前置观测；当前 Generator 没有这个信息。不能用契约的后置值冒充。
5. **是否应全局改为按键匹配？** 会改变 5 条历史官方判定（INCOMPLETE→FAIL/FAIL 原因变化）。是否只在新 `judgment_semantics` 下启用？
6. **P5 的 Knowledge Feedback 是否应因官方 FAIL 失效？** 当前 `result_analysis` 只看场景 Evaluation，官方 FAIL 仍可 `SOURCE_CONFIRMED`；这是语义风险，需产品/治理决策。
7. **Coverage matrix 的 canonical 输入是否应包含 p166/p168？** 当前默认目录不含 P4/P5 证据；`evaluation_dimension` 又按 mtime 选报告，已出现 P2 报告被选中。需要明确“哪个 run/plan 是权威”。
8. **当前 HEAD 的 60 条官方契约是否仍全部可执行？** 最后一次全量是 `dd3a0e4d` 的 60/60 PASS；当前契约 expected 60/60 与该 bundle 一致、actions 59/60 一致，但不能代替当前 HEAD 的真实重跑。
9. **Attestation 是否需要证明“官方检查被请求”？** 当前只证明产物/运行；若要证明覆盖完整性，需要把 Observation Plan 纳入 evidence payload，或新增 attestation 字段。
10. **P4/P5 的 9 条场景是否应继续作为“覆盖”计入场景链？** 它们是真实验证（守卫语义），但不是官方契约覆盖；建议在报告中分列“场景链覆盖”和“官方契约覆盖”，不再合并口径。

---

## 10. Final Conclusion

1. **P5 官方覆盖没有增加的主要根因**：P5 的 4 条场景全部是 `foreign_group_ignored` 否定语义，官方契约要求目标组正向行为；场景在构造上就不满足官方契约。即使补齐缺失观测，3 条 INCOMPLETE 也只会变成 FAIL。更深一层，Generator 显式跳过 base contract（`scenario_generator.py:442-449`），学习链从不生成“官方正向场景”；129/145 官方检查从未进入任何场景。**主因是 H（场景语义）+ B/C（观测规划/生成器），不是 Runner/Evidence/Attestation 故障。**
2. **3 个 INCOMPLETE 能否通过补充观测解决？** 能解决“可判定性”，不能解决“官方覆盖”。把 `health.current` 加入请求后，官方判定会从 INCOMPLETE 变成 FAIL（外来组没有造成伤害/治疗，实际值≠官方后置值）。要得到官方 PASS，必须用官方 actions 单独执行官方契约，或生成独立的正向场景。
3. **`collect_pickup` 的 FAIL 是否应由独立场景解决？** 是。当前场景验证的是“外来组不得拾取”，官方 FAIL 是正确结论；不应改期望消除 FAIL。应新增目标组正向场景或官方契约执行。
4. **当前架构是否支持统一 Observation Plan？** 支持，但必须区分 `shared`（actions 相同）与 `separate`（actions 不同）。当前 8/9 场景属于后者；强行共享会改变场景语义。建议先做分离的官方执行（方案 A），再评估统一 v2。
5. **Phase 1.68.2 最小安全改造范围**：新增独立的官方契约执行路径（复用 `verify_contract`/Evidence/Attestation 现有实现）+ 新增按键匹配的官方判定函数（不改旧 `judge_record`）+ 新增 `official_contract` 覆盖维度（不改 `fully_covered` 公式）。不改 Generator/Scenario/Contract/Probe/Evidence v1；不重跑/不改历史证据；先做 4 条 P5，再回归 door。

**一句话**：场景链证明的是“守卫语义”，官方契约证明的是“正向行为”；当前系统把两者放在同一份证据上，用同一套位置/条数判定去消费，于是既无法让官方契约 PASS，也无法诚实地报告“未覆盖”。修复方向不是补一个字段，而是把“官方契约执行”作为独立、可追溯的证据路径接入。

---

## 11. 只读合规与验证说明

- 未修改任何产品源码、Scenario Generator、Scenario Validator、Evidence/Attestation/Evaluation 实现、Contract、Knowledge Registry、Scenario Registry。
- 未生成新 Scenario、未执行新的 Godot 场景、未生成新的 Evidence Bundle、未修改历史执行记录。
- 未执行 Knowledge 审批、未执行 Planner 更新、未执行 Git commit/push/reset/clean。
- 审计使用：文件读取、`git rev-parse/status/diff --cached`、`godot --version`、以及导入现有 Python 模块做**内存计算**（`build_contracts`、`judge_record`、`build_matrix`、`all_records`）。
- 未写临时审计数据文件；报告是唯一新增文件。Python 导入可能刷新既有 `__pycache__`，不改变任何源文件/Registry/证据。
- 工作区状态：HEAD `54169659`，staged 0；审计前 dirty 1094，审计后 1095（唯一差异为本报告）。
