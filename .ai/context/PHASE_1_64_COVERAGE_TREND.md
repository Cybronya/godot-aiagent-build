# Phase 1.64 — Coverage Trend

口径说明（重要）：本文件所有数字都来自**同一脚本、同一口径**重算的八维矩阵快照，
差异只在证据目录：

- Before：`.ai/tmp/p164/before/matrix/coverage_matrix.json`（仅 1.63 E2E 证据，评估报告按 1.63 证据重算）
- After：`.ai/tmp/p164/batch1/matrix_after/coverage_matrix.json`（+ Batch 1 证据、评估、runs、mutation 12 条）

不使用 `.ai/context/coverage_matrix.json`（1.63 生成）作为对比基线，因为它默认扫描整个
`.ai/tmp/eval`，会把其它批次临时评估报告算进来（审计 P2）。p164 的 before/after 都已避开这一点。

## 1. 八维总量

| 维度 | Before | After | Δ | 分母 |
| --- | --- | --- | --- | --- |
| Contract | 60 | 60 | 0 | 60 |
| Binding（获批） | 60 | 60 | 0 | 60 |
| Evidence Verified | 8 | **12** | **+4** | 60 |
| Signature Verified | 8 | **12** | **+4** | 60 |
| Attestation Verified | 8 | **12** | **+4** | 60 |
| Evaluation VERIFIED_PASS | 8 | **12** | **+4** | 60 |
| Holdout Available | 1 | 1 | 0 | 60 |
| L5 Mutation Killed（Behavior 数） | 9 | **10** | **+1** | 60 |
| Mutation Invalid | 0 | 0 | 0 | 60 |
| **Fully Covered** | **0** | **1** | **+1** | 60 |

比例（分母固定 60，动态支持集）：Evidence/Signature/Attestation/Evaluation 各 **20%**（12/60），
Mutation Killed **17%**（10/60），Fully Covered **1.7%**（1/60）。

## 2. 状态分布变化

| 维度 | Before | After |
| --- | --- | --- |
| Evidence | `NO_EVIDENCE=52`、`EVIDENCE_VERIFIED=8` | `NO_EVIDENCE=48`、`EVIDENCE_VERIFIED=12` |
| Signature | `NO_SIGNATURE=52`、`VERIFIED=8` | `NO_SIGNATURE=48`、`VERIFIED=12` |
| Attestation | `NO_ATTESTATION=52`、`VERIFIED=8` | `NO_ATTESTATION=48`、`VERIFIED=12` |
| Evaluation | `NOT_EVALUATED=52`、`VERIFIED_PASS=8` | `NOT_EVALUATED=48`、`VERIFIED_PASS=12` |
| Mutation | `NOT_TESTED=51`、`KILLED=9` | `NOT_TESTED=50`、`KILLED=10` |
| Holdout | `NO_HOLDOUT=59`、`AVAILABLE=1` | 不变 |

## 3. 逐 Behavior 增量（Before → After）

| Behavior | Evidence | Eval | Mutation | 说明 |
| --- | --- | --- | --- | --- |
| `i_frames/iframes_block_damage_within_window` | NO → **VERIFIED** | NOT → **PASS** | KILLED（M09，不变） | 新增证据 + 签名 + attestation |
| `i_frames/iframes_expire_and_damage_resumes` | NO → **VERIFIED** | NOT → **PASS** | NOT_TESTED → **KILLED（M11）** | 本阶段同时补证据与 mutation |
| `i_frames/killing_blow_still_dies` | NO → **VERIFIED** | NOT → **PASS** | NOT_TESTED（仍无） | 证据有、mutation 无 → 不成 Fully Covered |
| `openable_door/open` | NO → **VERIFIED** | NOT → **PASS** | KILLED（M05→M12） | **唯一 Fully Covered**（八维齐全） |
| `save_game/save_slot_persists_world_state` | 已 VERIFIED（1.63） | PASS（重算） | KILLED（M06） | 本批为重跑复核 |
| `save_game/load_slot_restores_world_state` | 已 VERIFIED（1.63） | PASS（重算） | KILLED（M07） | 本批为重跑复核 |
| `health/*`（5）与 `collect_pickup/collect_on_contact` | 已 VERIFIED（1.63） | 1.63 的 4 条 PASS → 本口径 **8 条 PASS** | 3 条 KILLED | 1.63 只给 3 个 Feature 各建一条评估任务；本阶段用已审批 Binding 为 8 条 Behavior 全部建任务后重算 |

> `health/*` 的 8 → 12 里有 4 条是「原本就有证据、只是没有逐 Behavior 的评估任务」。
> 这不是新证据，而是**同一批证据上补齐了评估覆盖**；趋势表如实分列，不把它算成新采集。

## 4. Knowledge 覆盖

| 指标 | 值 |
| --- | --- |
| Knowledge 记录 | 7（Batch 1 的 6 条 + `trigger_switch/latch_once`） |
| 来源分布 | CONTRACT_FACT=31、TEST_OBSERVATION=12、MUTATION_OBSERVATION=8、INFERENCE=7 |
| 置信度 | `VERIFIED_EXECUTION`=5、`PARTIAL`=2（`killing_blow_still_dies` 无 mutation；`latch_once` 无本轮证据） |
| 含失败知识 | 2（M04、M06 的历史 INVALID 根因与修复，状态 RESOLVED） |
| 未解决问题 | 6 条记录带 `unresolved_questions`（缺 Holdout / 缺 mutation / 缺证据） |

Knowledge Coverage = **7 / 60**（11.7%）。该维度未纳入八维 Fully Covered 判定（1.63 的定义未包含它），
因此没有借它提高 Fully Covered 数字。

## 5. 趋势结论

1. 本阶段真实推进：Evidence/Signature/Attestation/Evaluation 各 +4，Mutation Killed +1，Fully Covered 0 → 1。
2. 没有任何维度被删除或放宽；Fully Covered 的定义保持 1.63 的八维全满足。
3. 剩余 48 条 Behavior 无证据、50 条无 mutation——这些是缺口，不是 PASS。
