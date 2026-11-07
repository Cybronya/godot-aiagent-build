# Phase 1.66 — Knowledge-Driven Test Generation & Execution 架构

日期：2026-11-07
上游：Phase 1.65（Source Analysis 60/60、Dependency Graph 60/118、Knowledge 45 条、
Planner 277 任务、Pilot 5 Behavior，12 条候选场景全部 `executed=false`）。

## 1. 目标闭环

```text
Knowledge Store（1.64/1.65）
   ↓  planner.py 选目标与缺口
Learning Planner（276 任务，本阶段后）
   ↓  scenario_generator.py（知识事实 → 参数化场景）
Scenario Validator（scenario_validate.py，7 状态）
   ↓  scenario_run.py（Execution Planner + 真实 Godot 执行）
真实执行（scene_composer/feature_behavior_evidence.py，1.56/1.62 链路）
   ↓  Evidence Bundle / Manifest / Execution Attestation
Validator / Evaluation（evaluation/evidence_eval.py，1.57/1.58）
   ↓  result_analysis.py（9 分类，双结论）
Candidate Knowledge（feedback.py，默认 PENDING_REVIEW）
   ↓  feedback.py --review（本地显式审批）
Knowledge Store（新增 4 类型，历史版本保留）
   ↓  planner.py --scenario-results
Next Learning Plan（真实执行结果排除已完成设计任务）
```

## 2. 模块与职责

| 模块 | 职责 | 不做什么 |
| --- | --- | --- |
| `scenario_generator.py` | 读已审批知识 + 契约 + 依赖图，按 5 条规则生成场景 | 不改产品源码/契约/基线；不执行 |
| `scenario_validate.py` | 7 状态验证（契约/来源/知识/依赖/环境/可执行性） | 不自动降低要求换 PASS |
| `scenario_run.py` | Execution Planner（指纹/隔离/唯一 Run ID）+ 调真实采集器与评估 | 不模拟 Godot；不伪造 PASS |
| `result_analysis.py` | 从真实四个结果层推导分类 | 不在证据不足时给根因 |
| `feedback.py` | 场景/执行/行为/测试设计候选知识 + 显式审核 | 不自动 APPROVED；不覆盖历史 |
| `mutation_candidates.py` | 已审批守卫知识 → Mutation Candidate → 交 1.59 harness | 不改仓库源码；只认 KILLED |
| `knowledge_v2.py`（扩展） | 4 个新知识类型的门禁 + `revive()` 生命周期 | 不重定义已有类型 |

## 3. 复用而非重建

- **执行**：`scene_composer/feature_behavior_evidence.py` 的 `verify_contract`，
  `--features-dir` 指向隔离 worktree；不新增 Runner。
- **证据/验证/评估**：`evidence_eval.py`（1.57 Artifact Cross-Validation、1.58 Evaluation）、
  1.62 `execution_attestation`；`scenario_run` 只做编排与结果汇总。
- **Mutation**：`evaluation/mutation/harness.py`（1.59）的 Control/Mutation/Recovery + repo_guard。
- **知识**：`knowledge_v2` 的 ID/版本/冲突/撤销/归档；不建平行 Store。

## 4. 数据流与产物

| 产物 | 路径 |
| --- | --- |
| 场景索引 | `.ai/learning/scenarios.json` |
| 单场景 | `.ai/learning/scenarios/<scenario_id>.json` |
| 验证报告 | `.ai/learning/scenario_validation.json` |
| 执行计划 | `.ai/tmp/p166/runs/<run_id>/plan.json` |
| 执行结果汇总 | `.ai/learning/scenario_results.json`（本轮 label=`P4`） |
| Evidence Bundle | `.ai/tmp/p166/evidence/*.json` |
| 结果分析 | `.ai/learning/result_analysis.json` |
| 回流候选 | `.ai/learning/feedback.json` |
| Mutation 候选/报告 | `.ai/learning/mutation_candidates.json`、`.ai/tmp/p166/mutations/**` |
| 计划 | `.ai/learning/learning_plan.json`（前态 `learning_plan_before_p166.json`） |

## 5. 隔离与信任边界

- 每次执行独立 run 目录、独立 `user://` 目录标签、独立证据目录；Run ID 唯一。
- 证据目录**只在批次开始时**清理本批次自己的文件（`_prepare_dirs(..., clean=True)`）；
  单场景运行/被拒绝的运行绝不清理——本阶段实测曾因此误删真实证据，已修复并写测试。
- 信任级别仍为 `LOCAL_ISOLATED`：四指纹 + Attestation 只证明“本地隔离环境内一致性”，
  不升级为 `EXTERNAL_TRUSTED_RUNNER`。
- 签名状态按实际记录，不用“缺签名”换 PASS。

## 6. 结论边界（双结论设计）

扩展场景的期望项数量通常多于正式契约（例如 `signal` 计数），因此：

| 结论层 | 含义 |
| --- | --- |
| `scenario_expectation` | 本场景自定义观测是否满足（决定 Execution/Evaluation） |
| `official_contract_status` | 正式契约（数量/条目）是否匹配，单独记录 |

二者不互相冒充：5 个场景全部 `evaluation=VERIFIED_PASS`，但官方契约为
PASS 1 / FAIL 2 / INCOMPLETE 2，差异原因逐条记录在 `PHASE_1_66_EXECUTION_REPORT.md`。
