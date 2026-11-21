# Phase 1.71 — Preflight Baseline

审计/实施开始时间：2026-11-14T20:53:30+08:00

## Git 状态

| 项目 | 值 |
|---|---|
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| origin/master (local tracking ref) | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Ahead / Behind | `0 / 0` |
| Staged | 0 |
| Modified | 26 |
| Deleted | 0 |
| Untracked | 138 |
| Conflicts | 0 |
| `git diff` SHA256 | `00aaa1062c97804a3833226193ebd59e5d370d39faeab808bf1532168edd53c4` |
| `git status --porcelain` SHA256 | `8e50dcced76ea24d75d2b91f6047499b904b7130a2f5fd22e685f51d4d64755c` |

### Remote synchronization

- 本地 `origin/master` tracking ref 与 HEAD 相同，ahead/behind = `0 / 0`。
- 本阶段未执行 `git fetch`，因此**实际远程服务器 HEAD 状态为 UNKNOWN**；不能把本地 tracking ref 当作远端已 Push 的独立证明。

### Full current status snapshot

```text
 M .ai/context/CURRENT_TASK.md
 M .ai/context/FEATURE_BEHAVIOR_COVERAGE.md
 M .ai/context/WORK_STATE.md
 M .ai/context/feature_graph.json
 M .ai/context/feature_index.json
 M .ai/learning/feedback.json
 M .ai/learning/result_analysis.json
 M .ai/learning/results/s-16f6576c8683f7bc.json
 M .ai/learning/results/s-37cd4dc9f084950e.json
 M .ai/learning/results/s-7771e41885fcd58e.json
 M .ai/learning/results/s-8b9f108ecb56beb2.json
 M .ai/learning/results/s-e6eb3fc5c8e82e32.json
 M .ai/learning/scenario_results.json
 M .ai/learning/scenario_validation.json
 M .ai/learning/scenarios.json
 M .ai/learning/source_analysis/collect_pickup/collect_on_contact.json
 M .ai/learning/source_analysis/contact_damage/damage_amount_is_respected.json
 M .ai/learning/source_analysis/contact_damage/damage_on_contact.json
 M .ai/learning/source_analysis/heal_pickup/heal_damaged_target.json
 M .ai/tools/scene_composer/tests/test_feature_capability_adoption.py
 M .ai/tools/scene_composer/tests/test_feature_capability_pipeline.py
 M .ai/tools/scene_composer/tests/test_scene_composer.py
 M AI_ENTRY.md
 M Features/attack_emitter/feature.yaml
 M Features/knockback/feature.yaml
 M Features/save_game/feature.yaml
 M Features/sfx_pool/feature.yaml
 M Features/state_machine/feature.yaml
 M Features/trigger_switch/template.yaml
 M project.godot
?? .ai/context/PHASE_1_55_AUDIT.md
?? .ai/context/PHASE_1_56_COMPLETION_REPORT.md
?? .ai/context/PHASE_1_57_COMPLETION_REPORT.md
?? .ai/context/PHASE_1_58_COMPLETION_REPORT.md
?? .ai/context/PHASE_1_59_AUDIT.md
?? .ai/context/PHASE_1_59_COMPLETION_REPORT.md
?? .ai/context/PHASE_1_60_AUDIT.md
?? .ai/context/PHASE_1_60_COMPLETION_REPORT.md
?? .ai/context/PHASE_1_61_AUDIT.md
?? .ai/context/PHASE_1_61_COMPLETION_REPORT.md
?? .ai/context/PHASE_1_62_AUDIT.md
?? .ai/context/PHASE_1_62_COMPLETION.md
?? .ai/context/PHASE_1_63_ATTACK_TESTS.md
?? .ai/context/PHASE_1_63_AUDIT.md
?? .ai/context/PHASE_1_63_COMPLETION.md
?? .ai/context/PHASE_1_63_COVERAGE_REPORT.md
?? .ai/context/PHASE_1_64_ATTACK_TESTS.md
?? .ai/context/PHASE_1_64_AUDIT.md
?? .ai/context/PHASE_1_64_BATCH_1_REPORT.md
?? .ai/context/PHASE_1_64_BEHAVIOR_INVENTORY.md
?? .ai/context/PHASE_1_64_COMPLETION.md
?? .ai/context/PHASE_1_64_COVERAGE_TREND.md
?? .ai/context/PHASE_1_64_INITIAL_COVERAGE.md
?? .ai/context/PHASE_1_64_VERIFICATION_PLAN.md
?? .ai/context/PHASE_1_65_ARCHITECTURE.md
?? .ai/context/PHASE_1_65_ATTACK_TESTS.md
?? .ai/context/PHASE_1_65_AUDIT.md
?? .ai/context/PHASE_1_65_COMPLETION.md
?? .ai/context/PHASE_1_65_DEPENDENCY_REPORT.md
?? .ai/context/PHASE_1_65_KNOWLEDGE_REPORT.md
?? .ai/context/PHASE_1_65_LEARNING_PILOT.md
?? .ai/context/PHASE_1_65_LEARNING_PLAN.md
?? .ai/context/PHASE_1_65_SOURCE_ANALYSIS.md
?? .ai/context/PHASE_1_67_1_BEHAVIOR_COVERAGE_AUDIT.md
?? .ai/context/PHASE_1_67_2_P5_EXECUTION_REPORT.md
?? .ai/context/PHASE_1_69_B_REPOSITORY_SYNC_AUDIT.md
?? .ai/context/PHASE_1_69_C_CONTROLLED_GIT_SYNCHRONIZATION.md
?? .ai/context/PHASE_1_69_D_PUSH_AND_REMOTE_VERIFICATION.md
?? .ai/context/PHASE_1_69_D_PUSH_PREFLIGHT.md
?? .ai/context/coverage_matrix.json
?? .ai/context/coverage_matrix.md
?? .ai/context/phase_1_63_support_inventory.json
?? .ai/context/phase_1_64_behavior_taxonomy.json
?? .ai/knowledge/behavior_learning/candidates/k-020ba095d5f47944.json
?? .ai/knowledge/behavior_learning/candidates/k-021f3611e98d5190.json
?? .ai/knowledge/behavior_learning/candidates/k-121fe43917cf39d6.json
?? .ai/knowledge/behavior_learning/candidates/k-1898a32edbdb90a3.json
?? .ai/knowledge/behavior_learning/candidates/k-1c9dbc005d590e6f.json
?? .ai/knowledge/behavior_learning/candidates/k-1da790443313b658.json
?? .ai/knowledge/behavior_learning/candidates/k-399a327c1c82a02f.json
?? .ai/knowledge/behavior_learning/candidates/k-3a5a0c61052a6b5d.json
?? .ai/knowledge/behavior_learning/candidates/k-487ee00eb480757d.json
?? .ai/knowledge/behavior_learning/candidates/k-49ae13c75b074e11.json
?? .ai/knowledge/behavior_learning/candidates/k-597c32094c354749.json
?? .ai/knowledge/behavior_learning/candidates/k-6791f3d0dcd0b9be.json
?? .ai/knowledge/behavior_learning/candidates/k-6973c38b5870daf7.json
?? .ai/knowledge/behavior_learning/candidates/k-6a0ac1f282775640.json
?? .ai/knowledge/behavior_learning/candidates/k-704ab04d0f240fec.json
?? .ai/knowledge/behavior_learning/candidates/k-7c76150f56011851.json
?? .ai/knowledge/behavior_learning/candidates/k-8b34a1398a9e443f.json
?? .ai/knowledge/behavior_learning/candidates/k-94bfab698e9cf811.json
?? .ai/knowledge/behavior_learning/candidates/k-9ad6ca517ba5e2ee.json
?? .ai/knowledge/behavior_learning/candidates/k-c6268bc9977aa784.json
?? .ai/knowledge/behavior_learning/candidates/k-cb1aa1065cddfa88.json
?? .ai/knowledge/behavior_learning/candidates/k-d8832ff2e5be83b7.json
?? .ai/knowledge/behavior_learning/candidates/k-d97481ab1909655a.json
?? .ai/knowledge/behavior_learning/candidates/k-daf186b664cc1398.json
?? .ai/knowledge/behavior_learning/candidates/k-db0591a63d91db8c.json
?? .ai/knowledge/behavior_learning/candidates/k-de485172db537838.json
?? .ai/knowledge/behavior_learning/candidates/k-f690cfaca973aebf.json
?? .ai/knowledge/behavior_learning/records/k-8423097baa8ec620.json
?? .ai/knowledge/behavior_learning/records/k-875dbe2de3b9fca9.json
?? .ai/knowledge/behavior_learning/records/k-af3decf8ebc135bd.json
?? .ai/knowledge/behavior_learning/records/k-e219d71a96f8bd0d.json
?? .ai/learning/results/s-9efdc90351f7112e.json
?? .ai/learning/results/s-d2fe30d380537d07.json
?? .ai/learning/results/s-d503c62564c391ef.json
?? .ai/learning/results/s-eef9972034da734b.json
?? .ai/learning/scenarios/index.json
?? .ai/learning/scenarios/s-9efdc90351f7112e.json
?? .ai/learning/scenarios/s-d2fe30d380537d07.json
?? .ai/learning/scenarios/s-d503c62564c391ef.json
?? .ai/learning/scenarios/s-eef9972034da734b.json
?? .ai/learning/validation/s-9efdc90351f7112e.json
?? .ai/learning/validation/s-d2fe30d380537d07.json
?? .ai/learning/validation/s-d503c62564c391ef.json
?? .ai/learning/validation/s-eef9972034da734b.json
?? .cloud-attachments/
?? .workbuddy-ai/
?? Features/anima_behaviour/
?? Features/attribute_editor/
?? Features/audio_player_pool/
?? Features/blackboard/
?? Features/clean_copy/
?? Features/flying_letter/
?? Features/pedestal_interaction/
?? Features/pickable_audio/
```

## Library Baseline

| 项目 | 值 |
|---|---:|
| Source Repositories | 77 |
| Source Files | 7452 |
| References Files | 6813 |
| Catalog Entries | 7270 |
| Unique Entries | 6813 |
| Duplicate Entries | 457 |
| INDEX Rows | 6813 |
| Missing Reference | 0 |
| Missing Source | 0 |
| SHA256 Mismatch | 0 |

## Key File SHA256

| File | SHA256 |
|---|---|
| `.ai/skills/foundation/godot-gdscript/tools/github_collector.py` | `33b922522fcc65d9af1f06526c3a432b00ace2e429f654d3b41eabf0f2147f36` |
| `.ai/tools/feature_registry/search_assets.py` | `2448bd98bb9198343ddaa89c490ea15c8643608e7fa77fbd02573946a5b380e9` |
| `.ai/tools/learning/gd_parse.py` | `70d509a6d9a4d98b670dc863bcff8017a6203ff1ef8dfbfdd67a9a2bd9a5e67b` |
| `.ai/tools/learning/source_analysis.py` | `1a236f66cbd1e477f5e32f7c613052477c94350101344f93c875b48107bdde1a` |
| `.ai/tools/learning/knowledge_v2.py` | `9f613e98cc5f747d0f6801931b2a3d24a3f06bc7ec4fcebb0eb26557f5fb9302` |
| `.ai/tools/learning/feedback.py` | `56b52cbe666a2355ba3df3c131cb8080273f51aab43f425a249ccc63d5849eba` |
| `.ai/tools/learning/planner.py` | `3b1bfc9052607a57fc17a642b3df50539e320790564edc7f1f6cc9bacbfd2c8e` |

## Existing workspace changes

当前 modified/untracked 均为 Phase 1.71 之前已存在的工作区状态；本报告只建立基线，不清理、不覆盖、不暂存这些文件。

## Known risks

- 当前工作区有 26 个 modified、138 个 untracked；路径级完整快照已包含在上方 status block。
- 历史 Catalog 的 `commit_sha` 为 12 位；本阶段新数据补 `commit_sha_full`，旧数据不伪造完整 SHA。
- 四个仓库本地缺少 LICENSE/COPYING 文本；只能标记缺失，不能推断已取得完整许可证。
- 严格实施修改只允许 Phase 1.71 相关代码、测试与报告；不得全量重建 Catalog。
