# Phase 1.60 执行前审计（以当前仓库为准）

审计时间：2026-11-03。审计人：Phase 1.60 执行 Agent。
所有结论均来自当前工作区的真实代码与文件，不引用历史报告作为事实来源。

## 1. Git 与工作区事实（实测）

- 分支：`master`；HEAD：`dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`。
- `git status --porcelain` 共 **996 条**：含大量未提交修改（`M`）与删除（`D`）。
- 已确认的关键未提交成果（与 WORK_STATE.md 记载一致）：
  - `.ai/tools/evaluation/evidence_adapter.py`、`evidence_eval.py`（Phase 1.58）
  - `.ai/tools/validator/check_behavior_evidence.py`、`execution_artifacts.py`（1.56/1.57）
  - `.ai/tools/evaluation/mutation/`（Phase 1.59）
  - `.ai/context/WORK_STATE.md`、`CURRENT_TASK.md`、`FEATURE_BEHAVIOR_COVERAGE.md`
  - `Features/*/template.yaml` 多处修改（含 `behavior` 契约）
- 未跟踪目录/文件较多（996 条中含 `??`），本阶段不整理、不删除、不提交。
- 结论：**Phase 1.56–1.59 的成果以未提交状态存在于工作区**，历史 HEAD 不包含它们；
  一切实现必须叠加在当前工作区之上，禁止任何 `git reset/checkout/restore/clean`。

## 2. 当前真实架构（实测）

### 2.1 Golden Trace（编排场景级）

- 基线文件：`.ai/tools/validator/baselines/{waves,holdout,single_stage_boss,multi_stage_boss}.json`。
  每条含 `scenario_id`、`baseline_version`、`events[]`、`approval{status=approved,
  candidate_fingerprint, ...}`、`coverage`、`expected_final_state`。
- **全部 4 条只有场景级绑定**，无 `feature` / `behavior` 字段 —— 与 Phase 1.58 报告一致。
- 回放/比较：`validator/trace_replay.py`、`validator/trace_baselines.py`
  （`validate_baseline`、`compare`、`compare_files`）。
- 审批：`e2e/approve_trace_baselines.py`（candidate → review → apply --i-approve；
  指纹 scheme 1/2，review/apply 时重算）。审批记录含 `approver`（自由文本，无身份认证）。

### 2.2 Evidence → Validator → Evaluation（1.56–1.58）

- 采集：`scene_composer/feature_behavior_evidence.py --evidence-out DIR` 写
  `feature_behavior_evidence_bundle`（schema_version 1，`integrity.payload_sha256`，
  每行为 `expected/actual`、`replay_count/consistent`、`evidence_paths`、`artifact_digests`）。
- 复核：`validator/check_behavior_evidence.py`（`check_evidence()` API）用
  `template.yaml#behavior` 契约重算；`validator/execution_artifacts.py` 从真实
  `result.json` 交叉验证（Phase 1.57）。
- Evaluation：`evaluation/evidence_adapter.py`（`load_verified` / `evaluate_task` /
  `evaluation_status` / `baseline_report` / `compare_with_baseline` / `holdout_isolation` /
  `supported_set` 动态读取支持集）+ `evaluation/evidence_eval.py`（Mode A/B/C）。
- 状态模型（1.58，必须保留）：`VERIFIED_PASS / VERIFIED_FAIL / INVALID_EVIDENCE /
  INCOMPLETE / EVALUATION_ERROR / NOT_EVALUATED`，转换表写死在 `evaluation_status()`。

### 2.3 Holdout 现状

- 语义一：关卡编排模式（`holdout` 生存模式 + `holdout.json` 黄金基线）——与评估无关。
- 语义二：评估侧 Holdout（E5 任务）：`--holdout-dir` 独立证据目录 +
  `adapter.holdout_isolation()` 做批次隔离（bundle_id / run_id 不允许两边共用）。
  缺失时 → `NOT_EVALUATED(holdout_unavailable)`（1.58 语义）。
- **不存在** Holdout 数据集生命周期对象：无 `holdout_id / dataset_version /
  content_digest / sealed_at / usage_history`，无污染判定、无重复消费防护。

### 2.4 Mutation Harness（1.59）

- `evaluation/mutation/`：catalog / operators / workspace / harness / mutation_eval。
- **实测确认：Mutation 不依赖 Golden Trace Baseline。** catalog 中每条 mutation 的
  `effect.baseline`（如 `{equals: 1}`）是 **Mutation Test Expectation**，由
  `harness.py` 在 control 观测上用 `catalog.stage_expected()` 求值；
  不读 `baselines/*.json`，不写任何基线，不把 KILLED 结果升级为 Expected。
- 兼容性风险点：`harness.py` 调用采集器与 Validator 的路径；本轮对这些模块只做
  加法式扩展，不改其调用签名。

## 3. 绑定缺口（本阶段要关闭的）

1. **无逐 Behavior 绑定**：Trace/Baseline 只有 `scenario_id`；Evidence 的
   Feature/Behavior 归属由 Validator 重算（1.56/1.57），但 Evidence ↔ Trace/Baseline
   之间没有正式绑定文档，`baseline_report()` 硬性返回 `binding: "scenario_only"`。
2. **无 Expected 来源追溯**：任务的 `expect` 只存在于 evidence_tasks.yaml；
   契约 expected 在 template.yaml；两者都没有 binding 文档串联，`expected_source`
   字段不存在。
3. **Baseline 生命周期缺失**：`approval.status` 只有 `approved` 一种值在使用；
   无 DRAFT/PENDING_REVIEW/REJECTED/SUPERSEDED/REVOKED 状态机；
   **使用时不重算内容摘要**（现有 candidate_fingerprint 只在审批时重算；
   `baseline_report()` 只做结构校验）→ 审批后改内容可以逃过 `baseline_report`。
   这是本阶段用 Content Digest + 使用时复核关闭的核心缺口。
4. **审批绕过路径（现状确认）**：`baseline_report()` 信任文件内 `approval.status`
   字段 + `trace_baselines.validate_baseline()`；同权限者改文件内容但保留 approval
   块即可绕过（结构仍合法）。指纹虽在文件内，但 `baseline_report()` 不验指纹。
   → 使用时必须重算摘要并与审批登记比对。
5. **Holdout 隔离不足**：只有批次隔离；无数据集身份、无封存摘要、无使用记录、
   无「训练/调优数据分类」边界。

## 4. 可复用的现有接口（不重写）

- `check_behavior_evidence.check_evidence()` / `load_bundle()` / `expected_holds()`
- `execution_artifacts`（1.57 交叉验证，绑定验证不得绕过它 —— adapter 的
  `load_verified` 已内联调用）
- `trace_baselines.validate_baseline() / compare()`
- `evidence_adapter` 的状态模型、`supported_set()`、`evaluate_task()`、`summarize()`
- `evidence_eval.py` 的 Mode A/B/C 骨架与 CLI
- `approve_trace_baselines.py` 审批入口（保持不变，注册表与之并联）
- 采集器 `feature_behavior_evidence.py`（Mode B 真实采集）

## 5. 不应修改的文件

- `.ai/tools/e2e/approve_trace_baselines.py`（审批入口冻结；注册表只读地引用其产物）
- `.ai/tools/validator/trace_replay.py`、`trace_baselines.py`（回放/比较语义冻结）
- `.ai/tools/validator/execution_artifacts.py`、`check_behavior_evidence.py`
  （1.56/1.57 判定核心；只允许新增调用，不改判定）
- `.ai/tools/evaluation/mutation/**`（1.59 冻结）
- `.ai/tools/evaluation/runner.py`、`scoring.py`（Mode C 兼容）
- 生产 GDScript（`Orchestration/**`、`Scenes/**`、`Features/**/*.gd`）
- 4 条黄金基线 `baselines/*.json`（不重录、不改内容）
- 其他 Agent 的未跟踪产物与 `code_library`

## 6. Phase 1.60 实施方案（最小加法）

新增模块（全部为新增文件，零重写）：

1. `validator/baseline_lifecycle.py`：
   - 规范化序列化（sort_keys + 紧凑分隔符）→ SHA256 内容摘要，覆盖
     评估相关载荷（events/scenario_id/comparison_policy/expected_final_state/
     schema 版本/approved_behavior_version/coverage），**不含 approval 块本身**
     （waves 的 coverage 修订先例证明 approval 元数据会合法变化）。
   - 状态机 DRAFT/PENDING_REVIEW/APPROVED/REJECTED/SUPERSEDED/REVOKED；
     审批登记表 `validator/baselines/approval_registry.json`
     （baseline_id + version + digest + 审批者 + 时间 + 依据）。
   - `use_baseline()`：使用时重算摘要并核对登记；不匹配 → 拒绝。
   - 4 条既有基线：以**显式迁移登记**入表（依据 = 文件内既有 approval 块 +
     指纹可复算），不是自动审批、不是新批准；迁移记录写明 basis。
2. `validator/trace_bindings.py`：
   - Binding Schema（binding_id/feature_id/behavior_id/scenario_id/trace_id/
     trace_version/contract_version/baseline_id/baseline_version/expected/
     expected_source/approved/approval_reference/created_at/updated_at）。
   - 绑定库 `validator/bindings/behavior_bindings.json`；**精确 ID 匹配**，
     禁止子串推断。
   - Trace 绑定状态：`SCENARIO_ONLY / BEHAVIOR_BOUND / BEHAVIOR_PARTIALLY_BOUND /
     UNBOUND`；场景级 Trace 不自动升级（保留 1.58 的
     `NOT_APPLICABLE(binding: scenario_only)`）。
   - `validate_binding()` → `VALID_BINDING / MISSING_BINDING / STALE_BINDING /
     INVALID_BINDING / REVOKED_BASELINE / UNAPPROVED_BASELINE / DIGEST_MISMATCH /
     CONTRACT_MISMATCH / SCENARIO_MISMATCH / NOT_APPLICABLE`。
3. `evaluation/holdout_registry.py`：
   - 数据集生命周期 CREATED/VALIDATED/SEALED/CONSUMED/INVALIDATED；
     `holdout_id/dataset_version/source/content_digest/sealed_at/
     feature_ids/behavior_ids/usage_history/is_training_data/is_tuning_data`。
   - 封存摘要 + 使用时复核；消费追加 usage_history；重复消费/污染/重叠检测；
     与 `holdout_isolation()` 的批次检查叠加。
4. 集成（`evidence_adapter.py` / `evidence_eval.py`，加法式）：
   - `baseline_report()` 增加使用时摘要复核（登记缺失 → 不判定为 PASS）。
   - 任务可声明 `expected_source`；golden_trace/baseline 来源必须有
     BEHAVIOR_BOUND 绑定 + 受信 Baseline，否则 NOT_EVALUATED / INCOMPLETE；
     缺省任务保持 1.58 语义不变（`binding_status` 仅作诊断字段）。
   - 覆盖对账 `binding_reconciliation()`：正式支持集动态读取，统计
     已绑定/部分绑定/未绑定、Baseline 覆盖、Holdout 覆盖、过期绑定。
5. 测试：`test_baseline_lifecycle.py`、`test_trace_bindings.py`、
   `test_holdout_registry.py`、`test_cross_binding.py` + 真实 Godot 端到端
   （状态转换 = health/damage；事件传播 = collect_pickup/collect_on_contact；
   持久化 = save_game 两行为），篡改/缺失/未审批负向全部实测。
   完成后跑 1.59 mutation 回归 + evaluation 既有 4 套回归。

## 7. 信任边界（审计确认，写入完成报告）

- **A 内容完整性**：SHA256 + 使用时复核 → 本阶段可交付。
- **B 审批流程完整性**：状态机 + 登记表 + 摘要对账 → 本阶段可交付。
- **C 审批者身份真实性**：`approver` 是自由文本、`--i-approve` 无身份认证、
  注册表与基线同权限可改 → **本阶段不宣称完成**。同权限攻击者仍可同时改写
  内容、登记表与审批记录；独立签名/外部信任根留待后续阶段。
- Mutation Test Expectation（catalog `effect.baseline`）与正式 Golden Baseline
  是两类东西，现状已分离，本阶段保持分离并在文档中显式声明。
