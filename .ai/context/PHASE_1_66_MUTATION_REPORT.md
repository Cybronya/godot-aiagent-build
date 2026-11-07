# Phase 1.66 — Knowledge-Driven Mutation

## 1. 候选生成

来源：**已审批** `SOURCE_OBSERVATION:guards` 记录（仅这些事实可以定位到真实 `if` 守卫）。
代码中没有 Behavior 名单；候选 ID 由 `feature|behavior|file|anchor` 的 sha256 决定（稳定、可复现）。

```text
candidates = 19
anchor_validation VALID   = 17
anchor_validation INVALID = 2   （锚点不唯一 / 不是 `if` 守卫）
existing_catalog          = 0   （全部为新增候选，未复用旧 catalog）
```

候选字段（`mutation_candidates.json`）：`mutation_candidate_id`、`feature_id`、`behavior_id`、
`target_symbol`、`target_file/line`、`mutation_operator`、`anchor`、`replacement`、
`knowledge_refs`、`expected_failure`、`expected_observations`、`safety_constraints`、
`execution_requirements`、`approval_status`。
未执行候选的 `approval_status=PENDING_APPROVAL`，不带 verdict/knowledge_id。

## 2. 执行门禁

- 只改 harness 创建的 `Features/` 副本（`require_inside` 校验）。
- 执行前校验 `source_sha256`、锚点唯一、operator 空 diff 拒绝、块结构守恒。
- 顺序：Negative Control → Mutation → Effectiveness → Recovery → Repo Guard。
- 仓库源码不被修改；`repo_guard` 前后快照 265 文件。

## 3. 本轮执行：`mc-55bda008e9123f41`

| 项 | 值 |
| --- | --- |
| Behavior | `trigger_switch/latch_once` |
| 目标 | `Features/trigger_switch/trigger_switch.gd:41` `if _triggered:` → `if false:` |
| 知识引用 | 已审批 `SOURCE_OBSERVATION:guards`（`_triggered` 守卫） |
| Run ID | `p166-55bda008e9123f41-111034` |
| 时长 | 56.35s（报告 11:10:34Z → 11:11:32Z） |
| Control Evaluation | `VERIFIED_PASS`（`signal@. = 1`） |
| Mutant Evaluation | `INVALID_EVIDENCE`（`signal@. = 2`，SIGNAL_MISMATCH） |
| Effectiveness | `effective=true`（`baseline_holds` + `mutant_holds`，同一观测口径） |
| Recovery | `verified=true`，`restored_byte_for_byte=true` |
| Repo Guard | `changed=false`，265 文件 |
| Verdict | **`MUTANT_KILLED`** |

报告：`.ai/tmp/p166/mutations/mc-55bda008e9123f41.json`（已写入知识记录引用并带 digest）。

## 4. 判定语义的诚实说明（重要）

`MUTANT_KILLED` 的定义是“mutation 生效且现有链路给出非通过结论”。本次非通过结论是
`INVALID_EVIDENCE`，不是 `VERIFIED_FAIL`：

- 行为差异本身已被 **effectiveness predicate** 独立证实：同一 `signal` 观测 control=1、
  mutant=2（`SIGNAL_MISMATCH`）。
- 但评估器把“观测 2 个信号 vs 契约声明 1 个”判为证据无效（`validator_rejected_evidence`），
  因此没有落到 `VERIFIED_FAIL`。
- 这属于 Phase 1.64 已记录的“评估归因缺陷（P2）”同一族：数量不匹配应优先归为行为失败语义，
  而不是证据无效。本阶段**不修改**该历史问题（负责人未授权），只登记。

结论边界：可以确认“禁用该守卫会导致可观测行为差异且被链路拒绝”，
不能宣称“这是一条干净的 VERIFIED_FAIL 缺陷”。两者差别已写进知识记录引用的报告原文。

## 5. 知识入库

`MUTATION_OBSERVATION`（`key=mutation_candidate:mc-55bda008e9123f41`）：
- `mutation_verdict=MUTANT_KILLED`（否则记录被 schema 拒绝）
- `confidence=VERIFIED`、`run_id` 记录、引用报告 + digest
- **`verification_status=PENDING_REVIEW`**（未自动批准，等待人工审核）
- content 含 control/mutant 观测与 `restored_byte_for_byte`

SURVIVED / INVALID / ERROR / TIMEOUT / NOT_RUN 一律不写知识（`test_mutation_candidates.M10`）。

## 6. 覆盖与未完成

- 19 个候选中只执行 1 个（任务书要求“不要求完成全部 Behavior Mutation”）。
- 其余 18 个候选保持 `PENDING_APPROVAL`，未执行、未计分。
- 2 个 `INVALID` 锚点保留在候选中并明确标注，**未删除**、未计入 KILLED。
