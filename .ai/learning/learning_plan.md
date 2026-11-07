# Learning Plan（p166_after_feedback）

优先级公式：`priority = 3*severity + risk/2 + upstream_impact + failure_bonus - cost`

任务总数 **276**，阻塞 **0**，因已有知识排除 **10**。

| # | 任务 | 缺口 | 优先级 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | ANALYZE_DEPENDENCIES `health/post_death_guard` | DEPENDENCY_UNKNOWN | 18.5 | PENDING |
| 2 | ANALYZE_SOURCE `health/post_death_guard` | CONTRACT_UNDERSTOOD_ONLY | 18.5 | PENDING |
| 3 | ANALYZE_SOURCE `save_game/load_slot_restores_world_state` | CONTRACT_UNDERSTOOD_ONLY | 17.5 | PENDING |
| 4 | UPDATE_KNOWLEDGE `health/post_death_guard` | KNOWLEDGE_INCOMPLETE | 15.5 | PENDING |
| 5 | ANALYZE_SOURCE `stun/hit_stuns_and_freezes_host` | CONTRACT_UNDERSTOOD_ONLY | 15.5 | PENDING |
| 6 | EXECUTE_BEHAVIOR `stun/hit_stuns_and_freezes_host` | NO_RUNTIME_OBSERVATION | 15.5 | PENDING |
| 7 | ANALYZE_SOURCE `health/overkill_clamps_at_zero` | CONTRACT_UNDERSTOOD_ONLY | 15.0 | PENDING |
| 8 | ANALYZE_SOURCE `i_frames/killing_blow_still_dies` | CONTRACT_UNDERSTOOD_ONLY | 15.0 | PENDING |
| 9 | ANALYZE_DEPENDENCIES `projectile/lifetime_expiry_frees_projectile` | DEPENDENCY_UNKNOWN | 15.0 | PENDING |
| 10 | ANALYZE_SOURCE `projectile/lifetime_expiry_frees_projectile` | CONTRACT_UNDERSTOOD_ONLY | 15.0 | PENDING |
| 11 | EXECUTE_BEHAVIOR `projectile/lifetime_expiry_frees_projectile` | NO_RUNTIME_OBSERVATION | 15.0 | PENDING |
| 12 | ANALYZE_SOURCE `stun/stun_expires_and_host_resumes` | CONTRACT_UNDERSTOOD_ONLY | 15.0 | PENDING |
| 13 | EXECUTE_BEHAVIOR `stun/stun_expires_and_host_resumes` | NO_RUNTIME_OBSERVATION | 15.0 | PENDING |
| 14 | UPDATE_KNOWLEDGE `save_game/load_slot_restores_world_state` | KNOWLEDGE_INCOMPLETE | 14.5 | PENDING |
| 15 | DESIGN_MUTATION `stun/hit_stuns_and_freezes_host` | NO_MUTATION_KNOWLEDGE | 14.5 | PENDING |
| 16 | DESIGN_TEST_SCENARIO `stun/hit_stuns_and_freezes_host` | NO_TEST_SCENARIO | 14.5 | PENDING |
| 17 | ANALYZE_SOURCE `health/heal_clamped` | CONTRACT_UNDERSTOOD_ONLY | 14.0 | PENDING |
| 18 | DESIGN_MUTATION `health/overkill_clamps_at_zero` | NO_MUTATION_KNOWLEDGE | 14.0 | PENDING |
| 19 | DESIGN_MUTATION `i_frames/killing_blow_still_dies` | NO_MUTATION_KNOWLEDGE | 14.0 | PENDING |
| 20 | DESIGN_MUTATION `projectile/lifetime_expiry_frees_projectile` | NO_MUTATION_KNOWLEDGE | 14.0 | PENDING |
| 21 | DESIGN_TEST_SCENARIO `projectile/lifetime_expiry_frees_projectile` | NO_TEST_SCENARIO | 14.0 | PENDING |
| 22 | ANALYZE_SOURCE `stun/reentry_extends_without_rebroadcast` | CONTRACT_UNDERSTOOD_ONLY | 14.0 | PENDING |
| 23 | EXECUTE_BEHAVIOR `stun/reentry_extends_without_rebroadcast` | NO_RUNTIME_OBSERVATION | 14.0 | PENDING |
| 24 | DESIGN_MUTATION `stun/stun_expires_and_host_resumes` | NO_MUTATION_KNOWLEDGE | 14.0 | PENDING |
| 25 | DESIGN_TEST_SCENARIO `stun/stun_expires_and_host_resumes` | NO_TEST_SCENARIO | 14.0 | PENDING |
| 26 | ANALYZE_SOURCE `projectile/hit_deals_damage_and_expires` | CONTRACT_UNDERSTOOD_ONLY | 13.5 | PENDING |
| 27 | EXECUTE_BEHAVIOR `projectile/hit_deals_damage_and_expires` | NO_RUNTIME_OBSERVATION | 13.5 | PENDING |
| 28 | ANALYZE_SOURCE `attack_emitter/repeated_attack_can_kill` | CONTRACT_UNDERSTOOD_ONLY | 13.0 | PENDING |
| 29 | EXECUTE_BEHAVIOR `attack_emitter/repeated_attack_can_kill` | NO_RUNTIME_OBSERVATION | 13.0 | PENDING |
| 30 | ANALYZE_DEPENDENCIES `collect_pickup/collect_on_contact` | DEPENDENCY_UNKNOWN | 13.0 | PENDING |
| 31 | ANALYZE_SOURCE `collect_pickup/collect_on_contact` | CONTRACT_UNDERSTOOD_ONLY | 13.0 | PENDING |
| 32 | ANALYZE_SOURCE `health/death` | CONTRACT_UNDERSTOOD_ONLY | 13.0 | PENDING |
| 33 | DESIGN_MUTATION `health/heal_clamped` | NO_MUTATION_KNOWLEDGE | 13.0 | PENDING |
| 34 | ANALYZE_SOURCE `i_frames/iframes_block_damage_within_window` | CONTRACT_UNDERSTOOD_ONLY | 13.0 | PENDING |
| 35 | ANALYZE_SOURCE `stun/death_guard_rejects_stun` | CONTRACT_UNDERSTOOD_ONLY | 13.0 | PENDING |
| 36 | EXECUTE_BEHAVIOR `stun/death_guard_rejects_stun` | NO_RUNTIME_OBSERVATION | 13.0 | PENDING |
| 37 | DESIGN_MUTATION `stun/reentry_extends_without_rebroadcast` | NO_MUTATION_KNOWLEDGE | 13.0 | PENDING |
| 38 | DESIGN_TEST_SCENARIO `stun/reentry_extends_without_rebroadcast` | NO_TEST_SCENARIO | 13.0 | PENDING |
| 39 | DESIGN_MUTATION `projectile/hit_deals_damage_and_expires` | NO_MUTATION_KNOWLEDGE | 12.5 | PENDING |
| 40 | DESIGN_TEST_SCENARIO `projectile/hit_deals_damage_and_expires` | NO_TEST_SCENARIO | 12.5 | PENDING |

## 已排除（不重复安排）
- `save_game/save_slot_persists_world_state` ANALYZE_SOURCE：已有已审批 SOURCE_OBSERVATION
- `save_game/save_slot_persists_world_state` DESIGN_MUTATION：已有已审批 MUTATION_OBSERVATION
- `health/damage` ANALYZE_SOURCE：已有已审批 SOURCE_OBSERVATION
- `health/damage` DESIGN_MUTATION：已有已审批 MUTATION_OBSERVATION
- `openable_door/open` ANALYZE_SOURCE：已有已审批 SOURCE_OBSERVATION
- `openable_door/open` DESIGN_MUTATION：已有已审批 MUTATION_OBSERVATION
- `trigger_switch/latch_once` ANALYZE_SOURCE：已有已审批 SOURCE_OBSERVATION
- `trigger_switch/latch_once` DESIGN_MUTATION：已有已审批 MUTATION_OBSERVATION
- `i_frames/iframes_expire_and_damage_resumes` ANALYZE_SOURCE：已有已审批 SOURCE_OBSERVATION
- `i_frames/iframes_expire_and_damage_resumes` DESIGN_MUTATION：已有已审批 MUTATION_OBSERVATION

