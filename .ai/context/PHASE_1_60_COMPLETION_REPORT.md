# Phase 1.60 完成报告 — Golden Trace, Holdout & Baseline Trusted Binding

日期：2026-11-03。分支 `master`，HEAD `dd3a0e4`（实施前后未变；全部成果为工作区未提交增量）。

## 1. 审计时 HEAD 和分支

`master` / `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`。工作区 996 条未提交修改
（Phase 1.56–1.59 成果均为未提交状态），与 `PHASE_1_60_AUDIT.md` §1 一致。

## 2. 实施前工作区状态

见 `.ai/context/PHASE_1_60_AUDIT.md`。实施过程未执行任何 `git reset/checkout/restore/
clean/add/commit/push`，未删除/覆盖他人修改，未整理 `code_library` 与历史 Evidence。

## 3. 当前 Golden Trace 架构

- 4 条编排场景基线（waves / holdout / single_stage_boss / multi_stage_boss）不变、
  不重录、事件字节未动；`trace_baselines.py` / `trace_replay.py` / 审批入口
  `approve_trace_baselines.py` 零修改。
- 新增逐行为绑定层（见 §4）与使用时摘要复核（见 §5/§6），全部为**加法式**新模块。

## 4. 新的 Binding Schema

`validator/trace_bindings.py` + `validator/bindings/behavior_bindings.json`：

- 字段：`binding_id / feature_id / behavior_id / scenario_id / trace_id /
  trace_version / contract_version / baseline_id / baseline_version / expected /
  expected_source / expected_source_ref / approved / approval_reference /
  created_at / updated_at`。`contract_version` 取契约内容的 SHA256 前 12 位
  （契约无显式版本字段；契约一变即 CONTRACT_MISMATCH）。
- **精确 ID 匹配**，无任何子串/名称推断（测试 B3/B4 锁定）。
- 归属来源：`behavior_contract`（任务书允许来源 #1）；`golden_trace /
  approved_baseline / combined_approved` 支持于 schema 并在验证器中实现。
- 当前 6 条绑定（BND-001…006）：collect_pickup/collect_on_contact、health/damage、
  save_game/save_slot_persists_world_state、save_game/load_slot_restores_world_state、
  trigger_switch/latch_once、openable_door/open —— expected 逐项复制自正式契约，
  绑定预期宽于契约时验证返回 CONTRACT_MISMATCH（测试 C4）。
- Trace 绑定状态：`SCENARIO_ONLY / BEHAVIOR_BOUND / BEHAVIOR_PARTIALLY_BOUND /
  UNBOUND`。**4 条编排场景基线保持 SCENARIO_ONLY，未自动升级**（1.58 的
  `NOT_APPLICABLE(binding: scenario_only)` 行为保留，测试 CB8/CB10 锁定）。

## 5. Baseline 生命周期

`validator/baseline_lifecycle.py`：状态机 `DRAFT → PENDING_REVIEW → APPROVED`、
`APPROVED → SUPERSEDED/REVOKED`、`REJECTED → DRAFT`；跳步与终态转换被拒
（测试 B1–B5）。只有 APPROVED 可用于正式评估。审批入口不变；登记表
`baselines/approval_registry.json` 与之并联（审批入口不知道它，使用方必须核对）。

## 6. Baseline Digest 规则

- 规范化序列化：`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",",":"))`
  → SHA256（方案 `baseline-content-digest-v1`）。
- 摘要覆盖评估相关载荷：events / comparison_policy / expected_final_state /
  scenario_id / 全部 schema 版本 / approved_behavior_version / coverage / source。
  **不含** approval 块本身（waves 的 coverage 修订先例证明 approval 元数据会合法追加）
  与 scenario_description（纯说明文字）——两者由**审批一致性核对**单独覆盖。
- 使用时复核（`use_baseline`）：① 文件内 approval.status=approved；
  ② 登记记录存在且为 APPROVED；③ 重算摘要 == 登记摘要；④ 文件内
  approver/approved_at/candidate_fingerprint 与登记一致。任一失败返回
  `DIGEST_MISMATCH / UNAPPROVED / MISSING_REGISTRATION / REVOKED / SUPERSEDED /
  APPROVAL_MISMATCH / INVALID_BASELINE`，绝不放行。
- 4 条既有基线以**显式迁移登记**（`migrate_existing_baseline`，依据 = 文件内既有
  审批块 + 指纹可复算），不是自动审批、不是新批准；迁移后篡改副本内容即被
  DIGEST_MISMATCH 拒绝（测试 D1/D2，真实基线文件未被改动）。

## 7. 审批流程

- 新审批：仍走 `e2e/approve_trace_baselines.py`（candidate → review → apply）；
  批准后**必须**在登记表注册（digest + approver + approved_at + 指纹 + basis）才能被
  Evaluation 使用。未登记 → `MISSING_REGISTRATION`，自报 `approved=true` 不能绕过
  （测试 C7/C7b：伪造审批块 → APPROVAL_MISMATCH / MISSING_REGISTRATION）。
- 修改 APPROVED 基线内容 → 摘要失配 → 旧审批失效，必须重新登记。

## 8. Holdout 生命周期

`evaluation/holdout_registry.py` + `evaluation/holdout/holdout_datasets.json`：
`CREATED → VALIDATED → SEALED → CONSUMED / INVALIDATED`；记录
`holdout_id / dataset_version / source / created_at / validated_at / sealed_at /
content_digest（holdout-dataset-digest-v1）/ feature_ids / behavior_ids /
usage_history / is_training_data / is_tuning_data / pollution`。

## 9. Holdout 隔离规则

1. `is_training_data` / `is_tuning_data` 恒 False，被标记即拒绝使用（测试 B5）。
2. 不提供任何基线写入口（Holdout 不能自动生成正式 Baseline）。
3. 消费追加 `usage_history` 并转 CONSUMED；重复使用被拒绝（真实端到端实测：
   第二次运行 → `holdout_dataset_unusable`）；重用必须显式新版本封存。
4. 封存后内容变化 → 摘要失配 → 拒绝（测试 B4）。
5. 污染记录（overlap_with_training / overlap_with_tuning /
   overlap_with_baseline_source / manual_invalidation）→ 拒绝（测试 D1/D2）。
6. 与 1.58 的批次隔离（`holdout_isolation`：bundle_id/run_id 不允许两边共用）叠加。
7. 缺 Holdout → 保留 1.58 的 `NOT_EVALUATED(holdout_unavailable)`（真实端到端 E2E-5），
   不降级为 VERIFIED_PASS。

## 10. Cross-Binding Validation

`trace_bindings.validate_binding()` 状态：`VALID_BINDING / MISSING_BINDING /
STALE_BINDING / INVALID_BINDING / UNAPPROVED_BASELINE / REVOKED_BASELINE /
DIGEST_MISMATCH / CONTRACT_MISMATCH / SCENARIO_MISMATCH / APPROVAL_MISMATCH（经
baseline_report 转发）/ NOT_APPLICABLE`。验证内容：身份精确一致、schema 合法、
场景一致、契约版本一致、绑定预期不宽于当前契约、关联 Baseline 受信。
不绕过 1.57 的 Artifact Cross-Validation（adapter 的 `load_verified` 内联调用，
先于绑定验证执行）。

## 11. Evaluation 集成方式

- `evidence_adapter.evaluate_task(..., bindings=...)`：任务声明
  `expected_source` 时，期望取自**已验证绑定**；门禁映射：缺失绑定 →
  `INCOMPLETE(binding_missing)`；失效/冲突/不可信 Baseline → `NOT_EVALUATED
  (baseline_unapproved / baseline_revoked / baseline_digest_mismatch /
  baseline_approval_mismatch / binding_stale / binding_scenario_mismatch /
  binding_contract_mismatch / binding_invalid)`。未声明 `expected_source` 的任务
  **保持 1.58 语义完全不变**，绑定仅作 `binding_status` 诊断字段。
- `baseline_report()` 增加使用时摘要复核；4 条基线经迁移登记后行为与 1.58 兼容
  （PASS），内容被改后不再 PASS。
- `evidence_eval.py`：新增 `--bindings`（缺省自动加载绑定库）、Holdout 任务可声明
  `holdout_id / holdout_dataset_version` → 使用前查登记、复核、消费登记；
  报告新增 `binding_reconciliation` 块。CLI 默认行为与退出码语义未变
  （退出码仍只看主任务；Holdout 缺口独立成块报告——1.58 文档化契约）。
- 状态模型不变：`VERIFIED_PASS / VERIFIED_FAIL / INVALID_EVIDENCE / INCOMPLETE /
  EVALUATION_ERROR / NOT_EVALUATED`。三条独立语义保持：Validator PASS ≠
  Evaluation PASS；Baseline APPROVED ≠ Evidence PASS；普通 Evaluation PASS ≠
  Holdout PASS。

## 12. 旧版数据兼容方式

- 4 条既有基线：显式迁移登记（记录 basis 与既有审批凭据），内容字节未动。
- 旧 Evidence（无绑定）：绑定仅诊断，不阻断、不伪造。
- 未登记基线：`MISSING_REGISTRATION`（不自动审批、不静默升级可信等级）。
- CLI 默认行为不变；新能力经 `--bindings`、任务字段 `expected_source / holdout_id`
  显式启用。

## 13. 测试结果（全部真实执行，Python 3.12.5）

| 套件 | 结果 |
| --- | --- |
| `validator/tests/test_baseline_lifecycle.py`（A–E，26 checks） | **PASS（26/26）** |
| `validator/tests/test_trace_bindings.py`（A–E，28 checks） | **PASS（28/28）** |
| `evaluation/tests/test_holdout_registry.py`（A–E，23 checks） | **PASS（23/23）** |
| `evaluation/tests/test_cross_binding.py`（CB1–CB10，15 checks） | **PASS（15/15）** |
| `evaluation/tests/test_evidence_adapter.py`（1.58 回归） | **PASS（52/52）** |
| `evaluation/tests/test_evidence_eval.py`（1.58 回归） | **PASS（20/20）** |
| `evaluation/tests/test_evaluation_runner.py` / `test_evaluation_scoring.py` | **PASS（24+28）** |
| `validator/tests/test_trace_baselines.py`（比较器/审批回归） | **PASS** |
| `validator/tests/test_behavior_evidence_stage.py`（1.56 回归） | **PASS** |
| `evaluation/mutation/tests/test_mutation_harness.py`（1.59 回归） | **PASS（51/51）** |
| `evaluation/mutation/tests/test_mutation_integration.py`（1.59 回归） | **PASS（15/15）** |
| `validator/validate.py` | **0 error / 17 warning（与基线一致）** |

任务书 §8 矩阵覆盖情况：8.1（Binding）→ test_trace_bindings A/B/C/D；
8.2（Baseline）→ test_baseline_lifecycle A–E（含伪造审批、篡改、REVOKE、SUPERSEDED、
登记丢失）；8.3（Holdout）→ test_holdout_registry A–E；8.4（Cross-Binding）→
test_cross_binding CB1–CB10；8.5（真实端到端）→ 下节。
未覆盖项：SUPERSEDED 基线「按版本策略处理」只实现为拒绝（无自动版本切换），已按
拒绝语义测试；Holdout 与训练数据重叠的自动**检测**依赖调用方登记 pollution
（当前无训练系统，无自动检测对象），接口与拒绝行为已测试。

## 14. 真实 Godot 端到端结果

真实 Godot headless（4.7.stable）采集 3 类 Behavior + Holdout 1 类，全链路
（Feature → Probe → Collector → Validator → Binding → Baseline → Evaluation）：

| 用例 | 结果 |
| --- | --- |
| 状态转换：health/damage（真实 take_damage 5→1 + health_changed ×1） | 采集 PASS ×5 行为；E2 `VERIFIED_PASS` |
| 事件传播：collect_pickup/collect_on_contact（真实接触 → freed + collected ×1） | 采集 PASS；E1 `VERIFIED_PASS` |
| 持久化：save_game 两条行为（真实存/读档，last_slot=behavior_save） | 采集 PASS ×2；E3 `VERIFIED_PASS` |
| 三任务合跑（绑定诊断 + 基线摘要复核启用） | `VERIFIED_PASS=3`，**exit 0** |
| Holdout：openable_door/open 独立批次采集 → 登记 → 封存 v3 → E5 消费 | 隔离 PASS、binding VALID、`VERIFIED_PASS` |
| E5 重复消费（第二次运行同一数据集） | `NOT_EVALUATED(holdout_dataset_unusable)` —— 复用被真实拒绝 |
| E5 缺 Holdout（无 --holdout-dir） | `NOT_EVALUATED(holdout_unavailable)`，独立成块，不降级 |
| 证据包篡改（改观测不重签，真实采集副本） | `INVALID_EVIDENCE`，**exit 1** |
| 声明 expected_source 但绑定缺失 | `INCOMPLETE(binding_missing)`，exit 2 |
| 真实 waves 基线篡改副本 + 绑定门禁 | `NOT_EVALUATED(baseline_digest_mismatch)` |

以上由 `evaluation/tests/test_phase160_e2e.py`（5/5 PASS）与
`.ai/tmp/eval/8024-3dbddd61/evidence_report.json` 等真实报告承载。
实施中暴露并修复的真实缺陷：E5 的 `last_args` 期望缺 `count`（`expected_holds`
对 signal 缺省 count=0 → 必然 False）。E5 在 1.58 因 Holdout 不可用从未被真实评估，
本次首次执行即暴露；修复为补 `count: 1`（**加严**，非放宽），任务书冻结规则不违反。

## 15. Phase 1.59 Mutation 兼容性结果

`mutation/` 目录零修改。审计确认：Mutation 的 `effect.baseline` 是 Mutation Test
Expectation（在 control 观测上求值），不读 Golden Baseline、不写基线、KILLED 不升级为
Expected——与正式 Golden Baseline 的分离保持不变。回归：51 + 15 项全 PASS（上表）。

## 16. 未解决的信任边界（必须如实声明）

- **A 内容完整性：已交付**（SHA256 + 使用时复核）。
- **B 审批流程完整性：已交付**（状态机 + 登记表 + 摘要与审批一致性对账）。
- **C 审批者身份真实性：未完成，本阶段不宣称完成**。`approver` 是自报文本，
  `--i-approve` 无身份认证，登记表与基线同权限可写——**同权限攻击者仍可同时改写
  内容、摘要与登记记录**。独立签名 / 外部信任根属于后续阶段。
- Holdout 的「独立泛化能力」证明依赖独立数据来源的真实性（当前 source 是自报文本）。
- 绑定 expected 的「审批」是登记制（引用契约路径与验证链），不是独立主体签名。

## 17. 未运行测试

- `run_tests.py` 全量入口未在本阶段运行（历史记录显示其受环境删除守卫影响；
  本阶段以受影响套件的逐项真实执行代替，全部列出如 §13）。
- e2e 生成链路套件（`test_end_to_end_generation.py`，29 min）未运行——本阶段未触碰
  生成链路。其余 121 个测试文件中与本阶段改动无交集的套件未重复执行
  （1.57 已做过分段全量回归）。
- Godot 侧 `Tests/*.gd` 未改动、未重跑（生产 GDScript 零修改）。

## 18. 下一阶段建议

1. 独立审批者身份：最小方案为外部签名根（离线私钥签登记表），或至少把登记表
   移出工作区可写范围。
2. Holdout 来源真实性：把数据集 source 从自报文本升级为带签名的采集凭据。
3. 扩展绑定覆盖：当前 6/60 行为有逐行为绑定（54 个如实未绑定）；可按 Feature
   分批生成契约级绑定（生成器 + 漂移检测已就位，即 `contract_version` 摘要）。
4. 为 SCENARIO_ONLY 的 4 条编排场景建立「场景声明行为全集」登记，使
   BEHAVIOR_BOUND / PARTIALLY_BOUND 判定可用（当前缺 scenario_behavior_total
   声明时保守判 PARTIALLY）。
