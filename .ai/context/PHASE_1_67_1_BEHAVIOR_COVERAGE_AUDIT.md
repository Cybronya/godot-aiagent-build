# Phase 1.67.1 — Behavior Coverage Audit

日期：2026-11-07
阶段：Phase 1.67.1（只读审计；未进入 1.67.2，未执行 Git 操作）
产出脚本：`.ai/tmp/p167/audit.py`（gitignored，只读 Registry，不写项目状态）
原始数据：`.ai/tmp/p167/audit.json`

## 1. 基线与方法

### 1.1 实际基线（与任务书不一致处已核实）

| 项 | 任务书 | 实际磁盘 | 说明 |
| --- | --- | --- | --- |
| HEAD | `dd3a0e4d` | **`54169659`** | `dd3a0e4d` 是 1.66 开工前基线；1.66 成果已提交为 `54169659`（`feat(learning): 落地 Phase 1.66 …`） |
| Behavior 总数 | 52 | **60** | 由 `Features/*/template.yaml#behavior` 动态读取，与 1.65/1.66 一致 |
| 未覆盖 | 47 | **55** | 60 − 5 已覆盖；任务书的 52/47 与本机 Registry 不符，本审计以真实 Registry 为准，不沿用假设 |

> 审计开始前工作区有 1030 项与本阶段无关的未提交变更（其他阶段/Agent）；本次审计未触碰、未提交，审计后为 1033 项（新增本报告 + 两份状态文档）。

### 1.2 Registry 与读取方式

| Registry | 真实位置 | 读取方式 |
| --- | --- | --- |
| Behavior Registry | `Features/*/template.yaml` 的 `behavior[]` | `paths.supported_behaviors()`，不硬编码 |
| 正式契约 | 同上，经 `feature_behavior_evidence.build_contracts` | 真实解析 actions / expected / scene |
| Knowledge Registry | `.ai/knowledge/behavior_learning/{records,candidates,conflicts}` | `knowledge_v2.all_records()` |
| Scenario Registry | `.ai/learning/scenarios.json` + `scenarios/*.json` | 索引与单文件分别读取并对比 |
| Validation Registry | `.ai/learning/scenario_validation.json` | 按 `scenario_id` 取权威状态 |
| Execution Registry | `.ai/learning/scenario_results.json`（label `P4`） | 执行/证据/Attestation/评估四层 |
| Dependency Registry | `.ai/learning/behavior_dependency_graph.json` | 118 边，按 `source_behavior/target_behavior` 连接 |
| 历史行为证据 | `.ai/knowledge/behavior_verification/**` | 1.62/1.63 链路的旧记录，单独标注，不冒充本链覆盖 |

审计对每个 Behavior 重新执行 `generate_behavior()`（内存中，不写盘），并在**修正 `res://` 前缀映射**后核对场景文件真实存在。

## 2. 覆盖总览（真实统计）

```text
Behaviors                 60
  已覆盖（1.66 场景链）      5
  未覆盖                   55
    可接入、无历史证据       10   （B1 6 + B2 4）
    可接入、有历史证据        1   （save_game/load_slot_restores_world_state）
    规则族缺口、有历史证据     2   （i_frames/iframes_block_damage_within_window、killing_blow_still_dies）
    规则族缺口              42
```

| 指标 | 值 |
| --- | --- |
| 行为类别 | A 27 / F 17 / E 7 / D 4 / B 3 / C 2 |
| 风险分布 | 高（≥15）7 / 中（10–14）28 / 低（<10）25 |
| 契约可执行性 | 60/60 有 actions 与 expected；场景文件 60/60 存在 |
| 源码分析 | 60/60 文件存在；50/60 至少 1 条 `conditions`，10/60 为空 |
| 知识库 | 71 条；`behaviors_with_knowledge = 5`；OPEN 冲突 0 |
| 场景 | 5 条，全部 `VALID`，ID 唯一，无重复 `(behavior, rule)` |
| 真实执行（P4） | 5 执行、5 EVIDENCE_VERIFIED、5 ATTESTED_VERIFIED、5 VERIFIED_PASS |
| 官方契约 | PASS 1 / FAIL 2 / INCOMPLETE 2（设计差，独立记录） |
| 历史证据 | 7 条 behavior_verification 记录，6 条有现存 bundle；6 个 mutation 引用 |

**关键瓶颈不是 Runner，而是知识覆盖率**：只有 5 个 Behavior 有已审批知识，因此 5 条规则族只能驱动这 5 个场景；其余 55 个即使契约、场景、环境全部可用，也不会被生成。

## 3. 规则族适用性

### 3.1 现有 5 条规则的真实触发条件

| rule_id | 触发的知识事实 | 额外契约条件 |
| --- | --- | --- |
| `idempotent_repeat` | 守卫文本含 `== value` | 有非 fixture 动作，且契约未重复同一动作 |
| `foreign_group_ignored` | 守卫文本含 `is_in_group` | 契约有 `physics.overlap` 动作，可反转预期 |
| `invalid_slot_rejected` | 守卫文本含 `_is_valid_slot_name` | 契约有 `savegame.save_slot` 动作 |
| `post_terminal_input_ignored` | 守卫文本含 `_is_dead` 或 `_current_health == 0` | 契约有 `health.take_damage` 动作 |
| `dependency_postcondition_after_death` | 依赖边 `REQUIRES_PRECONDITION` 且 haystack 含 `health` | 契约动作 target 必须含 `Host/Health` |

### 3.2 知识落地后可触发的候选（潜力，非覆盖）

11 个 Behavior 的源码事实与契约形状满足现有规则，一旦其知识经**显式审批**进入 Store，即可生成场景：

- 成员过滤族（6）：`collect_pickup/collect_on_contact`、`contact_damage/damage_on_contact`、`contact_damage/no_damage_without_contact`、`contact_damage/damage_amount_is_respected`、`heal_pickup/heal_damaged_target`、`trigger_switch/toggle_on_second_contact`
- 状态守卫族（5）：`health/death`、`health/heal_clamped`、`health/overkill_clamps_at_zero`、`health/post_death_guard`、`save_game/load_slot_restores_world_state`

### 3.3 依赖规则的真实边界

依赖图有 21 条 `REQUIRES_PRECONDITION` 边，但 20 条指向 `health/post_death_guard`，其契约动作 target 为 `.`；`health/damage` 同样为 `.`。生成器要求 target 含 `Host/Health`，因此除已覆盖的 `i_frames` 外，**没有任何未覆盖 Behavior 能套用该规则**。这不是环境阻塞，而是模板过度绑定具体节点路径，属于 1.67.2 的设计输入。

### 3.4 42 个规则族缺口需要的方向（提案，未实施）

| 方向 | 代表 Behavior |
| --- | --- |
| 状态迁移序列 | `state_machine/*`、`openable_door` 之外的开关语义 |
| 信号次数/时序 | `cooldown/*`、`hit_flash/*`、`condition_gate/*` |
| 物理运动与轨迹 | `player_movement/*`、`patrol_movement/*`、`moving_platform/*`、`knockback/*`、`chase_movement/*` |
| 资源生命周期 | `projectile/*`、`sfx_pool/*` |
| 跨 Feature 事件投影 | `health_bar/*`、`hit_flash/*`、`stun/*` |
| 碰撞/射线与伤害归属 | `attack_emitter/*`、`contact_damage`（成员族之外的伤害数值语义） |

## 4. 逐 Behavior 覆盖表

说明：Dependencies 最多列 3 个名称，计数为真实边数；Coverage 的“已有历史证据”指 1.62/1.63 链路，不等同于 1.66 场景链覆盖；Feasibility 的“规则族缺口”是**生成能力缺口**，不是环境不可执行。

| Behavior | Coverage | Rule Family | Dependencies | Scenario | Evidence | Feasibility | Knowledge | Risk | Batch |
|---|---|---|---|---|---|---|---|---|---|
| `attack_emitter/raycast_hit_deals_damage` | 阻塞（规则族缺口） | — | 下游2: attack_emitter/repeated_attack_can_kill, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 12 | B3_RULE_FAMILY_GAP |
| `attack_emitter/repeated_attack_can_kill` | 阻塞（规则族缺口） | — | 上游1: attack_emitter/raycast_hit_deals_damage；下游1: health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 14 | B3_RULE_FAMILY_GAP |
| `chase_movement/approach_target` | 阻塞（规则族缺口） | — | 下游1: chase_movement/hold_without_target | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `chase_movement/hold_without_target` | 阻塞（规则族缺口） | — | 上游1: chase_movement/approach_target | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `collect_pickup/collect_on_contact` | 未覆盖（可接入） | foreign_group_ignored（候选） | 无 | 无 | 无 | 可执行（需先落地知识） | 0 | 16 | B1_MEMBERSHIP |
| `condition_gate/partial_conditions_block_output` | 阻塞（规则族缺口） | — | 无 | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 13 | B3_RULE_FAMILY_GAP |
| `condition_gate/all_conditions_fulfill` | 阻塞（规则族缺口） | — | 无 | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 13 | B3_RULE_FAMILY_GAP |
| `condition_gate/condition_fallback_withdraws_output` | 阻塞（规则族缺口） | — | 无 | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 13 | B3_RULE_FAMILY_GAP |
| `contact_damage/damage_on_contact` | 未覆盖（可接入） | foreign_group_ignored（候选） | 上游1: contact_damage/damage_amount_is_respected；下游1: contact_damage/no_damage_without_contact | 无 | 无 | 可执行（需先落地知识） | 0 | 12 | B1_MEMBERSHIP |
| `contact_damage/no_damage_without_contact` | 未覆盖（可接入） | foreign_group_ignored（候选） | 上游2: contact_damage/damage_amount_is_respected, contact_damage/damage_on_contact | 无 | 无 | 可执行（需先落地知识） | 0 | 8 | B1_MEMBERSHIP |
| `contact_damage/damage_amount_is_respected` | 未覆盖（可接入） | foreign_group_ignored（候选） | 下游2: contact_damage/damage_on_contact, contact_damage/no_damage_without_contact | 无 | 无 | 可执行（需先落地知识） | 0 | 12 | B1_MEMBERSHIP |
| `cooldown/cooldown_blocks_during_window` | 阻塞（规则族缺口） | — | 下游2: cooldown/cooldown_expires_and_notifies, cooldown/restart_resets_remaining_window | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `cooldown/cooldown_expires_and_notifies` | 阻塞（规则族缺口） | — | 上游1: cooldown/cooldown_blocks_during_window；下游1: cooldown/restart_resets_remaining_window | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `cooldown/restart_resets_remaining_window` | 阻塞（规则族缺口） | — | 上游2: cooldown/cooldown_blocks_during_window, cooldown/cooldown_expires_and_notifies | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `heal_pickup/heal_damaged_target` | 未覆盖（可接入） | foreign_group_ignored（候选） | 无 | 无 | 无 | 可执行（需先落地知识） | 0 | 11 | B1_MEMBERSHIP |
| `health/damage` | 已覆盖（场景链） | post_terminal_input_ignored | 上游25: health_bar/damage_updates_health_bar, health_bar/death_empties_health_bar, health_bar/healing_updates_health_bar；下游25: health/death, health/heal_clamped, health/overkill_clamps_at_zero | 有（VALID） | 已验证 | 已执行 | 11 已批 / 14 总 | 14 | B0_COVERED_BASELINE |
| `health/heal_clamped` | 未覆盖（可接入） | post_terminal_input_ignored（候选） | 上游2: health/damage, health/death；下游2: health/overkill_clamps_at_zero, health/post_death_guard | 无 | 无 | 可执行（需先落地知识） | 0 | 14 | B2_STATE_GUARDS |
| `health/death` | 未覆盖（可接入） | post_terminal_input_ignored（候选） | 上游1: health/damage；下游3: health/heal_clamped, health/overkill_clamps_at_zero, health/post_death_guard | 无 | 无 | 可执行（需先落地知识） | 0 | 14 | B2_STATE_GUARDS |
| `health/overkill_clamps_at_zero` | 未覆盖（可接入） | post_terminal_input_ignored（候选） | 上游3: health/damage, health/death, health/heal_clamped；下游1: health/post_death_guard | 无 | 无 | 可执行（需先落地知识） | 0 | 14 | B2_STATE_GUARDS |
| `health/post_death_guard` | 未覆盖（可接入） | post_terminal_input_ignored（候选） | 上游24: attack_emitter/raycast_hit_deals_damage, attack_emitter/repeated_attack_can_kill, health/damage | 无 | 无 | 可执行（需先落地知识） | 0 | 15 | B2_STATE_GUARDS |
| `health_bar/initial_health_bar_ratio` | 阻塞（规则族缺口） | — | 上游2: health/damage；下游3: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `health_bar/damage_updates_health_bar` | 阻塞（规则族缺口） | — | 上游2: health/damage；下游3: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `health_bar/healing_updates_health_bar` | 阻塞（规则族缺口） | — | 上游2: health/damage；下游3: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `health_bar/death_empties_health_bar` | 阻塞（规则族缺口） | — | 上游2: health/damage；下游3: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `health_bar/unbound_bar_reports_no_fill` | 阻塞（规则族缺口） | — | 上游2: health/damage；下游3: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `hit_flash/hit_flashes_host` | 阻塞（规则族缺口） | — | 上游3: health/damage, hit_flash/flash_ends_after_duration, hit_flash/heal_does_not_flash；下游2: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `hit_flash/flash_ends_after_duration` | 阻塞（规则族缺口） | — | 上游1: health/damage；下游4: health/damage, hit_flash/heal_does_not_flash, hit_flash/hit_flashes_host | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `hit_flash/heal_does_not_flash` | 阻塞（规则族缺口） | — | 上游2: health/damage, hit_flash/flash_ends_after_duration；下游3: health/damage, health/post_death_guard, hit_flash/hit_flashes_host | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `i_frames/iframes_block_damage_within_window` | 已有历史证据 | — | 上游1: health/damage；下游5: health/damage, health/post_death_guard, i_frames/iframes_expire_and_damage_resumes | 无 | 历史 1 bundle | 规则族缺口（非环境阻塞） | 0 | 14 | B3_RULE_FAMILY_GAP |
| `i_frames/iframes_expire_and_damage_resumes` | 已覆盖（场景链） | dependency_postcondition_after_death | 上游2: health/damage, i_frames/iframes_block_damage_within_window；下游4: health/damage, health/post_death_guard, i_frames/killing_blow_still_dies | 有（VALID） | 已验证 | 已执行 | 11 已批 / 14 总 | 14 | B0_COVERED_BASELINE |
| `i_frames/killing_blow_still_dies` | 已有历史证据 | — | 上游3: health/damage, i_frames/iframes_block_damage_within_window, i_frames/iframes_expire_and_damage_resumes；下游3: health/damage, health/post_death_guard | 无 | 历史 1 bundle | 规则族缺口（非环境阻塞） | 0 | 14 | B3_RULE_FAMILY_GAP |
| `knockback/knockback_applies_and_signals` | 阻塞（规则族缺口） | — | 下游2: knockback/knockback_decays_to_rest, knockback/knockback_rejects_invalid | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `knockback/knockback_decays_to_rest` | 阻塞（规则族缺口） | — | 上游1: knockback/knockback_applies_and_signals；下游1: knockback/knockback_rejects_invalid | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `knockback/knockback_rejects_invalid` | 阻塞（规则族缺口） | — | 上游2: knockback/knockback_applies_and_signals, knockback/knockback_decays_to_rest | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `moving_platform/travel` | 阻塞（规则族缺口） | — | 上游1: moving_platform/round_trip | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `moving_platform/round_trip` | 阻塞（规则族缺口） | — | 下游1: moving_platform/travel | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `openable_door/open` | 已覆盖（场景链） | idempotent_repeat | 无 | 有（VALID） | 已验证 | 已执行 | 10 已批 / 12 总 | 10 | B0_COVERED_BASELINE |
| `patrol_movement/loop_patrol_cycles_waypoints` | 阻塞（规则族缺口） | — | 下游2: patrol_movement/outbound_leg_moves_at_constant_speed, patrol_movement/ping_pong_reverses_at_path_end | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `patrol_movement/outbound_leg_moves_at_constant_speed` | 阻塞（规则族缺口） | — | 上游1: patrol_movement/loop_patrol_cycles_waypoints；下游1: patrol_movement/ping_pong_reverses_at_path_end | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `patrol_movement/ping_pong_reverses_at_path_end` | 阻塞（规则族缺口） | — | 上游2: patrol_movement/loop_patrol_cycles_waypoints, patrol_movement/outbound_leg_moves_at_constant_speed | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `player_movement/move_right` | 阻塞（规则族缺口） | — | 下游1: player_movement/stop_on_release | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `player_movement/stop_on_release` | 阻塞（规则族缺口） | — | 上游1: player_movement/move_right | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 7 | B3_RULE_FAMILY_GAP |
| `projectile/in_flight_moves_until_lifetime` | 阻塞（规则族缺口） | — | 上游1: projectile/hit_deals_damage_and_expires；下游1: projectile/lifetime_expiry_frees_projectile | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 12 | B3_RULE_FAMILY_GAP |
| `projectile/lifetime_expiry_frees_projectile` | 阻塞（规则族缺口） | — | 上游2: projectile/hit_deals_damage_and_expires, projectile/in_flight_moves_until_lifetime | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 16 | B3_RULE_FAMILY_GAP |
| `projectile/hit_deals_damage_and_expires` | 阻塞（规则族缺口） | — | 下游3: health/post_death_guard, projectile/in_flight_moves_until_lifetime, projectile/lifetime_expiry_frees_projectile | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 17 | B3_RULE_FAMILY_GAP |
| `save_game/save_slot_persists_world_state` | 已覆盖（场景链） | invalid_slot_rejected | 上游2: save_game/load_slot_restores_world_state；下游2: health/post_death_guard, save_game/load_slot_restores_world_state | 有（VALID） | 已验证 | 已执行 | 13 已批 / 17 总 | 23 | B0_COVERED_BASELINE |
| `save_game/load_slot_restores_world_state` | 已有历史证据 | invalid_slot_rejected（候选） | 上游1: save_game/save_slot_persists_world_state；下游3: health/post_death_guard, save_game/save_slot_persists_world_state | 无 | 历史 1 bundle | 可执行（需先落地知识） | 0 | 23 | B2_STATE_GUARDS |
| `screen_shake/trauma_starts_shake` | 阻塞（规则族缺口） | — | 上游1: screen_shake/shake_stops_after_decay | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `screen_shake/shake_stops_after_decay` | 阻塞（规则族缺口） | — | 下游1: screen_shake/trauma_starts_shake | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 5 | B3_RULE_FAMILY_GAP |
| `sfx_pool/sfx_play_emits_and_occupies` | 阻塞（规则族缺口） | — | 下游1: sfx_pool/sfx_pool_steals_oldest_when_full | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `sfx_pool/sfx_pool_steals_oldest_when_full` | 阻塞（规则族缺口） | — | 上游1: sfx_pool/sfx_play_emits_and_occupies | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 8 | B3_RULE_FAMILY_GAP |
| `state_machine/transition_to_named_state` | 阻塞（规则族缺口） | — | 上游1: state_machine/previous_backtracks_via_history | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `state_machine/previous_backtracks_via_history` | 阻塞（规则族缺口） | — | 下游1: state_machine/transition_to_named_state | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `stun/hit_stuns_and_freezes_host` | 阻塞（规则族缺口） | — | 上游3: health/damage, stun/death_guard_rejects_stun, stun/heal_does_not_stun；下游4: health/damage, health/post_death_guard, stun/reentry_extends_without_rebroadcast | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 15 | B3_RULE_FAMILY_GAP |
| `stun/stun_expires_and_host_resumes` | 阻塞（规则族缺口） | — | 上游5: health/damage, stun/death_guard_rejects_stun, stun/heal_does_not_stun；下游2: health/damage, health/post_death_guard | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `stun/heal_does_not_stun` | 阻塞（规则族缺口） | — | 上游2: health/damage, stun/death_guard_rejects_stun；下游5: health/damage, health/post_death_guard, stun/hit_stuns_and_freezes_host | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `stun/death_guard_rejects_stun` | 阻塞（规则族缺口） | — | 上游1: health/damage；下游6: health/damage, health/post_death_guard, stun/heal_does_not_stun | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 14 | B3_RULE_FAMILY_GAP |
| `stun/reentry_extends_without_rebroadcast` | 阻塞（规则族缺口） | — | 上游4: health/damage, stun/death_guard_rejects_stun, stun/heal_does_not_stun；下游3: health/damage, health/post_death_guard, stun/stun_expires_and_host_resumes | 无 | 无 | 规则族缺口（非环境阻塞） | 0 | 10 | B3_RULE_FAMILY_GAP |
| `trigger_switch/latch_once` | 已覆盖（场景链） | foreign_group_ignored | 下游1: trigger_switch/toggle_on_second_contact | 有（VALID） | 已验证 | 已执行 | 10 已批 / 14 总 | 10 | B0_COVERED_BASELINE |
| `trigger_switch/toggle_on_second_contact` | 未覆盖（可接入） | foreign_group_ignored（候选） | 上游1: trigger_switch/latch_once | 无 | 无 | 可执行（需先落地知识） | 0 | 10 | B1_MEMBERSHIP |
## 5. 完整性检查

| 检查 | 结果 |
| --- | --- |
| Scenario ID 唯一 | 5/5 唯一 |
| 重复 `(behavior, rule)` | 0 |
| `knowledge_refs` 存在且 APPROVED | 5/5 通过 |
| `dependency_refs` 可解析 | 1/1（仅 i_frames 场景有 1 条，`dep-0057` 存在于图） |
| 知识冲突 | `conflicts_open=0`；5 条历史冲突均已解决且保留 |
| 历史 Evidence Bundle | 6/6 引用文件仍存在 |
| 场景文件存在 | 60/60 契约场景可定位（修正 `res://` 后才成立） |
| 契约 expected 为空 | 0 |

### 5.1 发现的两处 Registry 状态不一致（P3，本阶段只记录不修）

1. **索引与单场景文件不一致**：`scenarios.json` 内嵌副本的 `validation_status` 仍是 `PENDING`，而 `scenarios/*.json` 与 `scenario_validation.json` 已是 `VALID`（5/5）。只读索引的消费者会看到过期状态。
2. **执行状态未回写场景**：单场景文件仍是 `execution_status=NOT_EXECUTED`，真实结果只存在于 `scenario_results.json`。当前 `scenario_run` 以结果文件为准，因此不影响 1.66 结论；但两个 Registry 的权威边界需要在 1.67.2 明确（建议：索引/场景文件为生成快照，验证与执行状态以各自报告为唯一权威，并在文档中写明）。

> 这两项不构成本阶段阻塞，也不影响既有 Evidence；修复需要改变写入行为，不属于“只读审计”。

## 6. 执行可行性与风险

### 6.1 是否存在环境阻塞

- 60/60 契约有可执行 actions 与 expected，60/60 场景文件存在。
- 5/5 真实执行已在 `LOCAL_ISOLATED` 完成（Godot 4.7-stable console）。
- **未发现“当前环境确定不可执行”的 Behavior**；“规则族缺口”是生成能力问题，不得写成环境阻塞。
- 潜在环境风险（未验证，不得预判）：
  - 音频：`sfx_pool/*`（headless 音频设备行为）
  - 物理/射线：`attack_emitter/*`、`projectile/*`、`contact_damage/*`
  - 输入模拟：`player_movement/*`
  - 帧时序：`cooldown/*`、`i_frames/*`
  这些必须在 1.67.2 用真实执行确认，不能因“应该能跑”直接标记 PASS。

### 6.2 规则模板迁移风险（审计发现，必须在实施前处理）

现有 5 条规则是围绕 1.66 的 5 个契约写的通用匹配器，但**迁移到同族其他契约并不总是语义安全**：

| 候选 | 风险 | 说明 |
| --- | --- | --- |
| `health/death`、`health/overkill_clamps_at_zero` | 高 | 契约动作本身已致死；规则再追加致死伤害并期望 `health_changed +1`，但守卫会提前返回，预期很可能错误 → 会产出 FAIL 或 TEST_DESIGN_ERROR，而不是行为缺陷 |
| `health/post_death_guard` | 高 | 契约已包含死亡后动作；再追加会重复同一语义，期望无法区分“新增”与“原有” |
| `health/heal_clamped` | 中 | 契约先伤害后治疗；追加“致死+治疗”后的 `health_changed` 计数需按守卫重新推导 |
| `save_game/load_slot_restores_world_state` | 高 | 规则把 save 动作改成非法槽，但契约随后 load 该槽并期望 `game_loaded=1`、`health=3`；非法 save 会让 load 失败 → 预期自相矛盾 |
| `contact_damage/no_damage_without_contact` | 中 | 契约有两个 `physics.overlap`（近点/远点），规则会把两者都改成外来组，丢失“远点不接触”的原意 |
| `trigger_switch/toggle_on_second_contact` | 中 | 同理两个 overlap 都被替换；成员过滤语义成立，但不再测试“第二次接触切换” |
| `collect_pickup`、`contact_damage/damage_on_contact`、`contact_damage/damage_amount_is_respected`、`heal_pickup` | 低 | 单一 overlap、预期以信号/数值为主，反转语义直接成立 |

结论：11 个“潜力”里只有 4 个可低风险直接套用；其余 7 个需要**先修生成规则的期望推导**（从守卫事实推导“死亡后不再发信号”，而不是固定 `+1`；对多 overlap 契约只替换“应命中”的那一个），并且要用真实执行验证。这个修改属于生成器逻辑与场景预期，不涉及 Validator/Evaluation 判定规则，但仍需在实施前单独确认。

## 7. 分批建议（待确认，不实施）

### Batch B1 — 成员过滤族（6 个）

| Behavior | 风险 | 模板迁移 | 备注 |
| --- | --- | --- | --- |
| `collect_pickup/collect_on_contact` | 16 | 低 | 单一 overlap；单条组合守卫（`_collected` 或 非目标组） |
| `contact_damage/damage_amount_is_respected` | 12 | 低 | 建议本批第一个执行（同 Feature 上游） |
| `contact_damage/damage_on_contact` | 12 | 低 | 依赖上一项 |
| `contact_damage/no_damage_without_contact` | 8 | 中 | 双 overlap，需限定只替换目标 overlap |
| `heal_pickup/heal_damaged_target` | 11 | 低 | 单一 overlap；额外有死亡/满血守卫 |
| `trigger_switch/toggle_on_second_contact` | 10 | 中 | 双 overlap；与已覆盖 `latch_once` 同 Feature，可复用执行经验 |

进入条件：为上述 6 个 Behavior 抽取并**显式审批** `SOURCE_OBSERVATION:guards`；修复“多 overlap 只替换目标动作”后再生成。

### Batch B2 — 状态守卫族（5 个）

| Behavior | 风险 | 模板迁移 | 备注 |
| --- | --- | --- | --- |
| `health/death` | 14 | 高 | 需按 `_is_dead` 守卫重推期望 |
| `health/overkill_clamps_at_zero` | 14 | 高 | 同上 |
| `health/heal_clamped` | 14 | 中 | 追加“致死+治疗”后核对计数 |
| `health/post_death_guard` | 15 | 高 | 契约已含死亡后动作，考虑改用“追加第三次输入”的变体 |
| `save_game/load_slot_restores_world_state` | 23 | 高 | 非法槽规则需改为“非法 load”而非“非法 save + 正常 load” |

进入条件：先完成终态规则与非法槽规则的**期望推导修订 + 单元测试**，再生成；否则会产出假 FAIL，污染知识回流。

### 不建议在 1.67.2 内处理

- 42 个规则族缺口：需要新增规则族（状态迁移、信号时序、物理运动、资源生命周期、UI 投影、跨 Feature 传播）。这是设计扩展，不是“批量接入”，应与本阶段分开授权。
- 其中 `i_frames/iframes_block_damage_within_window`、`killing_blow_still_dies` 已有 1.62/1.63 历史证据，可优先补场景，但仍需新规则族。

### 每批执行顺序（B1/B2 相同）

```text
extract.py（限定 behaviors，生成 PENDING_REVIEW 候选）
  → 显式审批（不可自动；记录 reviewer/reason/scope）
  → scenario_generator.py（--behaviors ... --prune 仅该批）
  → scenario_validate.py（全部 VALID 才继续）
  → scenario_run.py --label P5/P6（真实 Godot）
  → result_analysis.py
  → feedback.py（候选默认 PENDING；是否批准按 §8 决策）
  → planner.py（对比前后任务数与证据依据）
```

每批完成后核对：Evidence Bundle 未被覆盖、Attestation 独立、官方契约与场景结论分开、Repo Guard 未变、历史 bundle 未删。

## 8. 需要确认的决策（阻塞 1.67.2 启动）

1. **知识审批权限**：11 个候选的 `SOURCE_OBSERVATION` 需要 APPROVED 才能驱动生成。是否授权 Agent 以 `phase_1_67_local_review` 执行 `feedback`/`knowledge_v2 approve`（本地审查，非人类身份验证），还是必须由用户逐条确认？
2. **规则模板修订范围**：是否允许在 1.67.2 修订生成器的期望推导（终态计数、单 overlap 替换、非法 load）？这不改 Validator/Evaluation，但会改变生成结果，需要明确授权。
3. **批次范围**：1.67.2 只做 B1+B2（11 个），还是同时启动 42 个缺口中的新规则族？后者建议独立阶段。
4. **执行 label 与目录**：建议 `P5`（B1）、`P6`（B2），产物继续放 `.ai/tmp/p167/**`，不覆盖 `.ai/tmp/p166/**`。
5. **Matrix 输入**：`.ai/tmp/p164/batch1/matrix_after/coverage_matrix.json` 当前存在但是 gitignored 的本地文件；若被清理，需要先用 1.64 入口重建矩阵，不能改为默认扫描。

## 9. 本阶段未执行事项与工作区状态

- 未生成任何新场景、未执行任何 Godot、未改动产品源码/契约/Binding/Baseline、未写知识。
- 未运行测试套件（审计未改代码）；引用的是 1.66 已提交的 158 项检查结果。
- 未执行 Git commit/push/reset/clean。
- 新增文件仅：本审计文档；审计脚本与 `audit.json`、`table.md` 位于 `.ai/tmp/p167/`（gitignored）。
- 工作区仍有其他阶段的未提交变更（审计前 1030 项，审计后 1033 项，差额为本报告与 `CURRENT_TASK.md`/`WORK_STATE.md`）；HEAD 仍为 `54169659`。

## 10. 审计结论

1. 真实覆盖是 **5/60**，不是任务书假设的 5/52；未覆盖 **55**，其中 11 个可由现有规则族接入（4 个低风险、7 个需先修模板），42 个缺规则族，2 个仅有历史证据且缺规则族。
2. 阻碍扩展的第一瓶颈是**知识覆盖率（5/60）**，第二是**规则族与模板迁移安全**，两者都不是 Runner 或环境问题。
3. 现有场景、证据、知识引用与历史 bundle 完整性检查全部通过；唯一发现是索引/场景文件的状态未回写（P3）。
4. 建议 1.67.2 先做 B1（6）与 B2（5），并在启动前确认 §8 的 5 个决策；42 个规则族缺口另立阶段。
