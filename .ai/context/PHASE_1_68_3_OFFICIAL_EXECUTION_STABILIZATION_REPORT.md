# Phase 1.68.3 — Official Execution Stabilization 报告

日期：2026-11-09  
范围：Phase 1.68.3（只到本阶段，不进入 1.68.4 / 1.69）  
最终结论：**PARTIAL PASS**。核心稳定性目标已完成；全量 Python Suite 未完成，Level 3 仍有明确未完成项。

---

## 1. Baseline

| 项目 | 值 |
|---|---|
| HEAD | `541696593994345f916b2aaf42462cf6fc8247c7` |
| 进入阶段时 staged | 0 |
| 进入阶段时 dirty | 1119 |
| Feature / Behavior / 官方检查项 | 32 Feature / 60 Behavior / 145 checks |
| Phase 1.68.2 官方执行 | 5 |
| Phase 1.68.2 官方 PASS | 5 |
| Phase 1.68.2 官方 FAIL / INCOMPLETE / NOT_DECIDED | 0 / 0 / 55 |
| Phase 1.68.2 Attestation Verified | 5 |
| Phase 1.68.2 Official Fully Covered | 5 |
| 原 7 维 Fully Covered | 0 |

重新读取并核对了实际实现：

- `official_plan()`
- `run_official_contract()`
- `run_official_batch()`
- CLI `--official`
- `judge_record_keyed()`
- Official Evidence Bundle / Attestation / Coverage

本阶段没有重新执行五个官方 Behavior，也没有改写任何官方 Bundle 或 Attestation。

---

## 2. Duplicate Conflict Audit

### 2.1 根因

Phase 1.68.2 观察到的 `duplicate_conflict` 来自：

- `.ai/tmp/p168/official/evidence/13224-1ffe73ec-bundle.json`：修复 Evidence 字段前的首轮 `collect_pickup/collect_on_contact` 产物；
- `.ai/tmp/p168/official/evidence/8188-b20b350e-bundle.json`：修复后的重跑产物；
- 旧 Validator 把同一目录下两个不同 Bundle 按 `(feature, behavior)` 聚合，内容不同即报 `2 conflicting records for the same behavior`。

不是同一文件被扫描两次，也不是 Scenario Bundle 与 Official Bundle 混淆。

### 2.2 逐项回答

| 问题 | 结论 |
|---|---|
| 同一文件被重复扫描？ | 否。冲突来自两个不同文件、不同 `bundle_id`、不同 Run。 |
| Scenario 与 Official 混淆？ | 否。Official Bundle 带 `official_contract.kind=OFFICIAL_CONTRACT`；索引 scope 固定为 `official_contract`。 |
| 同一 Run 重复注册？ | 否。5 个 active Run ID 唯一。 |
| Bundle ID 冲突但内容不同？ | 当前数据没有；索引逻辑与测试会明确拒绝。 |
| 索引记录与实际文件不一致？ | Phase 1.68.2 没有 Evidence Index；本次新建并核对 active 5 / superseded 1 / unindexed 0 / conflicts 0。 |
| 影响 Evidence Integrity？ | 否。两个 Bundle 各自的 integrity 均有效；冲突只是目录级聚合歧义。 |
| 影响 Attestation？ | 否。Attestation 绑定各自 Bundle 摘要与 manifest。 |
| 影响 Official Coverage？ | 否。Coverage 一直读取 `results.json` 的最新记录；受影响的是对整目录直接运行的旧 Validator。 |

### 2.3 最小修复

新增 `evidence_index.json`（只登记，不修改 Bundle）：

```text
schema=official_evidence_index, scope=official_contract
active[]      当前官方执行应消费的 Bundle
superseded[]  同 Behavior 的旧 Bundle，保留路径/摘要/被谁取代
unindexed[]   未登记或非官方 Bundle
conflicts[]   同 bundle id 不同内容、active 指向缺失文件等真实冲突
```

实现：

- `.ai/tools/learning/scenario_run.py`
  - `build_official_evidence_index()`：纯函数、幂等、不删除/不改写 Bundle。
  - `rebuild_official_evidence_index()`：写入官方 evidence 目录。
  - `_update_official_index()` / `run_official_batch()` 完成后自动重建。
- `.ai/tools/validator/check_behavior_evidence.py`
  - 目录存在 `evidence_index.json` 时只加载 active；
  - 同一 active 文件重复登记 -> 幂等去重，不报虚假冲突；
  - 索引指向缺失文件、未登记 Bundle、同 ID 不同内容、非官方 Bundle 混入 -> fatal；
  - 没有索引时完全保持 Phase 1.56 的目录扫描语义。

实际生成结果：

```text
active=5, superseded=1, unindexed=0, conflicts=0
superseded: 13224-1ffe73ec-bundle -> 8188-b20b350e-bundle
```

官方目录旧 Validator 复核：

```text
pass=5 fail=0 incomplete=55 (checked=60, artifacts=10, cross_validated=5)
```

55 个 INCOMPLETE 是其余未执行 Behavior 的 `behavior_uncovered`，不是冲突。

### 2.4 测试

新增 `.ai/tools/evaluation/tests/test_official_evidence_index.py`，12 checks 全 PASS：

1. 同一 Bundle 重复扫描；
2. 同一 Bundle 重复登记；
3. 重复重建索引幂等；
4. 不同 Bundle 不同 ID；
5. 不同文件相同 ID + 不同内容；
6. 索引指向不存在文件；
7. Bundle 存在但未登记；
8. Scenario Bundle 混入 Official 目录；
9. 历史 Bundle + 新 Bundle 并存；
10. active 选择最新记录；
11. 真冲突被拒绝；
12. superseded 不删除、不改写。

---

## 3. Official Evidence Status

### 3.1 状态语义

`official_contract_dimension()` 保持以下分支顺序：

| 状态 | 含义 | 是否计入 PASS |
|---|---|---|
| `NO_OFFICIAL_EXECUTION` | 未执行 | 否 |
| `OFFICIAL_EXECUTION_BLOCKED` | 环境/契约前置阻塞 | 否 |
| `OFFICIAL_EXECUTION_FAILED` | 执行失败 | 否 |
| `OFFICIAL_FAIL` | Contract 明确不符合 | 否 |
| `OFFICIAL_INCOMPLETE` | 检查项缺失/无法判定 | 否 |
| `OFFICIAL_EVIDENCE_INVALID` | Evidence 缺失、被改、摘要/签名/契约引用无效 | 否 |
| `OFFICIAL_ATTESTATION_INVALID` | Attestation 缺失/验签失败/绑定错误 | 否 |
| `OFFICIAL_CONTRACT_MISMATCH` | 当前契约与执行时契约不同 | 否 |
| `OFFICIAL_PASS` | 执行 PASS + Evidence 有效 + Attestation 有效 + keyed PASS | 是 |

关键规则：

- Evidence 无效不等于 Contract FAIL；
- Attestation 无效不等于 Contract FAIL；
- 两者都独立计数，且都不能进入 Official PASS；
- 只有完整证据链 + keyed PASS 才计入 `official_contract_fully_covered`；
- `official_contract_fully_covered` 与原 7 维 `fully_covered` 完全分离。

### 3.2 Coverage 新增统计

`.ai/tools/evaluation/coverage_matrix.py` 新增：

```text
official_contract_evidence_invalid
official_contract_attestation_invalid
official_contract_contract_mismatch
official_contract_execution_failed
official_contract_execution_blocked
```

并保留：

```text
official_contract_total / executed / passed / failed / incomplete /
not_decided / attestation_verified / official_contract_fully_covered
```

Markdown 汇总同步增加对应行。

### 3.3 实际结果

```text
total=60
executed=5
passed=5
failed=0
incomplete=0
not_decided=55
evidence_invalid=0
attestation_invalid=0
contract_mismatch=0
execution_failed=0
execution_blocked=0
attestation_verified=5
official_fully_covered=5
原 fully_covered=0
```

### 3.4 测试

`test_official_contract_coverage.py` 扩到 16 checks 全 PASS，新增：

- C6b：Attestation 验签失败不计覆盖；
- C13：Evidence Invalid / Attestation Invalid 独立计数；
- C14：PASS / FAIL / INCOMPLETE / NOT_DECIDED 不混算；
- C15：只有完整 Official PASS 提升 Official Fully Covered，原 Fully Covered 仍为 0。

---

## 4. Evaluation Regression

原 INCOMPLETE：`.ai/tools/evaluation/tests/test_phase160_e2e.py` 缺少必填 `--evidence-dir`。

### 4.1 重新归因

- 该测试确实需要一个已采集证据目录；
- `evidence_eval.main()` 的 `--evidence-dir` 是必要输入；
- 测试文件本身声明了前置采集条件，但缺少默认入口；
- 不是生产代码兼容性问题，也不是 Evaluation 逻辑回归；
- 不能使用历史 Evidence 作为测试输出目录。

### 4.2 修复

测试入口改为：

- 传入 `--evidence-dir`：保持原行为，允许显式输入；
- 不传参数：在 `.ai/tmp` 下新建隔离目录，用真实采集器采集
  `health` / `collect_pickup` / `save_game`，再跑 E1–E5；
- 不读取、不写入 `.ai/tmp/p160_e2e` 或其他历史 Evidence；
- 结束后删除本次 `new_dir()` 创建的临时目录；
- 同时删除本次测试在 `.ai/tmp/eval` 新增的报告目录（按测试开始前后集合差）。

### 4.3 实际执行

```text
E2E-1 ... E2E-5 全部 PASS
5 check(s), 0 failure(s)
run_tests.py --python-only test_phase160_e2e.py -> 1/1 PASS
```

`evaluation` 段随后为 **14/14 PASS**，不再有 INCOMPLETE。

---

## 5. Full Python Regression

### 5.1 测试结构

发现集合：`.ai/tools/**/tests/test_*.py` 共 **96** 个文件。

按本阶段分层策略：

| Level | 内容 | 命令 |
|---|---|---|
| Level 1 | 纯逻辑 / Schema / Judge / Index / Coverage / Planner | `asset_registry`, `feature_registry`, `gameplay_planner`, `knowledge` + 新增纯逻辑测试 |
| Level 2 | Validator / Learning / Evaluation / Runtime 组合行为 | `validator`, `learning`, `evaluation`, `runtime` |
| Level 3 | 真实 Godot / 场景组合 / 端到端生成 | `scene_composer`, `test_phase160_e2e.py`, `test_end_to_end_generation.py` |

Segment 之间有重叠（同一个文件可同时落入多个路径过滤器），因此各段计数之和大于 96；96 个文件均被至少一个段覆盖。

耗时说明：`run_tests.py` 不输出逐测试耗时；本报告只记录可由日志时间核对的
`test_end_to_end_generation.py`（约 29 分钟）和 `scene_composer` 段被停止前的
等待时间，不对其他段伪造秒数。所有 Level 1 / Level 2 命令都在 295s 同步预算内返回。

### 5.2 Level 1 实际结果

| 段 | 结果 |
|---|---|
| `asset_registry` | 11/11 PASS |
| `feature_registry` | 4/4 PASS |
| `gameplay_planner` | 2/2 PASS |
| `knowledge` | 2/2 PASS |
| 新增 `test_keyed_judge.py` | 14 checks PASS |
| 新增 `test_official_evidence_index.py` | 12 checks PASS |
| 新增 `test_official_contract_coverage.py` | 16 checks PASS |

### 5.3 Level 2 实际结果

| 段 | 结果 |
|---|---|
| `validator` | 22/22 PASS |
| `learning` | 11/11 PASS |
| `evaluation` | 14/14 PASS |
| `runtime` | 5/5 PASS |

包含真实 Godot 的 `test_behavior_evidence_stage.py` 也随 `validator` 段通过（缺陷注入、拒绝、逐字节恢复全部 PASS）。

### 5.4 Level 3 实际结果

| 测试 | 结果 |
|---|---|
| `test_phase160_e2e.py` | PASS（5/5 checks，隔离采集） |
| `scene_composer` 段 | **NOT_COMPLETED**：31 个中仅第 1 个 `test_artifact_evidence_validator.py` PASS；第 2 个 `test_behavior_protocol_consistency.py` 长时间无输出，超过 300s 单测预算，进程树被停止 |
| `test_end_to_end_generation.py` | **PASS**（1/1；20:35–21:04，约 29 分钟；ALL PASS，exit 0） |

Level 3 耗时：e2e 生成约 29 分钟；`scene_composer` 段在 300s 单测预算后仍未完成，
被停止；`test_phase160_e2e.py` 的 3 次 Evaluation 内部耗时分别约 2.5s / 2.5s / 2.2s，
外加一次隔离采集。

`scene_composer` 的 30 个未完成测试：

```text
test_behavior_protocol_consistency.py
test_behavior_time_driven.py
test_capability_contract_validator.py
test_chase_movement_behavior.py
test_component_instance_materialization.py
test_component_instance_ownership.py
test_composite.py
test_composite_behavior_evidence.py
test_condition_gate_behavior.py
test_contact_damage_behavior.py
test_entity_root_instance.py
test_external_artifact_evidence.py
test_feature_behavior_evidence.py
test_feature_capability_adoption.py
test_feature_capability_pipeline.py
test_feature_instance_evidence.py
test_health_bar_behavior.py
test_health_behavior.py
test_instance_evidence_reconciliation.py
test_plan_generator.py
test_runtime_instance_evidence.py
test_scene_builder_intent_input.py
test_scene_compatibility_gate.py
test_scene_composer.py
test_scene_intent_capability.py
test_scene_intent_contract.py
test_scene_intent_runtime.py
test_scene_validator_intent_input.py
test_slime_contact_arena.py
test_stun_behavior.py
```

其中 `test_capability_contract_validator.py`、`test_scene_validator_intent_input.py`、
`test_artifact_evidence_validator.py` 等已在 `validator` 段通过；这里按完整
`scene_composer` 段的要求仍列出未在本次 scene_composer 批次中完成的项。

### 5.5 全量结论

**全量 Python Suite 未完成。**

- 单命令全量未作为通过依据；
- Level 1 / Level 2 已实际执行并通过；
- `test_phase160_e2e.py` 与 `test_end_to_end_generation.py` 两个 Level 3 入口均 PASS；
- `scene_composer` Level 3 仍有 30 个测试未完成（见上表）；
- 未删除、跳过或降低任何断言。

---

## 6. Official Evidence Integrity

只读审计，不重新执行五个 Behavior。

| Behavior | Run | Run 目录 | Actions | Expected | Integrity | Keyed | Evidence | Attestation | Coverage | Checks |
|---|---|---|---|---|---|---|---|---|---|---|
| `collect_pickup/collect_on_contact` | `d58ed649` | 存在 | 官方一致 | 官方一致 | 通过 | PASS | VERIFIED | VERIFIED | OFFICIAL_PASS | 2 |
| `contact_damage/damage_amount_is_respected` | `b0a72130` | 存在 | 官方一致 | 官方一致 | 通过 | PASS | VERIFIED | VERIFIED | OFFICIAL_PASS | 2 |
| `contact_damage/damage_on_contact` | `6519d2e8` | 存在 | 官方一致 | 官方一致 | 通过 | PASS | VERIFIED | VERIFIED | OFFICIAL_PASS | 2 |
| `heal_pickup/heal_damaged_target` | `f5f88ab5` | 存在 | 官方一致 | 官方一致 | 通过 | PASS | VERIFIED | VERIFIED | OFFICIAL_PASS | 2 |
| `openable_door/open` | `573173f3` | 存在 | 官方一致 | 官方一致 | 通过 | PASS | VERIFIED | VERIFIED | OFFICIAL_PASS | 2 |

检查项：

1. Run 目录存在；
2. 5 个 Run ID 唯一；
3. Behavior / Feature 绑定正确；
4. `contract_actions` 与当前官方 Contract 完全一致；
5. `contract_expected` 与当前官方 Contract 完全一致；
6. Bundle `integrity.payload_sha256` 重算通过；
7. `observation_digest` 与观测一致；
8. keyed Judge 为 PASS；
9. Evidence 签名验证通过；
10. Attestation 签名与 manifest / Bundle / contract 绑定通过；
11. Coverage 重新验证为 `OFFICIAL_PASS`；
12. 没有为审计重新生成或覆盖任何证据。

Evidence Index：

```text
sha256(evidence_index.json) = 0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910
active=5 superseded=1 unindexed=0 conflicts=0
```

---

## 7. Historical Compatibility

| 检查项 | 结果 |
|---|---|
| P4/P5 历史 Scenario | 未写入；只读 |
| 历史 Scenario Evidence | 未修改 |
| 历史 Scenario Attestation | 未修改 |
| 历史 Scenario Evaluation | 未修改；p166 summary 仍为 5/5 evaluated_pass，p167 P5 仍为 4/4 |
| Phase 1.56 p157 Bundle | integrity 通过；23 features / 60 behaviors；mtime 仍为 2026-11-02 |
| 原 `judge_record()` | 未修改 |
| 原 Coverage 七维公式 | 未修改；`fully_covered=0` |
| Official Coverage | 独立字段，未污染 Scenario Coverage |
| Official Evidence Index | 只作用于官方 evidence 目录，不覆盖 Scenario Evidence |

历史文件 mtime 核对：

```text
p157-real.json          2026-11-02 01:54
p166/evaluation.json    2026-11-06 19:21
p167/scenario_results   2026-11-08 02:50
```

本阶段测试曾由既有 `test_scenario_run.py` 在 `.ai/tmp/p166/runs/` 写出一个
临时 `plan.json`（`f80dc751-...`），已确认只有 plan、不是 Evidence，并已删除该
本次测试新建目录；p166 历史 Evidence / Evaluation 未变。

---

## 8. Repo Guard

只读检查：

```text
HEAD    = 541696593994345f916b2aaf42462cf6fc8247c7
STAGED  = 0
DIRTY   = 1102
```

本阶段代码/测试变更：

```text
 M .ai/tools/learning/scenario_run.py
?? .ai/tools/evaluation/tests/test_official_evidence_index.py
?? .ai/tools/evaluation/tests/test_official_contract_coverage.py
?? .ai/tools/evaluation/tests/test_phase160_e2e.py
?? .ai/tools/validator/check_behavior_evidence.py
?? .ai/tools/evaluation/coverage_matrix.py
```

本阶段产物/索引：

```text
.ai/tmp/p168/official/evidence/evidence_index.json
.ai/tmp/p168/official/legacy_validator_report_indexed.json
.ai/tmp/p168/coverage/coverage_matrix.json|md
.ai/tmp/p168/scene_composer_tests.log
.ai/tmp/p168/e2e_generation_tests.log
.ai/context/PHASE_1_68_3_OFFICIAL_EXECUTION_STABILIZATION_REPORT.md
```

边界确认：

- 未修改官方 Contract；
- 未修改产品 Feature 源码；
- 未修改 Scenario 语义；
- 未修改 Scenario Generator / Validator 既有规则；
- 未修改旧 `judge_record()`；
- 未修改原 `fully_covered` 七维公式；
- 未重新生成 P4/P5 历史场景；
- 未删除或改写历史 Bundle / Attestation；
- 未执行 `git add` / `commit` / `push` / `reset` / `clean`。

说明：工作区在本阶段开始前已有大量历史 dirty 条目；最终 dirty 为 1102，
其中包含本阶段代码、测试、索引和报告，也包含 Level 3 测试清理其拥有的临时目录；
这不代表历史 Evidence/Evaluation 或产品文件被修改（§7 已核对历史路径无新写入）。

---

## 9. Remaining Issues

1. **Level 3 scene_composer 未完成**：31 个测试中仅 1 个完成；`test_behavior_protocol_consistency.py` 超过 300s 且进程树被停止，其余 30 个未执行。不能宣称全量 Python Suite 通过。
2. **scene_composer 仍阻断全量 Suite**：虽然 `test_end_to_end_generation.py` 已 PASS（约 29 分钟），`scene_composer` 的 30 个未完成测试仍使全量 Python Suite 不能声明通过。
3. **Official Evidence Index 是选择清单，不是签名对象**：它不改变 Bundle/Attestation 的密码学验证；若索引本身被篡改，Validator 仍会验证 active Bundle 的 integrity 与签名，但不会验证索引作者。当前索引仅作为本地路由清单，信任级别仍为 `LOCAL_ISOLATED`。
4. **主动失败无 Bundle 时索引策略**：若某 Behavior 最新执行失败且没有 Bundle，`results.json` 没有历史 active 记录，重建索引会把旧 Bundle 标为 unindexed。当前 5 条均为成功记录，未触发；后续扩展时应决定“保留上一次成功证据”还是“明确无 active”。
5. **55 个 Behavior 未执行**：本阶段不扩大 Behavior 覆盖，Official NOT_DECIDED 仍为 55。
6. **未进入 B2 / 剩余 42 规则族 / Knowledge 审批 / 信任升级**。

---

## 10. Final Verdict

**PARTIAL PASS**

已完成：

- 查明并修复目录级 `duplicate_conflict` 的真实根因；
- 用 active / superseded / unindexed / conflicts 索引保留历史 Bundle 的审计链；
- 将 Evidence Invalid、Attestation Invalid、Contract Mismatch、Execution Failed/Blocked 从 PASS/FAIL 中独立统计；
- 修复 Evaluation 唯一 INCOMPLETE 测试入口，并用隔离采集真实执行；
- 只读证明五个官方 PASS 的 Run、Evidence、Attestation、Keyed Judge、Coverage 链路完整；
- 保持原 7 维 Fully Covered = 0，历史 p157/p166/p167 未被改写。

未完成：

- `scene_composer` Level 3 仍有 30 个测试未完成；
- 因此不能声明“全量 Python Suite 通过”（`test_end_to_end_generation.py` 本身已 PASS）。

这是本阶段的最终状态。停止在此处，等待用户检查与授权。

---

## 附录 A：完整 Python 测试文件清单（96）

```text
.ai/tools/asset_registry/tests/test_asset_binding.py
.ai/tools/asset_registry/tests/test_asset_index.py
.ai/tools/asset_registry/tests/test_asset_query.py
.ai/tools/asset_registry/tests/test_binding_schema.py
.ai/tools/asset_registry/tests/test_binding_schema_checks.py
.ai/tools/asset_registry/tests/test_binding_scope.py
.ai/tools/asset_registry/tests/test_check_assets.py
.ai/tools/asset_registry/tests/test_hardening.py
.ai/tools/asset_registry/tests/test_query_api.py
.ai/tools/asset_registry/tests/test_scan_assets.py
.ai/tools/asset_registry/tests/test_slots_config.py
.ai/tools/e2e/tests/test_end_to_end_generation.py
.ai/tools/evaluation/mutation/tests/test_mutation_harness.py
.ai/tools/evaluation/mutation/tests/test_mutation_integration.py
.ai/tools/evaluation/tests/test_coverage_matrix.py
.ai/tools/evaluation/tests/test_cross_binding.py
.ai/tools/evaluation/tests/test_evaluation_runner.py
.ai/tools/evaluation/tests/test_evaluation_scoring.py
.ai/tools/evaluation/tests/test_evidence_adapter.py
.ai/tools/evaluation/tests/test_evidence_eval.py
.ai/tools/evaluation/tests/test_evidence_signature.py
.ai/tools/evaluation/tests/test_holdout_registry.py
.ai/tools/evaluation/tests/test_holdout_signature.py
.ai/tools/evaluation/tests/test_official_contract_coverage.py
.ai/tools/evaluation/tests/test_official_evidence_index.py
.ai/tools/evaluation/tests/test_phase160_e2e.py
.ai/tools/feature_registry/tests/test_composition.py
.ai/tools/feature_registry/tests/test_discovery_to_binding.py
.ai/tools/feature_registry/tests/test_feature_discovery.py
.ai/tools/feature_registry/tests/test_feature_pipeline.py
.ai/tools/gameplay_planner/tests/test_gameplay_planner.py
.ai/tools/gameplay_planner/tests/test_level_planner.py
.ai/tools/knowledge/behavior_verification/tests/test_knowledge_store.py
.ai/tools/learning/tests/test_dependency_graph.py
.ai/tools/learning/tests/test_feedback.py
.ai/tools/learning/tests/test_knowledge_store.py
.ai/tools/learning/tests/test_mutation_candidates.py
.ai/tools/learning/tests/test_official_contract_run.py
.ai/tools/learning/tests/test_planner.py
.ai/tools/learning/tests/test_result_analysis.py
.ai/tools/learning/tests/test_scenario_generator.py
.ai/tools/learning/tests/test_scenario_run.py
.ai/tools/learning/tests/test_scenario_validator.py
.ai/tools/learning/tests/test_source_analysis.py
.ai/tools/runtime/tests/test_asset_self_repair.py
.ai/tools/runtime/tests/test_runtime_playtest.py
.ai/tools/runtime/tests/test_self_repair.py
.ai/tools/scene_composer/tests/test_artifact_evidence_validator.py
.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py
.ai/tools/scene_composer/tests/test_behavior_time_driven.py
.ai/tools/scene_composer/tests/test_capability_contract_validator.py
.ai/tools/scene_composer/tests/test_chase_movement_behavior.py
.ai/tools/scene_composer/tests/test_component_instance_materialization.py
.ai/tools/scene_composer/tests/test_component_instance_ownership.py
.ai/tools/scene_composer/tests/test_composite.py
.ai/tools/scene_composer/tests/test_composite_behavior_evidence.py
.ai/tools/scene_composer/tests/test_condition_gate_behavior.py
.ai/tools/scene_composer/tests/test_contact_damage_behavior.py
.ai/tools/scene_composer/tests/test_entity_root_instance.py
.ai/tools/scene_composer/tests/test_external_artifact_evidence.py
.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py
.ai/tools/scene_composer/tests/test_feature_capability_adoption.py
.ai/tools/scene_composer/tests/test_feature_capability_pipeline.py
.ai/tools/scene_composer/tests/test_feature_instance_evidence.py
.ai/tools/scene_composer/tests/test_health_bar_behavior.py
.ai/tools/scene_composer/tests/test_health_behavior.py
.ai/tools/scene_composer/tests/test_instance_evidence_reconciliation.py
.ai/tools/scene_composer/tests/test_plan_generator.py
.ai/tools/scene_composer/tests/test_runtime_instance_evidence.py
.ai/tools/scene_composer/tests/test_scene_builder_intent_input.py
.ai/tools/scene_composer/tests/test_scene_compatibility_gate.py
.ai/tools/scene_composer/tests/test_scene_composer.py
.ai/tools/scene_composer/tests/test_scene_intent_capability.py
.ai/tools/scene_composer/tests/test_scene_intent_contract.py
.ai/tools/scene_composer/tests/test_scene_intent_runtime.py
.ai/tools/scene_composer/tests/test_scene_validator_intent_input.py
.ai/tools/scene_composer/tests/test_slime_contact_arena.py
.ai/tools/scene_composer/tests/test_stun_behavior.py
.ai/tools/validator/execution/tests/test_attacks.py
.ai/tools/validator/provenance/tests/test_provenance_attacks.py
.ai/tools/validator/provenance/tests/test_provenance_core.py
.ai/tools/validator/tests/test_baseline_lifecycle.py
.ai/tools/validator/tests/test_baseline_signature.py
.ai/tools/validator/tests/test_behavior_evidence_stage.py
.ai/tools/validator/tests/test_binding_candidates.py
.ai/tools/validator/tests/test_cross_layer_contract.py
.ai/tools/validator/tests/test_e2e_ownership.py
.ai/tools/validator/tests/test_env_paths.py
.ai/tools/validator/tests/test_evidence_cross_validation.py
.ai/tools/validator/tests/test_keyed_judge.py
.ai/tools/validator/tests/test_orchestration_trace.py
.ai/tools/validator/tests/test_run_tests_evidence.py
.ai/tools/validator/tests/test_run_workspace.py
.ai/tools/validator/tests/test_trace_baselines.py
.ai/tools/validator/tests/test_trace_bindings.py
.ai/tools/validator/tests/test_unified_validator.py
```
