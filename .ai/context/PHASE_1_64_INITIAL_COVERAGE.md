# Phase 1.64 — Initial Coverage Baseline

> 本文件由 `.ai/tmp/p164/initial/gen_initial_coverage.py` 从**本次重新生成**的矩阵快照
> 生成；不沿用任何历史报告数字。机器可读版本：
> `.ai/tmp/p164/initial/coverage_matrix.json`（`generated_at=2026-11-04T16:20:00Z`）。

## 1. 分母与口径

| 项 | 值 |
| --- | --- |
| 正式支持 Feature | 23 |
| 正式支持 Behavior（分母） | 60 |
| 支持集来源 | `Features/*/template.yaml#behavior`（动态推导，非硬编码） |
| 矩阵行数 | 60 |
| 八维独立 | 是（每维各自状态，不构成单一线性等级；缺失 = null/NO_*，不伪造 PASS） |

## 2. 八维覆盖（分子/分母均为本次实测）

| 维度 | 分子 | 分母 | 比例 | 说明 |
| --- | --- | --- | --- | --- |
| Contract | 60 | 60 | 100% | CONTRACT_PRESENT |
| Binding（正式库命中） | 60 | 60 | 100% | 含审批状态判定 |
| Approved Binding | 60 | 60 | 100% | 门禁 APPROVED_BINDING |
| Evidence Verified | 8 | 60 | 13% | 真实 bundle + Validator PASS |
| Signature Verified | 8 | 60 | 13% | Ed25519 sidecar 验签通过 |
| Attestation Verified | 8 | 60 | 13% | 执行证明与 run 绑定 |
| Evaluation VERIFIED_PASS | 4 | 60 | 7% | 完整链路重算 |
| Holdout Available | 1 | 60 | 2% | 已签名封存的数据集 |
| L5 Mutation Killed | 9 | 60 | 15% | KILLED 的 Behavior 数（非 mutation 条数） |
| Fully Covered | 0 | 60 | 0% | 八维全部满足 |

## 3. 各维度状态分布（实测）

| 维度 | 状态分布 |
| --- | --- |
| binding | APPROVED=60 |
| evidence | EVIDENCE_VERIFIED=8，NO_EVIDENCE=52 |
| signature | NO_SIGNATURE=52，SIGNATURE_VERIFIED=8 |
| attestation | ATTESTATION_VERIFIED=8，NO_ATTESTATION=52 |
| evaluation | INVALID_EVIDENCE=1，NOT_EVALUATED=55，VERIFIED_PASS=4 |
| holdout | HOLDOUT_AVAILABLE=1，NO_HOLDOUT=59 |
| mutation | MUTATION_KILLED=9，NOT_TESTED=51 |

## 4. 逐 Behavior 状态（60 行，全部来自矩阵快照）

| Feature | Behavior | Contract | Binding | Evidence | Signature | Attestation | Evaluation | Holdout | Mutation | latest_run_id | Evidence digest | Attestation digest | missing_requirements |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `attack_emitter` | `raycast_hit_deals_damage` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `attack_emitter` | `repeated_attack_can_kill` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `chase_movement` | `approach_target` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `chase_movement` | `hold_without_target` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `collect_pickup` | `collect_on_contact` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | 6520-9e5bf6f3-collect_on_contact | fd9366c9f66919c5 | b025c05539acf112 | holdout |
| `condition_gate` | `partial_conditions_block_output` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `condition_gate` | `all_conditions_fulfill` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `condition_gate` | `condition_fallback_withdraws_output` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `contact_damage` | `damage_on_contact` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | MUTATION_KILLED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout |
| `contact_damage` | `no_damage_without_contact` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `contact_damage` | `damage_amount_is_respected` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `cooldown` | `cooldown_blocks_during_window` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `cooldown` | `cooldown_expires_and_notifies` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `cooldown` | `restart_resets_remaining_window` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `heal_pickup` | `heal_damaged_target` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `health` | `damage` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | INVALID_EVIDENCE | NO_HOLDOUT | MUTATION_KILLED | 6520-c90f5d20-damage | f42379205e960e2f | a2f3947a0217640e | holdout |
| `health` | `heal_clamped` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | 6520-530715a9-heal_clamped | f42379205e960e2f | a2f3947a0217640e | evaluation, holdout, l5_mutation |
| `health` | `death` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | 6520-cdf015c3-death | f42379205e960e2f | a2f3947a0217640e | evaluation, holdout, l5_mutation |
| `health` | `overkill_clamps_at_zero` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | 6520-536eeb7e-overkill_clamps_at_zero | f42379205e960e2f | a2f3947a0217640e | evaluation, holdout, l5_mutation |
| `health` | `post_death_guard` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | MUTATION_KILLED | 6520-1856e5d0-post_death_guard | f42379205e960e2f | a2f3947a0217640e | evaluation, holdout |
| `health_bar` | `initial_health_bar_ratio` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `health_bar` | `damage_updates_health_bar` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `health_bar` | `healing_updates_health_bar` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `health_bar` | `death_empties_health_bar` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `health_bar` | `unbound_bar_reports_no_fill` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `hit_flash` | `hit_flashes_host` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `hit_flash` | `flash_ends_after_duration` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `hit_flash` | `heal_does_not_flash` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `i_frames` | `iframes_block_damage_within_window` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | MUTATION_KILLED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout |
| `i_frames` | `iframes_expire_and_damage_resumes` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `i_frames` | `killing_blow_still_dies` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `knockback` | `knockback_applies_and_signals` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `knockback` | `knockback_decays_to_rest` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `knockback` | `knockback_rejects_invalid` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `moving_platform` | `travel` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `moving_platform` | `round_trip` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `openable_door` | `open` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | HOLDOUT_AVAILABLE | MUTATION_KILLED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation |
| `patrol_movement` | `loop_patrol_cycles_waypoints` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `patrol_movement` | `outbound_leg_moves_at_constant_speed` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `patrol_movement` | `ping_pong_reverses_at_path_end` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `player_movement` | `move_right` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `player_movement` | `stop_on_release` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `projectile` | `in_flight_moves_until_lifetime` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `projectile` | `lifetime_expiry_frees_projectile` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `projectile` | `hit_deals_damage_and_expires` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `save_game` | `save_slot_persists_world_state` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | 6520-f4430a07-save_slot_persists_world_state | abb2b248b34464d2 | 9eaaac7445350760 | holdout |
| `save_game` | `load_slot_restores_world_state` | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | 6520-3b947572-load_slot_restores_world_state | abb2b248b34464d2 | 9eaaac7445350760 | holdout |
| `screen_shake` | `trauma_starts_shake` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `screen_shake` | `shake_stops_after_decay` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `sfx_pool` | `sfx_play_emits_and_occupies` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `sfx_pool` | `sfx_pool_steals_oldest_when_full` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `state_machine` | `transition_to_named_state` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `state_machine` | `previous_backtracks_via_history` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `stun` | `hit_stuns_and_freezes_host` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `stun` | `stun_expires_and_host_resumes` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `stun` | `heal_does_not_stun` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `stun` | `death_guard_rejects_stun` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `stun` | `reentry_extends_without_rebroadcast` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |
| `trigger_switch` | `latch_once` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | - | - | - | verified_evidence, verified_signature, verified_attestation, holdout |
| `trigger_switch` | `toggle_on_second_contact` | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | - | - | - | verified_evidence, verified_signature, verified_attestation, evaluation, holdout, l5_mutation |

## 5. 审计发现：矩阵的两处归因问题（不影响本阶段判定，但影响数字解读）

1. `health/damage` 的 Evaluation 显示 `INVALID_EVIDENCE`（`report=.ai/tmp/eval/44-*/evidence_report.json`），
   而同一行的 Evidence/Signature/Attestation 都是 VERIFIED。根因：矩阵默认扫描整个 `.ai/tmp/eval`，
   一次**其它批次**（mutant/临时任务）的评估报告被当成该行为的最新结论。
2. `trigger_switch/latch_once` 显示 `VERIFIED_PASS`，但 Evidence 是 `NO_EVIDENCE`：评估报告引用的证据
   不在矩阵扫描的 `.ai/tmp/p163_e2e/evidence` 里，两个维度来自不同批次。

结论：**Evaluation 维度的默认数字不可直接采信**，必须按批次用 `--evidence-dir` / `--eval-dir` 限定后重算。
Phase 1.64 的每批矩阵都用显式目录重算（见批次报告），并以此作为覆盖趋势的唯一来源。
