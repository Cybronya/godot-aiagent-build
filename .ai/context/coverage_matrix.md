# Phase 1.63 Coverage Matrix

生成时间：2026-11-04T03:22:49Z

## 汇总（分母 = 动态正式支持集 60 Behavior / 23 Feature）

| 指标 | 数值 | 比例 |
| --- | --- | --- |
| Contract | 60 | 100% |
| Binding（含非 APPROVED） | 60 | 100% |
| Approved Binding | 60 | 100% |
| Evidence Verified | 8 | 13% |
| Signature Verified | 8 | 13% |
| Attestation Verified | 8 | 13% |
| Evaluation VERIFIED_PASS | 5 | 8% |
| Holdout Available | 1 | 2% |
| L5 Mutation Killed | 9 | 15% |
| L5 Mutation Invalid | 0 | 0% |
| Fully Covered | 0 | 0% |
| Behaviors With Gaps | 60 | 100% |

## 逐 Behavior 状态

| Feature | Behavior | Contract | Binding | Evidence | Signature | Attestation | Evaluation | Holdout | Mutation | 下一步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| attack_emitter | raycast_hit_deals_damage | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| attack_emitter | repeated_attack_can_kill | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| chase_movement | approach_target | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| chase_movement | hold_without_target | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| collect_pickup | collect_on_contact | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | collect an independent batch and seal a fresh holdout datase |
| condition_gate | partial_conditions_block_output | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| condition_gate | all_conditions_fulfill | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| condition_gate | condition_fallback_withdraws_output | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| contact_damage | damage_on_contact | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | MUTATION_KILLED | collect real evidence (feature_behavior_evidence.py --featur |
| contact_damage | no_damage_without_contact | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| contact_damage | damage_amount_is_respected | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| cooldown | cooldown_blocks_during_window | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| cooldown | cooldown_expires_and_notifies | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| cooldown | restart_resets_remaining_window | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| heal_pickup | heal_damaged_target | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| health | damage | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | collect an independent batch and seal a fresh holdout datase |
| health | heal_clamped | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | run evidence_eval.py for this behavior; collect an independe |
| health | death | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | run evidence_eval.py for this behavior; collect an independe |
| health | overkill_clamps_at_zero | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | run evidence_eval.py for this behavior; collect an independe |
| health | post_death_guard | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | NOT_EVALUATED | NO_HOLDOUT | MUTATION_KILLED | run evidence_eval.py for this behavior; collect an independe |
| health_bar | initial_health_bar_ratio | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| health_bar | damage_updates_health_bar | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| health_bar | healing_updates_health_bar | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| health_bar | death_empties_health_bar | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| health_bar | unbound_bar_reports_no_fill | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| hit_flash | hit_flashes_host | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| hit_flash | flash_ends_after_duration | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| hit_flash | heal_does_not_flash | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| i_frames | iframes_block_damage_within_window | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | MUTATION_KILLED | collect real evidence (feature_behavior_evidence.py --featur |
| i_frames | iframes_expire_and_damage_resumes | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| i_frames | killing_blow_still_dies | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| knockback | knockback_applies_and_signals | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| knockback | knockback_decays_to_rest | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| knockback | knockback_rejects_invalid | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| moving_platform | travel | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| moving_platform | round_trip | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| openable_door | open | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | HOLDOUT_AVAILABLE | MUTATION_KILLED | collect real evidence (feature_behavior_evidence.py --featur |
| patrol_movement | loop_patrol_cycles_waypoints | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| patrol_movement | outbound_leg_moves_at_constant_speed | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| patrol_movement | ping_pong_reverses_at_path_end | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| player_movement | move_right | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| player_movement | stop_on_release | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| projectile | in_flight_moves_until_lifetime | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| projectile | lifetime_expiry_frees_projectile | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| projectile | hit_deals_damage_and_expires | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| save_game | save_slot_persists_world_state | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | collect an independent batch and seal a fresh holdout datase |
| save_game | load_slot_restores_world_state | CONTRACT_PRESENT | APPROVED | EVIDENCE_VERIFIED | SIGNATURE_VERIFIED | ATTESTATION_VERIFIED | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | collect an independent batch and seal a fresh holdout datase |
| screen_shake | trauma_starts_shake | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| screen_shake | shake_stops_after_decay | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| sfx_pool | sfx_play_emits_and_occupies | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| sfx_pool | sfx_pool_steals_oldest_when_full | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| state_machine | transition_to_named_state | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| state_machine | previous_backtracks_via_history | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| stun | hit_stuns_and_freezes_host | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| stun | stun_expires_and_host_resumes | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| stun | heal_does_not_stun | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| stun | death_guard_rejects_stun | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| stun | reentry_extends_without_rebroadcast | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
| trigger_switch | latch_once | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | VERIFIED_PASS | NO_HOLDOUT | MUTATION_KILLED | collect real evidence (feature_behavior_evidence.py --featur |
| trigger_switch | toggle_on_second_contact | CONTRACT_PRESENT | APPROVED | NO_EVIDENCE | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | NO_HOLDOUT | NOT_TESTED | collect real evidence (feature_behavior_evidence.py --featur |
