# Phase 1.64 — Behavior Inventory（动态生成）

> 本文件由 `.ai/tmp/p164/inventory/gen_inventory.py` 从真实产物生成，**不要手工维护**。
> 数据来源：`Features/*/template.yaml#behavior`（契约）、`Features/*/*.gd`（源码/测试）、
> `.ai/tmp/p164/initial/coverage_matrix.json`（八维状态）。

## 1. 支持集与分类口径

| 项 | 值 |
| --- | --- |
| Feature | 23 |
| Behavior | 60 |
| 分类映射完整 | 是（60/60 有分类与依据） |
| 执行就绪 | READY=60 |

分类不看 ID/名称，依据是契约里的 actions / preconditions / expected 与对应实现源码：

| 代码 | 类别 | 数量 |
| --- | --- | --- |
| A | State Transition | 27 |
| B | Event Propagation | 3 |
| C | Persistence | 2 |
| D | Resource Lifecycle | 4 |
| E | Interaction | 7 |
| F | Guard & Conditional Logic | 17 |

## 2. 逐条清单（按风险分降序）

| risk | Feature / Behavior | 主类 | 次类 | 实现 | 依赖（场景/动作） | 现有测试 | Evidence | Eval | Mutation | 就绪 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | `save_game/load_slot_restores_world_state` | C | A | `Features/save_game/instanced_node_fixture.gd` | health, savegame | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 25 | `save_game/save_slot_persists_world_state` | C | A | `Features/save_game/instanced_node_fixture.gd` | health, savegame | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 23 | `projectile/hit_deals_damage_and_expires` | E | D,A | `Features/projectile/projectile.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 22 | `projectile/lifetime_expiry_frees_projectile` | D | A | `Features/projectile/projectile.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 21 | `stun/hit_stuns_and_freezes_host` | A | E,B | `Features/stun/stun.gd` | input, simulation, health | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 20 | `attack_emitter/repeated_attack_can_kill` | A | E | `Features/attack_emitter/attack_emitter.gd` | simulation, attackemitter | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 20 | `stun/death_guard_rejects_stun` | F | A | `Features/stun/stun.gd` | input, simulation, health | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 19 | `condition_gate/all_conditions_fulfill` | F | B | `Features/condition_gate/condition_gate.gd` | physics, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 19 | `condition_gate/condition_fallback_withdraws_output` | F | B,A | `Features/condition_gate/condition_gate.gd` | physics, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 19 | `condition_gate/partial_conditions_block_output` | F | B | `Features/condition_gate/condition_gate.gd` | physics, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 18 | `attack_emitter/raycast_hit_deals_damage` | E | B | `Features/attack_emitter/attack_emitter.gd` | simulation, attackemitter | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 18 | `collect_pickup/collect_on_contact` | D | E,B | `Features/collect_pickup/collect_pickup.gd` | physics | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 18 | `contact_damage/damage_amount_is_respected` | E | A | `Features/contact_damage/contact_damage.gd` | physics | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 18 | `contact_damage/damage_on_contact` | E | A | `Features/contact_damage/contact_damage.gd` | physics | 1 个 | NO_EVIDENCE | NOT_EVALUATED | MUTATION_KILLED | READY |
| 18 | `projectile/in_flight_moves_until_lifetime` | A | D | `Features/projectile/projectile.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 17 | `heal_pickup/heal_damaged_target` | E | A,D | `Features/heal_pickup/heal_pickup.gd` | physics | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 17 | `health/post_death_guard` | F | A | `Features/health/health.gd` | health | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 16 | `cooldown/cooldown_blocks_during_window` | F | A | `Features/cooldown/cooldown.gd` | cooldown, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `cooldown/cooldown_expires_and_notifies` | A | B | `Features/cooldown/cooldown.gd` | cooldown, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `cooldown/restart_resets_remaining_window` | A | F | `Features/cooldown/cooldown.gd` | cooldown, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `health/damage` | A | B | `Features/health/health.gd` | health | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 16 | `health/death` | A | B | `Features/health/health.gd` | health | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | NOT_TESTED | READY |
| 16 | `health/heal_clamped` | A | F | `Features/health/health.gd` | health | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | NOT_TESTED | READY |
| 16 | `health/overkill_clamps_at_zero` | F | A | `Features/health/health.gd` | health | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | NOT_TESTED | READY |
| 16 | `i_frames/iframes_block_damage_within_window` | F | A | `Features/i_frames/i_frames.gd` | health, simulation | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 16 | `i_frames/iframes_expire_and_damage_resumes` | A | F | `Features/i_frames/i_frames.gd` | health, simulation | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 16 | `i_frames/killing_blow_still_dies` | F | A | `Features/i_frames/i_frames.gd` | health, simulation | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | NOT_TESTED | READY |
| 16 | `state_machine/previous_backtracks_via_history` | A | F | `Features/state_machine/fixture_state.gd` | statemachine | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `state_machine/transition_to_named_state` | A | B | `Features/state_machine/fixture_state.gd` | statemachine | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `stun/heal_does_not_stun` | F | B | `Features/stun/stun.gd` | input, simulation, health | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `stun/reentry_extends_without_rebroadcast` | F | B,A | `Features/stun/stun.gd` | input, simulation, health | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `stun/stun_expires_and_host_resumes` | A | B | `Features/stun/stun.gd` | input, simulation, health | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 16 | `trigger_switch/latch_once` | F | A,B | `Features/trigger_switch/test_trigger_switch.gd` | physics, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | MUTATION_KILLED | READY |
| 16 | `trigger_switch/toggle_on_second_contact` | A | F,B | `Features/trigger_switch/test_trigger_switch.gd` | state, physics, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `contact_damage/no_damage_without_contact` | F | E | `Features/contact_damage/contact_damage.gd` | physics, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `health_bar/damage_updates_health_bar` | A | B | `Features/health_bar/health_bar.gd` | health, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `health_bar/death_empties_health_bar` | A | B | `Features/health_bar/health_bar.gd` | health, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `health_bar/healing_updates_health_bar` | A | B | `Features/health_bar/health_bar.gd` | health, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `knockback/knockback_applies_and_signals` | B | A | `Features/knockback/knockback.gd` | knockback, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `knockback/knockback_decays_to_rest` | A | B | `Features/knockback/knockback.gd` | knockback, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `patrol_movement/loop_patrol_cycles_waypoints` | A | B | `Features/patrol_movement/patrol_movement.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `patrol_movement/ping_pong_reverses_at_path_end` | A | F | `Features/patrol_movement/patrol_movement.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `sfx_pool/sfx_play_emits_and_occupies` | D | B | `Features/sfx_pool/sfx_pool.gd` | sfx, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 14 | `sfx_pool/sfx_pool_steals_oldest_when_full` | D | A | `Features/sfx_pool/sfx_pool.gd` | sfx, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `chase_movement/approach_target` | A | E | `Features/chase_movement/chase_movement.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `chase_movement/hold_without_target` | F | A | `Features/chase_movement/chase_movement.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `health_bar/initial_health_bar_ratio` | A | B | `Features/health_bar/health_bar.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `moving_platform/round_trip` | A | E | `Features/moving_platform/moving_platform.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `moving_platform/travel` | A | E | `Features/moving_platform/moving_platform.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `patrol_movement/outbound_leg_moves_at_constant_speed` | A | E | `Features/patrol_movement/patrol_movement.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `player_movement/move_right` | E | A | `Features/player_movement/player_controller.gd` | input, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 13 | `player_movement/stop_on_release` | E | F | `Features/player_movement/player_controller.gd` | input, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 12 | `openable_door/open` | A | B | `Features/openable_door/openable_door.gd` | door | 1 个 | EVIDENCE_VERIFIED | VERIFIED_PASS | MUTATION_KILLED | READY |
| 11 | `health_bar/unbound_bar_reports_no_fill` | F | A | `Features/health_bar/health_bar.gd` | simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 11 | `hit_flash/flash_ends_after_duration` | A | B | `Features/hit_flash/hit_flash.gd` | health, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 11 | `hit_flash/heal_does_not_flash` | F | B | `Features/hit_flash/hit_flash.gd` | health, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 11 | `hit_flash/hit_flashes_host` | B | A | `Features/hit_flash/hit_flash.gd` | health, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 11 | `knockback/knockback_rejects_invalid` | F | B | `Features/knockback/knockback.gd` | knockback, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 11 | `screen_shake/shake_stops_after_decay` | A | B | `Features/screen_shake/screen_shake.gd` | screenshake, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |
| 11 | `screen_shake/trauma_starts_shake` | B | A | `Features/screen_shake/screen_shake.gd` | screenshake, simulation | 1 个 | NO_EVIDENCE | NOT_EVALUATED | NOT_TESTED | READY |

## 3. 分类依据（逐条可追溯）

| Feature / Behavior | 依据（契约/源码事实） |
| --- | --- |
| `save_game/load_slot_restores_world_state` | contract: 读档回填 current（跨 run 恢复） |
| `save_game/save_slot_persists_world_state` | contract: 存档槽写入 current 与 last_slot（跨 run 持久化） |
| `projectile/hit_deals_damage_and_expires` | contract: 命中造成伤害且自身释放（一次性） |
| `projectile/lifetime_expiry_frees_projectile` | contract: 生命周期到期释放节点 + 信号 |
| `stun/hit_stuns_and_freezes_host` | contract: 受击後位移冻结 + stun 信号 + health 变化 |
| `attack_emitter/repeated_attack_can_kill` | contract: 重复命中累积到 is_dead=true 且 died 信号；源码同一 raycast 路径 |
| `stun/death_guard_rejects_stun` | contract: 死亡後不再进入眩晕（is_dead 守卫） |
| `condition_gate/all_conditions_fulfill` | contract: 全部条件满足時 trigger.is_triggered=true 且 door.is_open=true + 信号 |
| `condition_gate/condition_fallback_withdraws_output` | contract: 条件撤回後输出回退（trigger/door 复位） |
| `condition_gate/partial_conditions_block_output` | contract: 只满足部分条件時 trigger/door 不变且无广播 |
| `attack_emitter/raycast_hit_deals_damage` | contract: raycast hit -> health.current 减少 + health_changed 信号；源码 raycast_attack_emitter.gd 命中后调用 take_damage |
| `collect_pickup/collect_on_contact` | contract: pickup.is_collected + node.freed + pickup.collected 信号；源码 _collect 内 queue_free |
| `contact_damage/damage_amount_is_respected` | contract: 指定伤害量被精确应用（数值断言） |
| `contact_damage/damage_on_contact` | contract: 接触後 health.current 下降 + health_changed |
| `projectile/in_flight_moves_until_lifetime` | contract: 存活期内持续位移、未提前释放 |
| `heal_pickup/heal_damaged_target` | contract: 接触後 health.current 回升且 node.freed |
| `health/post_death_guard` | contract: 死後扣血/治疗均被守卫拒绝（current/信号/重复 died 三处可观测） |
| `cooldown/cooldown_blocks_during_window` | contract: is_ready 窗口内为 false 且不广播 ready |
| `cooldown/cooldown_expires_and_notifies` | contract: 到期後 is_ready=true 且广播 ready |
| `cooldown/restart_resets_remaining_window` | contract: 重启重新计时（is_ready 再次 false） |
| `health/damage` | contract: current 精确减少 + health_changed last_args |
| `health/death` | contract: current=0、is_dead=true、died 信号 1 次 |
| `health/heal_clamped` | contract: 治疗被钳到 max + last_args=[5,99] |
| `health/overkill_clamps_at_zero` | contract: 100 点过杀仍停在 0（下限钳制） |
| `i_frames/iframes_block_damage_within_window` | contract: 无敌窗口内 current 不变、无 health_changed |
| `i_frames/iframes_expire_and_damage_resumes` | contract: 窗口过後伤害恢复生效 |
| `i_frames/killing_blow_still_dies` | contract: 无敌不豁免致死判定（is_dead=true） |
| `state_machine/previous_backtracks_via_history` | contract: previous() 按历史栈回退（空历史有守卫） |
| `state_machine/transition_to_named_state` | contract: current_state_name 改变 + state_changed |
| `stun/heal_does_not_stun` | contract: 治疗不触发眩晕（反向守卫） |
| `stun/reentry_extends_without_rebroadcast` | contract: 重复命中延长时长但不重复广播 stun(true) |
| `stun/stun_expires_and_host_resumes` | contract: 眩晕到期恢复移动 + 信号 |
| `trigger_switch/latch_once` | contract: 第一次接触锁存，第二次无新广播 |
| `trigger_switch/toggle_on_second_contact` | contract: 第二次接触翻转状态 + 广播 |
| `contact_damage/no_damage_without_contact` | contract: 无接触時 current 不变且无信号（反向守卫） |
| `health_bar/damage_updates_health_bar` | contract: 受伤後 ratio 同步下降 + 信号 |
| `health_bar/death_empties_health_bar` | contract: 死亡後 ratio=0 |
| `health_bar/healing_updates_health_bar` | contract: 治疗後 ratio 回升 + 信号 |
| `knockback/knockback_applies_and_signals` | contract: 位移脉冲 + knockback_changed(true)（幂等不重复） |
| `knockback/knockback_decays_to_rest` | contract: 线性衰减至静止 + knockback_changed(false) |
| `patrol_movement/loop_patrol_cycles_waypoints` | contract: 循环模式重复广播 waypoint_reached |
| `patrol_movement/ping_pong_reverses_at_path_end` | contract: 往返模式端点折返（方向反转） |
| `sfx_pool/sfx_play_emits_and_occupies` | contract: play 同步广播 played 且 active_count 增加 |
| `sfx_pool/sfx_pool_steals_oldest_when_full` | contract: 池满时抢占最旧，active_count 不超上限 |
| `chase_movement/approach_target` | contract: position/displacement 向 target 收敛；源码 _physics_process 写 velocity 并 move_and_slide |
| `chase_movement/hold_without_target` | contract: target 缺失時 displacement=0；源码 _physics_process 早退并置 velocity=0 |
| `health_bar/initial_health_bar_ratio` | contract: 初始 ratio 与 current 一致 |
| `moving_platform/round_trip` | contract: 往返（三角波）回到起点附近 |
| `moving_platform/travel` | contract: 平台/乘客位移随时间推进 |
| `patrol_movement/outbound_leg_moves_at_constant_speed` | contract: 单段位移与速度/帧数一致 |
| `player_movement/move_right` | contract: 输入按下 → displacement 向右 |
| `player_movement/stop_on_release` | contract: 松开输入 → 位移归零 |
| `openable_door/open` | contract: is_open 变 true + door.state_changed 信号 |
| `health_bar/unbound_bar_reports_no_fill` | contract: 未绑定目标時 ratio 保持 0（不得 crash/假填充） |
| `hit_flash/flash_ends_after_duration` | contract: 时长後广播 flash(false) 且恢复 |
| `hit_flash/heal_does_not_flash` | contract: 治疗不触发闪烁（反向守卫） |
| `hit_flash/hit_flashes_host` | contract: 受伤广播 flash(true) 且宿主可见态改变 |
| `knockback/knockback_rejects_invalid` | contract: 零方向/非正力被拒绝且无广播 |
| `screen_shake/shake_stops_after_decay` | contract: trauma 衰减到 0 广播 shaking(false) |
| `screen_shake/trauma_starts_shake` | contract: add_trauma 广播 shaking(true) |

## 4. 未分类的 Behavior

无。60 条全部有主类、次类与依据；若未来契约新增未登记 Behavior，本生成器会直接失败（MAPPING MISMATCH），不会静默给出默认分类。
