# Phase 1.58 — Evaluation Evidence Integration（完成报告）

- 时间：2026-11-03
- 基线：HEAD `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`，分支 `master`（工作区有未提交修改，
  其中 `.ai/skills/.../code_library` 约 950 条为他人并行产物，本阶段未触碰）
- 结论：**已完成并实测**。Evaluation 现在消费 Validator 独立验证过的行为证据；Validator PASS
  与 Evaluation PASS 在状态模型层面强制分离；默认 CLI 与退出码未变，新路径显式 opt-in。
- 证据标签：本文用 **FACT**（本次命令输出/文件内容可直接复核）、**INFERENCE**（由事实推出、
  未直接观测）、**UNKNOWN**（无法验证）标注。

未执行任何 git 写操作（无 add / commit / push / reset / checkout / clean / rebase）。

---

## 1. 审计基准（§1）

| 侧 | 组件 | 现状（FACT） |
| --- | --- | --- |
| Evaluation | `evaluation/runner.py` | 5 个冻结任务 T1–T5，阶段 `plan/artifacts/loadable/behavior/negative/regression`；自带探针判行为 |
| Evaluation | `evaluation/scoring.py` | 纯函数；状态词表 `PASS/FAIL/SKIP/NOT_EXECUTED/INCOMPLETE/UNAVAILABLE` |
| Evidence | `scene_composer/feature_behavior_evidence.py` | 真实 Godot 执行契约动作，`--evidence-out` 落盘带完整性摘要的证据包；23 Feature / 60 Behavior |
| Evidence | `validator/check_behavior_evidence.py` | 用 `template.yaml#behavior` 重算观测，不采信自报 `status`；`expected_holds()` 可复用 |
| Evidence | `validator/execution_artifacts.py` | 从 `evidence_paths` 的真实 `result.json` 交叉验证执行标识/重放/观测 |
| Trace | `validator/baselines/*.json` | 4 个已批准基线：只有 `scenario_id` + `approved_behavior_version`，**无 Feature/Behavior 绑定** |

**断点确认**（FACT）：改造前 Evaluation 与上述证据链路零耦合——`runner.py` 既不读证据包，
也不引用 Validator 的任何模块。

---

## 2. 架构：只加 Adapter，不重写两侧（§2）

```
Features/*/template.yaml#behavior
  → feature_behavior_evidence.py  [采集：真实 Godot]
  → validator/check_behavior_evidence.py  [验证：重算 + 交叉验证]
  → evaluation/evidence_adapter.py  [适配：读结论 + 重算任务期望]
  → evaluation/evidence_eval.py  [评估：状态模型 + 报告]
```

新增文件：

| 文件 | 职责 |
| --- | --- |
| `evaluation/evidence_adapter.py` | `load_verified()` / `evaluation_status()` / `evaluate_expectations()` / `evaluate_task()` / `supported_set()` / `baseline_report()` / `compare_with_baseline()` / `holdout_isolation()` / `summarize()` / `coverage_gap()` |
| `evaluation/evidence_eval.py` | 新入口：Mode A / Mode B / Holdout / 报告 / 退出码 |
| `evaluation/evidence_tasks.yaml` | E1–E5 任务定义（4 正向 + 1 Holdout） |
| `evaluation/tests/evidence_fixtures.py` | 测试夹具（真实契约 + `bundle_digest` 签名） |
| `evaluation/tests/test_evidence_adapter.py` | 52 项 |
| `evaluation/tests/test_evidence_eval.py` | 20 项 |

**没有**重写 Runner / Validator / Feature Registry / Golden Trace 审批 / Holdout 生成，
没有新增第三方依赖，23 Feature / 60 Behavior 全部动态读取（`declared_features()`、
`build_contracts()`），未硬编码。

---

## 3. 状态模型（§3、§4）

`evaluation_status(validator_status, expectation_state)` 是唯一转换点：

| Validator \ 期望 | 满足 | 不满足 | 无法判定 |
| --- | --- | --- | --- |
| PASS | `VERIFIED_PASS` | `VERIFIED_FAIL` | `INCOMPLETE` |
| FAIL | `INVALID_EVIDENCE` | `INVALID_EVIDENCE` | `INVALID_EVIDENCE` |
| INCOMPLETE | `INCOMPLETE` | `INCOMPLETE` | `INCOMPLETE` |
| ERROR | `EVALUATION_ERROR` | `EVALUATION_ERROR` | `EVALUATION_ERROR` |

- 非法转换（未知 Validator 结论、空结论）→ `EVALUATION_ERROR(illegal_transition)`；
- `PASS` 但任务没有期望 → `EVALUATION_ERROR(expectation_missing)`，**绝不**默认成 PASS（B8 实测）；
- `NOT_EVALUATED` 只用于「没跑」：`collection_skipped`、`holdout_unavailable`。

**期望重算**：任务文件的 `expect` 交给 `check_behavior_evidence.expected_holds()`，
在同一批**真实观测**上求值；不读采集侧自报的 `status`。因此「证据有效但行为不符合需求」
落到 `VERIFIED_FAIL`（§11 实测），这是 Validator 单方面做不到的判定。

**包级拒绝传播**（本轮修的关键缺陷，FACT）：包摘要不符 / 过期 / 协议变更会让 Validator
总体 `FAIL`，但逐条契约复算可能仍 `PASS`；若只看逐条结果就会把被拒的包当有效证据。
`load_verified()` 用 `bundles[]` 的包级结论覆盖包内每条 behavior
（`FAIL(bundle_rejected)` / `INCOMPLETE(bundle_incomplete)`），**只降级、不升级**。
实测：篡改真实证据包 → `evidence: FAIL` 且 `rejected_bundles: p158-real.json=FAIL(integrity mismatch…)`，
评估结论 `INVALID_EVIDENCE`。

---

## 4. 任务映射与覆盖（§5）

- 映射键 `(feature, behavior)`；未知 Feature → `EVALUATION_ERROR(unknown_feature)`，
  未知 Behavior → `EVALUATION_ERROR(unknown_behavior)`，重复映射 → 结构错误（退出码 1）。
- 跨 Feature 证据不复用：只给 `collect_pickup` 证据时评估 `health` → `INCOMPLETE(no_evidence)`（C4 实测）。
- 一任务多行为时取**最严重**状态折叠（C6 实测：`VERIFIED_PASS` + `VERIFIED_FAIL` → `VERIFIED_FAIL`）。

**本轮修的真实缺陷**（FACT）：E3 的期望把 `target` 写成 `"."`，而 save_game 的真实观测节点是
`Saver` / `World/Player/Health`，导致 `expectation_undecidable`（"no observation for this check"）。
修正任务文件（写明真实观测节点）后 E3 → `VERIFIED_PASS`。这不是放宽判定，而是把期望写准。

---

## 5. 三种模式（§6）

| 模式 | 触发 | 证据来源 | `VERIFIED_*` |
| --- | --- | --- | --- |
| A | `mode: evidence`（默认） | 存量证据包 | 计入 |
| B | `mode: probe` | 本次真实采集（每 Feature 一次）后同一链路复核 | 计入 |
| C | `runner.py` + `--evidence-report` | 旧探针 | **不计入**，标 `LEGACY_PROBE_ONLY` |

- Mode C 默认行为与退出码完全不变（未传参时报告结构不变，H11 实测）；
- 接入证据报告时：校验 schema id，错误则退出码 2 且不写入假数据；旧任务逐条标
  `LEGACY_PROBE_ONLY`，并在输出里单列 `VERIFIED_PASS/FAIL/INVALID_EVIDENCE`（H12 实测）。

**Mode B 真实采集修复**（FACT）：`collect_feature()` 原先给采集器传了不存在的
`--artifact-root`，采集器立即 `exit 2 (unrecognized arguments)`，E4 因此 `no_evidence`。
移除该参数、并让 probe 证据复用默认产物根后，E4 真实采集 → `VERIFIED_PASS`。

---

## 6. Golden Trace（§7）

实测结论（FACT）：`baselines/{waves,holdout,multi_stage_boss,single_stage_boss}.json` 只有
场景级 `scenario_id` 与 `approved_behavior_version=phase-1.22-orchestration-trace-contract-v1`，
**没有 Feature/Behavior 绑定**。因此：

- 逐行为 trace 比较→ `NOT_APPLICABLE`，`binding: scenario_only`，`feature/behavior: null`（不伪造）；
- 基线审批状态为 `approved` 才接受：未审批 → `BASELINE_UNAPPROVED`，结构损坏 → `INVALID_BASELINE`
  （结构错误优先于「未审批」，避免把损坏文档误报成没批），缺失 → `INCOMPLETE`；
- 真实 Expected/Actual 比较走 `--trace` + `--baseline`，复用 `trace_baselines.compare()`：
  由基线事件重建 trace（换 `run_id`）→ `PASS` 且 `matched_event_count == 事件总数`；
  改动一条事件 `reason` → `REGRESSION` 且 `differences` 非空（F5/F6 实测）。

---

## 7. Holdout（§8）

- Holdout 任务独立成块，`metrics.holdout` 与主评估计数**分开**；主表不含 holdout 行（H8 实测）；
- 未提供 `--holdout-dir` → `NOT_EVALUATED(holdout_unavailable)`，**不计为通过**，也不伪造；
- 与训练批共用 bundle 或 run_id → `EVALUATION_ERROR` + `violations`，holdout 任务同样置错（H9 实测）；
  批次独立（不同 `bundle_id` + 不同 `run_id`）→ 无违规（G2 实测）。
- 本轮未做 Holdout 的自动生成/自动选批，只做隔离判定与如实报告。

---

## 8. 报告与退出码（§9）

报告 `.ai/tmp/eval/<pid>-<uuid8>/evidence_report.json`，schema `evaluation_evidence_report` v1：

`run` / `structural_problems` / `supported` / `evidence` / `collections` / `tasks` /
`holdout` / `golden_trace` / `metrics` / `limitations`。

- `metrics.evidence_validation` 与 `metrics.behavior_evaluation` 是两个独立计数器；
  后者逐状态计数，不合并；`bundles` / `rejected_bundles` 单列，避免 `pass=N fail=0` 被误读。
- 每个任务带可追溯字段：`execution_id`、`evidence_bundle_ref`、`artifact_digests`、
  `protocol_version`、`behavior_version`、`baseline_id`。
- 退出码：`0` 全 `VERIFIED_PASS`；`1` 有 `VERIFIED_FAIL`/`INVALID_EVIDENCE`/`EVALUATION_ERROR`；
  `2` 有 `INCOMPLETE`/`NOT_EVALUATED`；`3` 输入/环境错误。

---

## 9. 测试矩阵（§10）

`test_evidence_adapter.py`（52 项）+ `test_evidence_eval.py`（20 项），**72 项全过**；
既有 `test_evaluation_runner.py`（24 项）仍全过。

| 组 | 覆盖 |
| --- | --- |
| A（11 组用例） | 合法 PASS / 包篡改 / 缺产物 / Validator ERROR / 未知 Feature / 未声明 Behavior / `result.json` 改写 / 缺 integrity / 摘要与路径保留 / 协议版本保留 / 旧 schema |
| B（8 项） | 状态转换表六行 + 非法转换 + 缺期望不升级 |
| C（8 项） | 正确映射 / 未知 Feature / 未知 Behavior / 跨 Feature / 重复映射 / 多行为折叠 / 跨批次混用 / 支持集动态读取 |
| D（7 项） | `VERIFIED_PASS` / `INVALID_EVIDENCE` / `INCOMPLETE` / `VERIFIED_FAIL` / 观测缺失 / 可追溯字段 / 汇总分离 |
| F（6 项） | 已批准基线 / 未审批 / 损坏 / 缺失 / 一致 PASS / 差异 REGRESSION |
| G（2 项） | Holdout 同批复用 → 违规；批次独立 → 无违规 |
| H（12 项） | `--list` / Mode A 正常与报告结构 / 更严期望 / 篡改 / 缺产物 / 未知 Feature / 重复映射 / Holdout 未提供 / Holdout 复用 / Mode B 跳过 / runner 兼容 / runner 接入 |

夹具用**真实契约**构造观测并写入真实 `result.json` + `bundle_digest` 签名，测的是判定逻辑
而不是「夹具能否过校验」。所有夹具在 `.ai/tmp/` 临时目录内，测试结束删除。

---

## 10. 真实端到端（§11）

采集（真实 Godot，FACT）：`--feature collect_pickup --feature health --feature save_game`
→ **8 条行为全 PASS**（`pass=8 mismatch=0 insufficient=0 invalid=0`），
包 `.ai/tmp/p158/bundles/p158-real.json`，Validator 复核 `checked=8 pass=8 artifacts=16 cross_validated=8`。

| 场景 | 命令要点 | 结果 | 退出码 |
| --- | --- | --- | --- |
| Mode A + B 全通过 | `evidence_eval.py --evidence-dir .ai/tmp/p158/bundles` | E1–E3 `VERIFIED_PASS`，E4（真实采集 trigger_switch）`VERIFIED_PASS` | 0 |
| 禁采集 | 追加 `--no-collect` | E1–E3 `VERIFIED_PASS`；E4 `NOT_EVALUATED(collection_skipped)` | 2 |
| 更严期望（同一批真实证据） | `health.current equals 99` | `VERIFIED_FAIL(behavior_mismatch)`，Validator 仍 PASS | 1 |
| 证据包篡改 | 改一条观测、不重签 | `INVALID_EVIDENCE(validator_rejected_evidence)`，包级 `integrity mismatch` | 1 |
| Holdout 未提供 | 默认任务集含 E5 | `NOT_EVALUATED(holdout_unavailable)`，独立成块 | —（不改变主结论） |

主报告：`.ai/tmp/eval/10856-84242ddd/evidence_report.json`；
其余：`4720-97e0bd6a`（禁采集）、`1156-a9f64dbb`（更严期望）、`10764-d5f36868`（篡改）。

---

## 11. 覆盖对账（§12）

| 集合 | 数量 | 口径 |
| --- | --- | --- |
| 支持集（契约） | 60 行为 / 23 Feature | 动态读取 |
| 证据集（本轮） | 8 | 3 Feature |
| 评估集 | 5 | E1、E2、E3×2、E4 |
| Golden Trace 集 | 0 | 基线无 Feature/Behavior 绑定 → `NOT_APPLICABLE` |
| Holdout 集 | 0 | 未提供独立批次 → `NOT_EVALUATED` |

有证据但无评估任务（如实登记，未补任务凑数）：`health/death`、`health/heal_clamped`、
`health/overkill_clamps_at_zero`、`health/post_death_guard`。
其余 55 条行为既未评估、也未在本轮采集，状态为 `NOT_EVALUATED`，**不是 PASS**。
本节数字已同步到 `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md`。

---

## 12. 文档（§13）

- `.ai/tools/evaluation/README.md`：新增 Phase 1.58 章节（三种模式 / 状态表 / 报告与退出码 /
  Golden Trace 与 Holdout / 测试命令）；
- `.ai/tools/validator/README.md`：新增「下游消费方：Evaluation」小节（调用关系与口径约定）；
- `.ai/context/WORK_STATE.md`、`CURRENT_TASK.md`、`FEATURE_BEHAVIOR_COVERAGE.md` 已更新。

---

## 13. 验收矩阵（§14）

| # | 要求 | 结论 | 依据 |
| --- | --- | --- | --- |
| 1 | 不重写两侧，Adapter 连接 | 达成 | 只新增 3 个模块 + 1 个入口；Validator / Runner 判定逻辑未改 |
| 2 | 不新增第三方依赖 | 达成 | 仅用标准库 + 既有模块 |
| 3 | 不硬编码 23/60 | 达成 | `supported_set()` 动态读取；测试 C8 断言与 `declared_features()` 一致 |
| 4 | Validator PASS ≠ Evaluation PASS | 达成 | 状态表 + `VERIFIED_FAIL` 实测（更严期望） |
| 5 | 六状态分开统计 | 达成 | `metrics.behavior_evaluation` 逐状态；H3/H4/H5 实测 |
| 6 | 默认 CLI/退出码兼容 | 达成 | `runner.py --list` = 0；未传参报告结构不变；`test_evaluation_runner.py` 24 项通过 |
| 7 | Mode C 标 `LEGACY_PROBE_ONLY` 且不计入 | 达成 | H11/H12 |
| 8 | 包级拒绝不被逐条 PASS 掩盖 | 达成 | A2、真实篡改用例 |
| 9 | 期望来自任务、不采信自报 status | 达成 | `expected_holds()` 重算；D4/H3 |
| 10 | Golden Trace 不伪造绑定 | 达成 | F1（`binding: scenario_only`）、F2–F6 |
| 11 | Holdout 不可用如实报告 | 达成 | H8/H9；`NOT_EVALUATED` 独立计数 |
| 12 | 真实端到端（正/负） | 达成 | §10 五组运行 |
| 13 | 覆盖对账 | 达成 | §11 + 覆盖矩阵文件 |
| 14 | 测试 | 达成 | 72 项新增全过 + 24 项既有全过 |
| 15 | 未操作 git | 达成 | 未执行任何写操作 |

---

## 14. 未解决问题（§15）

1. **证据来源真实性（UNKNOWN）**：哈希只证明内容完整，同权限下改实现再重签即可绕过。
   与 Phase 1.56/1.57 记录的信任边界相同，本阶段未声称解决。
2. **逐行为 Golden Trace 缺失（FACT）**：4 个基线只有场景级绑定，无法按 Feature/Behavior
   比较；要补必须改基线 schema 并重新审批，本阶段未擅自扩写。
3. **Holdout 未自动串联**：只做隔离判定与如实报告，未实现「自动生成独立批次并驱动评估」。
4. **覆盖仍小**：评估集 5/60 行为；证据集 8/60。`VERIFIED_PASS=4` 不代表整体行为质量。
5. **Mode B 成本**：每 Feature 一次真实 Godot 采集（本轮 3 Feature ≈ 数分钟）；未做采集缓存，
   也没必要在没有需求前优化。
6. **`runner.py` 的 Mode C 折叠**只加可选参数，未把旧任务映射到证据行为——旧任务仍是探针式，
   这是有意保留（不假装旧结论等于已验证结论）。

---

## 15. Phase 1.59 建议（§16）

1. **扩大评估集**：为剩余 55 条行为补任务，或用「契约→任务」生成器批量产出
   （期望直接来自 `template.yaml#behavior` 的默认阈值），再人工审一遍避免自证。
2. **逐行为 Golden Trace**：给基线加可选 `behavior_bindings`，审批流程保持只增不改；
   在绑定存在前继续 `NOT_APPLICABLE`。
3. **Holdout 自动化**：把 `holdout` 生成器与 `evidence_eval --holdout-dir` 串起来，
   并强制「批次独立」检查（本轮已有判定器）。
4. **来源可信**：引入签名密钥或可信执行环境，解决「改实现再重签」的绕过。
5. **评估基线对比**：把两次评估报告做差分（新出现 `VERIFIED_FAIL` / `INVALID_EVIDENCE` 即回归），
   与现有 `trace_baselines` 思路一致。
